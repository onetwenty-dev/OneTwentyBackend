from datetime import datetime, timezone, timedelta
from typing import List, Union, Optional, Dict, Any
from app.repositories.entries import EntriesRepository, build_mongo_query
from app.schemas.entry import EntryCreate


def _normalize_entry(doc: dict) -> dict:
    """
    Mirrors original OneTwenty lib/server/entries.js create() normalization.

    1. Parse dateString (with timezone offset) via fromisoformat, or fall back to date ms.
    2. Compute: utcOffset (minutes), sysTime (UTC ISO), normalize dateString to sysTime.
    3. Add mills alias for date.
    4. Default type to "sgv".
    """
    date_str = doc.get("dateString")
    date_ms = doc.get("date")

    parsed = None
    utc_offset_minutes = 0

    if date_str:
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            parsed = dt
            if dt.tzinfo is not None:
                utc_offset_minutes = int(dt.utcoffset().total_seconds() / 60)
        except (ValueError, AttributeError):
            pass

    if parsed is None and date_ms is not None:
        parsed = datetime.fromtimestamp(date_ms / 1000, tz=timezone.utc)
        utc_offset_minutes = 0

    if parsed is None:
        parsed = datetime.now(tz=timezone.utc)

    parsed_utc = parsed.astimezone(timezone.utc)
    sys_time = parsed_utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{parsed_utc.microsecond // 1000:03d}Z"

    doc["utcOffset"] = utc_offset_minutes
    doc["sysTime"] = sys_time
    doc["dateString"] = sys_time      # Overwrite to normalized UTC ISO
    doc["mills"] = doc.get("date", 0)

    if "type" not in doc or not doc["type"]:
        doc["type"] = "sgv"

    return doc


def _strip_internal(entry: dict) -> dict:
    """Remove internal fields that must not appear in API responses."""
    entry.pop("tenant_id", None)
    return entry


class EntriesService:
    def __init__(self):
        self.repository = EntriesRepository()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create_entries(
        self, entries: Union[List[EntryCreate], EntryCreate], tenant_id: str
    ) -> List[dict]:
        """
        Normalize + upsert entries. Returns full stored documents.
        """
        if not isinstance(entries, list):
            entries = [entries]

        documents = []
        for entry in entries:
            doc = entry.dict()
            doc["tenant_id"] = tenant_id
            doc = _normalize_entry(doc)
            documents.append(doc)

        stored = await self.repository.upsert_many(documents)
        return [_strip_internal(dict(d)) for d in stored]

    # ------------------------------------------------------------------
    # Read — simple
    # ------------------------------------------------------------------

    async def get_entries(self, tenant_id: str, count: int = 10) -> List[dict]:
        entries = await self.repository.get_many(tenant_id, limit=count)
        return [_strip_internal(e) for e in entries]

    async def get_entries_by_time_range(self, tenant_id: str, hours: int) -> List[dict]:
        import time
        t0 = time.time()
        end_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        start_ms = end_ms - hours * 3600 * 1000
        print(f"[TIMING] Service: time range calc {(time.time()-t0)*1000:.1f}ms")
        entries = await self.repository.get_by_time_range(tenant_id, start_ms, end_ms)
        print(f"[TIMING] Service: total {(time.time()-t0)*1000:.1f}ms")
        return [_strip_internal(e) for e in entries]

    async def get_entries_by_timestamp_range(
        self, tenant_id: str, start_ms: int, end_ms: int
    ) -> List[dict]:
        import time
        t0 = time.time()
        entries = await self.repository.get_by_time_range(tenant_id, start_ms, end_ms)
        print(f"[TIMING] Service: ts-range {(time.time()-t0)*1000:.1f}ms")
        return [_strip_internal(e) for e in entries]

    # ------------------------------------------------------------------
    # Read — find[] query (P1)
    # ------------------------------------------------------------------

    async def query_entries(
        self, tenant_id: str, find: Optional[Dict] = None, count: int = 10
    ) -> List[dict]:
        """
        Execute a find[]-style query against MongoDB.
        `find` is a pre-parsed dict from the query string, e.g.:
            {"sgv": {"$gte": 120}, "type": "sgv"}
        """
        mongo_query = build_mongo_query(tenant_id, find, count)
        entries = await self.repository.query(mongo_query, limit=count)
        return [_strip_internal(e) for e in entries]

    # ------------------------------------------------------------------
    # Read — by spec (ID or type) (P1)
    # ------------------------------------------------------------------

    async def get_entry_by_id(self, entry_id: str, tenant_id: str) -> Optional[dict]:
        entry = await self.repository.get_by_id(entry_id, tenant_id)
        if entry:
            _strip_internal(entry)
        return entry

    async def get_entries_by_type(
        self, entry_type: str, tenant_id: str, count: int = 10
    ) -> List[dict]:
        find = {"type": entry_type}
        mongo_query = build_mongo_query(tenant_id, find, count)
        entries = await self.repository.query(mongo_query, limit=count)
        return [_strip_internal(e) for e in entries]

    async def get_current_sgv(self, tenant_id: str) -> Optional[dict]:
        entry = await self.repository.get_latest_sgv(tenant_id)
        if entry:
            _strip_internal(entry)
        return entry

    # ------------------------------------------------------------------
    # Delete (P1)
    # ------------------------------------------------------------------

    async def delete_entry_by_id(self, entry_id: str, tenant_id: str) -> int:
        return await self.repository.delete_by_id(entry_id, tenant_id)

    async def delete_entries_by_type(
        self, entry_type: str, tenant_id: str
    ) -> int:
        """Delete all entries of a given type for the tenant."""
        mongo_query = build_mongo_query(tenant_id, {"type": entry_type})
        # Remove the default date filter for delete — delete all matching type
        mongo_query.pop("date", None)
        return await self.repository.delete_by_query(mongo_query)

    async def delete_entries_by_find(
        self, tenant_id: str, find: Optional[Dict] = None
    ) -> int:
        """Delete entries matching a find[] query."""
        mongo_query = build_mongo_query(tenant_id, find)
        return await self.repository.delete_by_query(mongo_query)
