from fastapi import APIRouter, Depends, Body, Request, Header, HTTPException
from typing import List, Union, Optional
from app.schemas.entry import EntryCreate
from app.api.deps import get_tenant_from_api_key, get_tenant_from_jwt, get_mongo_db
from app.services.entries import EntriesService

router = APIRouter()

@router.post("/entries", status_code=201)
@router.post("/entries/", status_code=201)
@router.post("/entries.json", status_code=201)
async def create_entries(
    entries: Union[List[EntryCreate], EntryCreate],                                                                                                                                                                                                                                                                                                                                             
    tenant_id: str = Depends(get_tenant_from_api_key)
):
    """                                                                                 
    Creates one or more entries for the authenticated tenant.
    Broadcasts new entries to connected WebSocket clients.
    """                                                                                                                                                                                  
    from app.websocket.manager import manager
    
    service = EntriesService()
    entry_ids = await service.create_entries(entries, tenant_id)
    
    # Broadcast to WebSocket clients
    entries_list = entries if isinstance(entries, list) else [entries]
    for entry in entries_list:
        entry_dict = entry.dict()
        entry_dict['tenant_id'] = tenant_id
        
        # Add OneTwenty-compatible fields
        if 'date' in entry_dict:
            entry_dict['mills'] = entry_dict['date']
            if 'dateString' not in entry_dict:
                from datetime import datetime
                entry_dict['dateString'] = datetime.fromtimestamp(entry_dict['date'] / 1000).isoformat() + '.000Z'
            entry_dict['sysTime'] = entry_dict.get('dateString')
            if 'utcOffset' not in entry_dict:
                entry_dict['utcOffset'] = 0
        
        # Broadcast to all connected clients for this tenant
        await manager.broadcast_to_tenant(tenant_id, {
            "type": "new_entry",
            "data": entry_dict
        })
    
    return {"inserted_ids": entry_ids}

@router.get("/entries", status_code=200)
@router.get("/entries/", status_code=200)
async def get_entries(
    count: Optional[int] = None,
    hours: Optional[int] = None,
    start: Optional[str] = None,  # ISO timestamp or Unix timestamp (ms)
    end: Optional[str] = None,    # ISO timestamp or Unix timestamp (ms)
    api_secret: Optional[str] = Header(None, alias="api-secret"),
    request: Request = None
):
    """
    Fetches entries for the authenticated user's tenant.
    Supports:
    1. API key (header: api-secret) - for uploaders/write-access clients
    2. JWT (header: Authorization) - for dashboard/saas users
    3. Subdomain (URL) - for public/read-only access (if no auth provided)
    
    Query parameters:
    - count: Number of entries to fetch (default: 10)
    - hours: Time range in hours (e.g., 2, 4, 6, 12, 24). Takes precedence over count.
    """
    import time
    request_start = time.time()
    
    tenant_id = None

    # 1. Try API key first (for OneTwenty uploaders)
    auth_start = time.time()
    if api_secret:
        # Standard behavior: if key is invalid, 401. 
        # But we'll let dependency handle exception if we call it directly
        tenant_id = get_tenant_from_api_key(request, api_secret)
        print(f"[TIMING] API: API key auth took {(time.time() - auth_start)*1000:.2f}ms")

    # 2. If no API key, check Authorization header (JWT)
    if not tenant_id:
        jwt_start = time.time()
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from jose import jwt
                from app.core.config import settings
                from app.repositories.user import UserRepository
                
                token = auth_header.replace("Bearer ", "")
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = int(payload.get("sub"))
                
                repo = UserRepository()
                tenant_id = repo.get_tenant_for_user(user_id)
                if tenant_id:
                    tenant_id = str(tenant_id)
                print(f"[TIMING] API: JWT auth took {(time.time() - jwt_start)*1000:.2f}ms")
            except Exception as e:
                print(f"JWT auth failed: {e}")  # Debug logging
                pass # Invalid JWT, fall through
        
    # 3. If still no tenant, try Subdomain (Public Read-Only)
    if not tenant_id:
        subdomain_start = time.time()
        from app.api.deps import get_tenant_from_subdomain
        tenant_id = get_tenant_from_subdomain(request)
        print(f"[TIMING] API: Subdomain auth took {(time.time() - subdomain_start)*1000:.2f}ms")
        
    if not tenant_id:
         raise HTTPException(status_code=401, detail="Authentication required (API Key, JWT, or valid Subdomain)")
    
    auth_total = time.time()
    print(f"[TIMING] API: Total auth time {(auth_total - request_start)*1000:.2f}ms")
    
    service = EntriesService()
    
    # Priority: start/end > hours > count
    if start is not None and end is not None:
        # Convert ISO strings or Unix timestamps to Unix timestamps (ms)
        try:
            # Try parsing as Unix timestamp first (numeric string)
            start_ms = int(start) if start.isdigit() else None
            end_ms = int(end) if end.isdigit() else None
            
            # If not numeric, try parsing as ISO string
            if start_ms is None:
                from datetime import datetime
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                start_ms = int(start_dt.timestamp() * 1000)
            if end_ms is None:
                from datetime import datetime
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                end_ms = int(end_dt.timestamp() * 1000)
            
            result = await service.get_entries_by_timestamp_range(tenant_id, start_ms, end_ms)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid timestamp format: {str(e)}")
    elif hours is not None:
        # Time-based filtering
        result = await service.get_entries_by_time_range(tenant_id, hours)
    else:
        # Fallback to count-based
        result = await service.get_entries(tenant_id, count or 10)
    
    request_total = time.time()
    print(f"[TIMING] API: Total request time {(request_total - request_start)*1000:.2f}ms")
    
    return result

