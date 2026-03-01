from app.db.mongo import db
from bson import ObjectId
from bson.errors import InvalidId
from typing import List, Any, Dict, Optional
import re


# Fields that should be cast to int when received as strings from query parameters
# (mirrors original OneTwenty lib/server/query.js walker spec for entries)
_INT_FIELDS = {"date", "sgv", "filtered", "unfiltered", "rssi", "noise", "mbg"}

# Default time window enforced when no date constraint is present in a find[] query
# Mirrors original OneTwenty: deltaAgo = TWO_DAYS * 2 = 4 days in ms
_DEFAULT_DELTA_AGO_MS = 4 * 24 * 60 * 60 * 1000


def _cast_int_fields(obj: Any) -> Any:
    """
    Recursively cast leaf values of known numeric fields to int.
    Operates on a find[] sub-dict like {"$gte": "120"} → {"$gte": 120}.
    """
    if isinstance(obj, dict):
        return {k: _cast_int_fields(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_cast_int_fields(v) for v in obj]
    if isinstance(obj, str):
        try:
            return int(obj)
        except (ValueError, TypeError):
            pass
    return obj


def build_mongo_query(tenant_id: str, find: Optional[Dict] = None, count: int = 10) -> Dict:
    """
    Translate the parsed `find` dict (from query string) into a MongoDB query dict.

    Mirrors original OneTwenty lib/server/query.js `create()`:
    - Casts numeric fields (date, sgv, filtered, …) to int
    - If no date constraint is present, enforces date >= (now - 4 days)
    - Always scopes to tenant_id

    The `find` dict is already pre-parsed from the query string by FastAPI
    (using qs-style bracket notation flattened into nested dicts).
    """
    import time as _time

    query: Dict[str, Any] = {"tenant_id": tenant_id}

    if find:
        for field, value in find.items():
            if field in _INT_FIELDS:
                query[field] = _cast_int_fields(value)
            else:
                query[field] = value

    # Enforce default date filter if no date / dateString constraint was given
    if "date" not in query and "dateString" not in query and "_id" not in query:
        min_date_ms = int(_time.time() * 1000) - _DEFAULT_DELTA_AGO_MS
        query["date"] = {"$gte": min_date_ms}

    return query


def _stringify_id(entry: Dict) -> Dict:
    if "_id" in entry and not isinstance(entry["_id"], str):
        entry["_id"] = str(entry["_id"])
    return entry


class EntriesRepository:
    def __init__(self):
        pass

    @property
    def collection(self):
        return db.get_db().entries

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def upsert_many(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Upserts documents into the 'entries' collection, one at a time.

        Deduplication key: { sysTime, type, tenant_id }
        Mirrors original OneTwenty lib/server/entries.js create() upsert logic.
        Returns the full list of documents as stored (with _id as string).
        """
        if not documents:
            return []

        result_docs = []

        for doc in documents:
            dedup_filter = {
                "sysTime": doc["sysTime"],
                "type": doc.get("type", "sgv"),
                "tenant_id": doc["tenant_id"],
            }

            update_result = await self.collection.update_one(
                dedup_filter,
                {"$set": doc},
                upsert=True
            )

            if update_result.upserted_id:
                doc["_id"] = str(update_result.upserted_id)
            else:
                existing = await self.collection.find_one(dedup_filter, {"_id": 1})
                if existing:
                    doc["_id"] = str(existing["_id"])

            result_docs.append(doc)

        return result_docs

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_many(self, tenant_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Count-based fetch, newest first."""
        cursor = self.collection.find({"tenant_id": tenant_id})
        cursor.sort("date", -1).limit(limit)
        entries = await cursor.to_list(length=limit)
        return [_stringify_id(e) for e in entries]

    async def get_by_time_range(
        self, tenant_id: str, start_time_ms: int, end_time_ms: int
    ) -> List[Dict[str, Any]]:
        """Time range fetch, oldest-first (for chart rendering)."""
        import time
        t0 = time.time()

        query = {
            "tenant_id": tenant_id,
            "date": {"$gte": start_time_ms, "$lte": end_time_ms},
        }
        cursor = self.collection.find(query)
        cursor.sort("date", 1)
        entries = await cursor.to_list(length=None)

        print(f"[TIMING] MongoDB fetch: {(time.time() - t0)*1000:.2f}ms — {len(entries)} entries")
        return [_stringify_id(e) for e in entries]

    async def query(
        self, mongo_query: Dict[str, Any], limit: int = 10, sort_field: str = "date", sort_dir: int = -1
    ) -> List[Dict[str, Any]]:
        """
        Flexible query — used for find[] parameter support.
        mongo_query must already include tenant_id scope.
        """
        cursor = self.collection.find(mongo_query)
        cursor.sort(sort_field, sort_dir).limit(limit)
        entries = await cursor.to_list(length=limit)
        return [_stringify_id(e) for e in entries]

    async def get_by_id(self, entry_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single entry by its MongoDB ObjectId."""
        try:
            oid = ObjectId(entry_id)
        except (InvalidId, Exception):
            return None
        entry = await self.collection.find_one({"_id": oid, "tenant_id": tenant_id})
        if entry:
            _stringify_id(entry)
        return entry

    async def get_latest_sgv(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the most recent SGV entry — for GET /entries/current."""
        entry = await self.collection.find_one(
            {"tenant_id": tenant_id, "type": "sgv"},
            sort=[("date", -1)]
        )
        if entry:
            _stringify_id(entry)
        return entry

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_by_id(self, entry_id: str, tenant_id: str) -> int:
        """Delete a single entry by ObjectId. Returns number deleted (0 or 1)."""
        try:
            oid = ObjectId(entry_id)
        except (InvalidId, Exception):
            return 0
        result = await self.collection.delete_one({"_id": oid, "tenant_id": tenant_id})
        return result.deleted_count

    async def delete_by_query(self, mongo_query: Dict[str, Any]) -> int:
        """
        Delete all entries matching mongo_query.
        mongo_query must already include tenant_id scope.
        Returns the number of deleted documents.
        """
        result = await self.collection.delete_many(mongo_query)
        return result.deleted_count

    # ------------------------------------------------------------------
    # Index bootstrap
    # ------------------------------------------------------------------

    async def ensure_indexes(self) -> None:
        """
        Create indexes on the entries collection if they don't already exist.
        Mirrors original OneTwenty lib/server/entries.js indexedFields.
        Called once at application startup.

        NOTE on dedup_key:
        sparse=True does NOT skip null values — it only skips missing fields.
        Old docs have {"sysTime": null} (field present, value null), so sparse
        would still index them and cause DuplicateKeyError.
        partialFilterExpression restricts the index to only docs where sysTime
        is a string — old null/missing docs are excluded entirely.
        """
        col = self.collection

        await col.create_index([("date", -1)])
        await col.create_index("type")
        await col.create_index("sysTime")
        await col.create_index("dateString")

        # Compound index matching original NS: type + date + dateString
        await col.create_index([("type", 1), ("date", -1), ("dateString", 1)])

        # Multi-tenant essential: tenant_id + date for all common queries
        await col.create_index([("tenant_id", 1), ("date", -1)])

        # Dedup key: drop unconditionally first to clear any stuck/stale build
        # from a previous startup, then recreate.
        try:
            await col.drop_index("dedup_key")
        except Exception:
            pass  # Not found — that's fine

        # Compound index on (tenant_id, sysTime, type) — speeds up the upsert
        # filter lookup in upsert_many(). Not unique: the collection may have
        # pre-P0 duplicates from insert_many; uniqueness is enforced in
        # upsert_many() at the application layer.
        await col.create_index(
            [("tenant_id", 1), ("sysTime", 1), ("type", 1)],
            name="dedup_key"
        )

        print("[DB] Entries indexes ensured")

