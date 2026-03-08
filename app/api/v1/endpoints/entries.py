"""
OneTwenty-compatible Entries API endpoints.

GET  /entries              — list entries (count, hours, start/end, find[] query)
GET  /entries/current      — latest SGV entry (JSON or TSV via Accept header)
GET  /entries/{spec}       — fetch by ObjectId or filter by type (e.g. /entries/sgv)
POST /entries              — upload entries (upsert, dedup by sysTime+type)
DELETE /entries            — delete entries matching find[] query
DELETE /entries/{spec}     — delete by ObjectId or by type

Auth: API secret header → JWT Bearer → subdomain (multi-strategy, same as original NS).
"""

from __future__ import annotations

import re
import time as _time
from datetime import datetime, timezone
from email.utils import formatdate
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

import asyncio
from app.api.deps import get_tenant_from_api_key, get_mongo_db
from app.repositories.event import EventRepository
from app.schemas.entry import EntryCreate
from app.services.entries import EntriesService

router = APIRouter()

# 24-char hex ObjectId pattern
_ID_RE = re.compile(r"^[a-f\d]{24}$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Auth helper — shared across all entries endpoints
# ---------------------------------------------------------------------------

async def _resolve_tenant(request: Request, api_secret: Optional[str]) -> str:
    """
    Multi-strategy auth resolution (mirrors original OneTwenty).
    Passes directly into deps.py for robust Auth/Doctor Cross-Tenant checking.
    """
    from app.api.deps import get_current_tenant_from_api_secret_or_jwt
    return get_current_tenant_from_api_secret_or_jwt(request, api_secret)


def _last_modified_header(entries: List[Dict]) -> Optional[str]:
    """Return RFC-7231 Last-Modified value from the newest entry, or None."""
    if not entries:
        return None
    newest_ms = max((e.get("date") or e.get("mills") or 0) for e in entries)
    if newest_ms:
        return formatdate(newest_ms / 1000, usegmt=True)
    return None


def _check_not_modified(request: Request, last_modified_str: Optional[str]) -> bool:
    """
    Return True if the client's If-Modified-Since means we should send 304.
    Mirrors original OneTwenty ifModifiedSinceCTX behavior.
    """
    if not last_modified_str:
        return False
    ims = request.headers.get("If-Modified-Since")
    if not ims:
        return False
    try:
        from email.utils import parsedate_to_datetime
        lm_dt = parsedate_to_datetime(last_modified_str)
        ims_dt = parsedate_to_datetime(ims)
        return lm_dt <= ims_dt
    except Exception:
        return False


def _parse_find_params(request: Request) -> Optional[Dict[str, Any]]:
    """
    Parse find[field][op]=value style query params from the raw query string.

    Examples:
        ?find[sgv][$gte]=120        → {"sgv": {"$gte": "120"}}
        ?find[type]=sgv             → {"type": "sgv"}
        ?find[date][$gte]=123456789 → {"date": {"$gte": "123456789"}}

    Type-casting of numeric fields is handled downstream in build_mongo_query().
    """
    find: Dict[str, Any] = {}
    # qs gives us repeated keys; FastAPI exposes raw query string via request.url.query
    raw_qs = request.url.query

    for part in raw_qs.split("&"):
        if not part.startswith("find"):
            continue
        if "=" not in part:
            continue
        key_part, value = part.split("=", 1)
        # Decode URL encoding
        from urllib.parse import unquote
        value = unquote(value)
        key_part = unquote(key_part)

        # Match: find[field] or find[field][$op]
        m = re.match(r"find\[([^\]]+)\](?:\[([^\]]+)\])?", key_part)
        if not m:
            continue
        field = m.group(1)
        op = m.group(2)  # e.g. "$gte", or None for simple equality

        if op:
            if field not in find:
                find[field] = {}
            if isinstance(find[field], dict):
                find[field][op] = value
        else:
            find[field] = value

    return find if find else None


def _parse_timestamp(ts: str) -> int:
    """Parse ISO or numeric Unix-ms timestamp string; returns int milliseconds."""
    if ts.lstrip("-").isdigit():
        return int(ts)
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


# ---------------------------------------------------------------------------
# POST /entries  (all aliases)
# ---------------------------------------------------------------------------

@router.post("/entries", status_code=201)
@router.post("/entries/", status_code=201)
@router.post("/entries.json", status_code=201)
async def create_entries(
    entries: Union[List[EntryCreate], EntryCreate],
    request: Request,
    tenant_id: str = Depends(get_tenant_from_api_key),
):
    """
    Upload CGM entries.
    - Normalizes dates (sysTime, utcOffset, dateString) on write.
    - Upserts by (sysTime, type, tenant_id) — safe for retried/duplicate uploads.
    - Returns full array of stored documents (matching original OneTwenty shape).
    - Broadcasts to WebSocket clients.
    """
    from app.websocket.manager import manager

    service = EntriesService()
    stored_entries = await service.create_entries(entries, tenant_id)

    for entry in stored_entries:
        await manager.broadcast_to_tenant(tenant_id, {"type": "new_entry", "data": entry})

    return stored_entries


# ---------------------------------------------------------------------------
# GET /entries/current  — MUST be declared before /entries/{spec}
# ---------------------------------------------------------------------------

@router.get("/entries/current")
@router.get("/entries/current.json")
async def get_current_entry(
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    """
    Latest SGV entry.

    Content negotiation (mirrors original OneTwenty):
    - Accept: application/json (default) → single-element JSON array
    - Accept: text/plain | text/tab-separated-values → TSV line
    """
    tenant_id = await _resolve_tenant(request, api_secret)
    service = EntriesService()

    entry = await service.get_current_sgv(tenant_id)
    if not entry:
        raise HTTPException(status_code=404, detail="No entries found")

    lm = _last_modified_header([entry])
    accept = request.headers.get("Accept", "application/json")

    # TSV response
    if "text/plain" in accept or "text/tab-separated-values" in accept:
        tsv = (
            f'"{entry.get("dateString","")}\t'
            f'{entry.get("date","")}\t'
            f'{entry.get("sgv","")}\t'
            f'"{entry.get("direction","")}"'
            f'\t"{entry.get("device","")}"'
            "\n"
        )
        resp = PlainTextResponse(content=tsv, media_type="text/plain; charset=utf-8")
        if lm:
            resp.headers["Last-Modified"] = lm
        return resp

    # Default: JSON array (single element)
    response = JSONResponse(content=[entry])
    if lm:
        response.headers["Last-Modified"] = lm
    return response


# ---------------------------------------------------------------------------
# GET /entries-with-events
# ---------------------------------------------------------------------------

@router.get("/entries-with-events")
@router.get("/entries/entries-with-events")
async def get_entries_with_events(
    request: Request,
    start: str,
    end: str,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
    db = Depends(get_mongo_db)
):
    """
    Combined fetch for both entries and treatments (events) in a time range.
    Mirrors some custom client requirements (e.g. report generators).
    Path: /api/v1/entries-with-events OR /api/v1/entries/entries-with-events
    """
    t0 = _time.time()
    tenant_id = await _resolve_tenant(request, api_secret)
    
    try:
        start_ms = _parse_timestamp(start)
        end_ms = _parse_timestamp(end)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp: {exc}")

    entries_service = EntriesService()
    event_repo = EventRepository(db)

    # Fetch concurrently
    entries_task = asyncio.create_task(
        entries_service.get_entries_by_timestamp_range(tenant_id, start_ms, end_ms)
    )
    events_task = asyncio.create_task(
        event_repo.get_multi_by_tenant(tenant_id, limit=1000, start_date=start_ms, end_date=end_ms)
    )

    entries, events = await asyncio.gather(entries_task, events_task)
    
    print(f"[TIMING] GET /entries-with-events total: {(_time.time()-t0)*1000:.1f}ms")

    return {
        "entries": entries,
        "events": events
    }


# ---------------------------------------------------------------------------
# GET /entries
# ---------------------------------------------------------------------------

@router.get("/entries")
@router.get("/entries/")
async def get_entries(
    request: Request,
    count: Optional[int] = None,
    hours: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    """
    List CGM entries.

    Query parameter priority: find[] > start+end > hours > count (default 10).

    - find[field][$op]=value — full MongoDB-style filter (mirrors original NS)
      e.g. find[sgv][$gte]=120&find[type]=sgv
    - start / end — ISO 8601 or Unix ms timestamps
    - hours — last N hours
    - count — last N records
    """
    t0 = _time.time()
    tenant_id = await _resolve_tenant(request, api_secret)
    service = EntriesService()

    find = _parse_find_params(request)
    resolved_count = count or 10

    if find:
        # find[] takes priority — passes through to MongoDB with type casting/date enforcement
        result = await service.query_entries(tenant_id, find=find, count=resolved_count)
    elif start is not None and end is not None:
        try:
            result = await service.get_entries_by_timestamp_range(
                tenant_id, _parse_timestamp(start), _parse_timestamp(end)
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid timestamp: {exc}")
    elif hours is not None:
        result = await service.get_entries_by_time_range(tenant_id, hours)
    else:
        result = await service.get_entries(tenant_id, resolved_count)

    print(f"[TIMING] GET /entries total: {(_time.time()-t0)*1000:.1f}ms")

    # If-Modified-Since / Last-Modified
    lm = _last_modified_header(result)
    if _check_not_modified(request, lm):
        return Response(status_code=304)

    response = JSONResponse(content=result)
    if lm:
        response.headers["Last-Modified"] = lm
    return response


# ---------------------------------------------------------------------------
# GET /entries/{spec}  — by ObjectId or by type (e.g. /entries/sgv)
# ---------------------------------------------------------------------------

@router.get("/entries/{spec}")
async def get_entries_by_spec(
    spec: str,
    request: Request,
    count: Optional[int] = None,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    """
    Fetch entry by ObjectId or filter by type.

    - /entries/65cf81bc436037528ec75fa5 → single entry by ID
    - /entries/sgv                     → list of SGV entries
    - /entries/mbg                     → list of manual BG entries
    """
    tenant_id = await _resolve_tenant(request, api_secret)
    service = EntriesService()

    if _ID_RE.match(spec):
        # Fetch by ObjectId
        entry = await service.get_entry_by_id(spec, tenant_id)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"Entry not found: {spec}")

        lm = _last_modified_header([entry])
        response = JSONResponse(content=[entry])
        if lm:
            response.headers["Last-Modified"] = lm
        return response
    else:
        # Treat spec as type filter
        entries = await service.get_entries_by_type(spec, tenant_id, count=count or 10)

        lm = _last_modified_header(entries)
        if _check_not_modified(request, lm):
            return Response(status_code=304)

        response = JSONResponse(content=entries)
        if lm:
            response.headers["Last-Modified"] = lm
        return response


# ---------------------------------------------------------------------------
# DELETE /entries/{spec}  — by ObjectId or by type
# ---------------------------------------------------------------------------

@router.delete("/entries/{spec}")
async def delete_entries_by_spec(
    spec: str,
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    """
    Delete entry by ObjectId or all entries of a given type.

    - DELETE /entries/65cf81bc436037528ec75fa5 → delete one by ID
    - DELETE /entries/sgv                     → delete all SGV entries for tenant
    - DELETE /entries/*                       → delete all entries for tenant (type wildcard)
    """
    tenant_id = await _resolve_tenant(request, api_secret)
    service = EntriesService()

    if _ID_RE.match(spec):
        deleted = await service.delete_entry_by_id(spec, tenant_id)
        if deleted == 0:
            raise HTTPException(status_code=404, detail=f"Entry not found: {spec}")
        return {"deleted": deleted}
    else:
        # Type filter; "*" means all
        if spec == "*":
            deleted = await service.delete_entries_by_find(tenant_id, find=None)
        else:
            deleted = await service.delete_entries_by_type(spec, tenant_id)
        return {"deleted": deleted}


# ---------------------------------------------------------------------------
# DELETE /entries  — by find[] query
# ---------------------------------------------------------------------------

@router.delete("/entries")
@router.delete("/entries/")
async def delete_entries_by_query(
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    """
    Delete entries matching a find[] query.
    e.g. DELETE /entries?find[date][$lte]=1756339200000
    """
    tenant_id = await _resolve_tenant(request, api_secret)
    service = EntriesService()

    find = _parse_find_params(request)
    deleted = await service.delete_entries_by_find(tenant_id, find=find)
    return {"deleted": deleted}