@router.get("/entries-with-events", status_code=200)
async def get_entries_with_events(
    start: str,  # ISO timestamp or Unix timestamp (ms)
    end: str,    # ISO timestamp or Unix timestamp (ms)
    api_secret: Optional[str] = Header(None, alias="api-secret"),
    request: Request = None,
    db = Depends(get_mongo_db)
):
    """
    Fetches both CGM entries and events for the authenticated user's tenant in the specified time range.
    """
    
    tenant_id = None

    # 1. Try API key first
    if api_secret:
        # We need the request parameter for this
        if request is None:
             raise HTTPException(status_code=400, detail="Request object required for auth")
        tenant_id = get_tenant_from_api_key(request, api_secret)

    # 2. Check Authorization header (JWT)
    if not tenant_id and request:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from jose import jwt
                from app.core.config import settings
                from app.repositories.user import UserRepository
                
                token = auth_header.replace("Bearer ", "")
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = int(payload.get("sub"))
                
                repo = UserRepository()
                tenant_id = repo.get_tenant_for_user(user_id)
                if tenant_id:
                    tenant_id = str(tenant_id)
            except Exception:
                pass
        
    # 3. Subdomain fallback
    if not tenant_id and request:
        tenant_id = get_tenant_from_subdomain(request)
        
    if not tenant_id:
         raise HTTPException(status_code=401, detail="Authentication required")
         
    try:
        # Parse timestamps
        start_ms = int(start) if start.isdigit() else None
        end_ms = int(end) if end.isdigit() else None
        
        if start_ms is None:
            from datetime import datetime
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            start_ms = int(start_dt.timestamp() * 1000)
        if end_ms is None:
            from datetime import datetime
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            end_ms = int(end_dt.timestamp() * 1000)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp format: {str(e)}")

    import asyncio
    from app.repositories.event import EventRepository
    
    entries_service = EntriesService()
    # Need to manually get db dependency here properly by using FastAPI dependencies normally
    # But for a quick fix in function body we will get it from request state or rely on Depends wrapper
    # We will let FastApi inject `db`
    event_repo = EventRepository(db)
    
    # Run both queries concurrently
    try:
        entries_task = asyncio.create_task(
            entries_service.get_entries_by_timestamp_range(tenant_id, start_ms, end_ms)
        )
        events_task = asyncio.create_task(
            event_repo.get_multi_by_tenant(tenant_id, limit=1000, start_date=start_ms, end_date=end_ms)
        )
        
        entries, events = await asyncio.gather(entries_task, events_task)
        
        return {
            "entries": entries,
            "events": events
        }
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Failed to fetch combined data: {str(e)}")

@router.get("/entries/current", status_code=200)
@router.get("/entries/current.json", status_code=200)
async def get_current_entry(
    api_secret: Optional[str] = Header(None, alias="api-secret"),
    request: Request = None
):
    """
    Returns the most recent entry in TSV format (tab-separated values).
    Original OneTwenty API endpoint for uploaders to check last entry.
    Format: dateString \t date \t sgv \t direction \t device
    """
    from fastapi.responses import PlainTextResponse
    
    tenant_id = None

    # 1. Try API key first
    if api_secret:
        tenant_id = get_tenant_from_api_key(request, api_secret)

    # 2. If no API key, check Authorization header (JWT)
    if not tenant_id:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from jose import jwt
                from app.core.config import settings
                from app.repositories.user import UserRepository
                
                token = auth_header.replace("Bearer ", "")
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = int(payload.get("sub"))
                
                repo = UserRepository()
                tenant_id = repo.get_tenant_for_user(user_id)
                if tenant_id:
                    tenant_id = str(tenant_id)
            except Exception as e:
                print(f"JWT auth failed: {e}")  # Debug logging
                pass
        
    # 3. If still no tenant, try Subdomain (Public Read-Only)
    if not tenant_id:
        from app.api.deps import get_tenant_from_subdomain
        tenant_id = get_tenant_from_subdomain(request)
        
    if not tenant_id:
         raise HTTPException(status_code=401, detail="Authentication required")
    
    service = EntriesService()
    entries = await service.get_entries(tenant_id, count=1)
    
    if not entries:
        raise HTTPException(status_code=404, detail="No entries found")
    
    entry = entries[0]
    
    # Format as TSV: dateString \t date \t sgv \t direction \t device
    dateString = entry.get('dateString', '')
    date = entry.get('date', '')
    sgv = entry.get('sgv', '')
    direction = entry.get('direction', '')
    device = entry.get('device', '')
    
    # Wrap strings in quotes like original OneTwenty
    tsv_line = f'"{dateString}"\t{date}\t{sgv}\t"{direction}"\t"{device}"\n'
    
    return PlainTextResponse(content=tsv_line, media_type="text/plain; charset=utf-8")

