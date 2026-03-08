import asyncio
import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body, Header, Request, Query, File, UploadFile
from pydantic import BaseModel

from app.api.deps import get_current_tenant_from_api_secret_or_jwt, get_mongo_db
from app.services.ai_agent import AIAgentService
from app.repositories.chat import ChatRepository
from app.repositories.event import EventRepository
from app.repositories.document import DocumentRepository
from app.schemas.chat import ChatCreate
from app.schemas.event import EventCreate
from app.services.entries import EntriesService

router = APIRouter()

class TextChatRequest(BaseModel):
    message: str
    timezone_offset: int = 0  # In minutes, e.g., -330 for IST (+5:30)

async def fetch_health_context(db, tenant_id: str, message: str = "", timezone_offset: int = 0) -> str:
    """
    Always fetches and condenses recent bio-data (glucose + events).
    Adjusts lookback window if keywords like 'week' or 'month' are found.
    """
    now_ms = int(time.time() * 1000)
    
    # Dynamic lookback based on user intent
    lookback_hours = 24  # Default and fallback
    msg_lower = message.lower()
    requested_absolute = False
    
    import re
    import datetime
    
    # 1. Look for absolute time anchors: "since 11am", "from 10:30", etc.
    time_match = re.search(r'(?:since|from|after)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', msg_lower)
    
    if time_match:
        requested_absolute = True
        hr = int(time_match.group(1))
        mn = int(time_match.group(2)) if time_match.group(2) else 0
        p = time_match.group(3)
        
        if p == 'pm' and hr < 12: hr += 12
        if p == 'am' and hr == 12: hr = 0
        
        utc_now = datetime.datetime.fromtimestamp(now_ms / 1000, tz=datetime.timezone.utc)
        local_now = utc_now - datetime.timedelta(minutes=timezone_offset)
        anchor_local = local_now.replace(hour=hr, minute=mn, second=0, microsecond=0)
        
        if anchor_local > local_now:
            anchor_local -= datetime.timedelta(days=1)
            
        anchor_utc = anchor_local + datetime.timedelta(minutes=timezone_offset)
        start_ms = int(anchor_utc.timestamp() * 1000)
        # Update lookback_hours for the limit logic
        lookback_hours = (now_ms - start_ms) / (1000 * 60 * 60)
    else:
        # 2. Relative lookbacks
        hour_match = re.search(r'(?:last|past|for)\s+(\d+)\s+hour', msg_lower)
        day_match = re.search(r'(?:last|past|for)\s+(\d+)\s+day', msg_lower)
        
        if hour_match:
            lookback_hours = int(hour_match.group(1))
        elif day_match:
            lookback_hours = int(day_match.group(1)) * 24
        elif "week" in msg_lower:
            lookback_hours = 24 * 7
        elif "month" in msg_lower:
            lookback_hours = 24 * 30
        elif "yesterday" in msg_lower:
            lookback_hours = 24
        
        lookback_hours = min(max(1, lookback_hours), 24 * 30)
        start_ms = now_ms - (lookback_hours * 60 * 60 * 1000)
    
    entries_service = EntriesService()
    event_repo = EventRepository(db)
    
    # Run in parallel
    entries, events = await asyncio.gather(
        entries_service.get_entries_by_timestamp_range(tenant_id=tenant_id, start_ms=start_ms, end_ms=now_ms),
        event_repo.get_multi_by_tenant(tenant_id=tenant_id, start_date=start_ms, end_date=now_ms, limit=300 if lookback_hours > 48 else 100)
    )
    
    # FALLBACK LOGIC
    fallback_note = ""
    if not entries and not events and requested_absolute:
        # Try falling back to default 24h if the specific window was empty
        start_ms_fb = now_ms - (24 * 60 * 60 * 1000)
        entries, events = await asyncio.gather(
            entries_service.get_entries_by_timestamp_range(tenant_id=tenant_id, start_ms=start_ms_fb, end_ms=now_ms),
            event_repo.get_multi_by_tenant(tenant_id=tenant_id, start_date=start_ms_fb, end_date=now_ms, limit=100)
        )
        if entries or events:
            fallback_note = "NOTE: Requested window was empty. Showing last 24 hours instead."
    
    if not entries and not events:
        return ""
        
    condensed = AIAgentService.condense_data(entries, events, timezone_offset)
    return f"{fallback_note} {condensed}".strip()

async def fetch_document_context(db, tenant_id: str, message: str) -> str:
    """Fetches extracted text from the most recent blood reports if relevant."""
    keywords = ["report", "blood", "test", "result", "doctor", "lab", "document", "pdf", "what does it say"]
    if not any(k in message.lower() for k in keywords):
        return ""
    
    repo = DocumentRepository(db)
    docs = await repo.get_documents(tenant_id, limit=3)
    
    context = []
    for doc in docs:
        if doc.get("extracted_text"):
            context.append(f"Document: {doc['filename']}\nContent: {doc['extracted_text'][:1000]}...")
            
    return "\n---\n".join(context)

@router.post("/text")
async def chat_text(
    payload: TextChatRequest,
    tenant_id: str = Depends(get_current_tenant_from_api_secret_or_jwt),
    db = Depends(get_mongo_db)
):
    """
    Submits a text message to the AI Agent.
    """
    start_time = time.time()
    now_ms = int(start_time * 1000)
    
    health_context = await fetch_health_context(db, tenant_id, payload.message, payload.timezone_offset)
    doc_context = await fetch_document_context(db, tenant_id, payload.message)
    
    chat_repo = ChatRepository(db)
    chat_history = await chat_repo.get_multi_by_tenant(tenant_id=tenant_id, limit=10)
    # History is usually latest-first, we want oldest-first for the AI context
    chat_history.reverse()
    
    loop = asyncio.get_event_loop()
    try:
        bedrock_result = await loop.run_in_executor(
            None, 
            AIAgentService.process_bedrock_chat,
            payload.message,
            now_ms,
            health_context,
            doc_context,
            payload.timezone_offset,
            chat_history
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Processing failed: {str(e)}")
        
    extracted_events = bedrock_result.get("extracted_events", [])
    ai_response = bedrock_result.get("ai_response", "I could not generate a response.")
    
    # 2. Insert extracted events
    event_repo = EventRepository(db)
    inserted_event_ids = []
    
    for ev in extracted_events:
        try:
            ev_create = EventCreate(
                tenant_id=tenant_id,
                eventType=ev.get("eventType", "Note"),
                date=ev.get("date", now_ms),
                dateString=ev.get("dateString"),
                carbs=ev.get("carbs"),
                insulin=ev.get("insulin"),
                duration=ev.get("duration"),
                notes=ev.get("notes")
            )
            inserted_id_doc = await event_repo.create(tenant_id, ev_create)
            inserted_id = inserted_id_doc["_id"]
            inserted_event_ids.append(inserted_id)
        except Exception as e:
            print(f"Failed to log extracted event {ev}: {e}")

    # 3. Save the chat transaction to history
    chat_repo = ChatRepository(db)
    chat_log = ChatCreate(
        tenant_id=tenant_id,
        userMessage=payload.message,
        aiResponse=ai_response,
        date=now_ms
    )
    chat_id = await chat_repo.create(chat_log)
    
    return {
        "chat_id": chat_id,
        "ai_response": ai_response,
        "extracted_events": extracted_events,
        "inserted_event_count": len(inserted_event_ids)
    }

@router.get("/history")
async def get_chat_history(
    limit: int = 50,
    skip: int = 0,
    tenant_id: str = Depends(get_current_tenant_from_api_secret_or_jwt),
    db = Depends(get_mongo_db)
):
    chat_repo = ChatRepository(db)
    history = await chat_repo.get_multi_by_tenant(tenant_id=tenant_id, limit=limit, skip=skip)
    return history

from fastapi import UploadFile, File
from app.services.transcribe import TranscribeService

@router.post("/voice")
async def chat_voice(
    file: UploadFile = File(...),
    timezone_offset: int = Query(0),
    tenant_id: str = Depends(get_current_tenant_from_api_secret_or_jwt),
    db = Depends(get_mongo_db)
):
    """
    Submits a voice audio file to the AI Agent.
    1. Transcribes audio to text via AWS Transcribe
    2. Parses events via AI
    3. Saves events and chat log
    """
    start_time = time.time()
    now_ms = int(time.time() * 1000)
    file_bytes = await file.read()
    extension = file.filename.split('.')[-1] if '.' in file.filename else 'mp3'
    
    loop = asyncio.get_event_loop()
    try:
        # Transcribe directly asynchronously via HTTP2
        transcript_text = await TranscribeService.transcribe_audio_file(
            file_bytes,
            extension
        )
        
        if not transcript_text or not transcript_text.strip():
            return {
                "chat_id": None,
                "transcribed_text": "",
                "ai_response": "I couldn't hear anything in that audio. Could you please try speaking again?",
                "extracted_events": [],
                "inserted_event_count": 0
            }

        # Parse & Act
        chat_repo = ChatRepository(db)
        chat_history = await chat_repo.get_multi_by_tenant(tenant_id=tenant_id, limit=10)
        chat_history.reverse()

        health_context = await fetch_health_context(db, tenant_id, transcript_text, timezone_offset)
        doc_context = await fetch_document_context(db, tenant_id, transcript_text)
        bedrock_result = await loop.run_in_executor(
            None, 
            AIAgentService.process_bedrock_chat,
            transcript_text,
            now_ms,
            health_context,
            doc_context,
            timezone_offset,
            chat_history
        )
    except Exception as e:
        print(f"Voice Processing Error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice Processing failed: {str(e)}")
        
    extracted_events = bedrock_result.get("extracted_events", [])
    ai_response = bedrock_result.get("ai_response", "I could not generate a response.")
    
    # Insert extracted events
    event_repo = EventRepository(db)
    inserted_event_ids = []
    
    for ev in extracted_events:
        try:
            ev_create = EventCreate(
                tenant_id=tenant_id,
                eventType=ev.get("eventType", "Note"),
                date=ev.get("date", now_ms),
                dateString=ev.get("dateString"),
                carbs=ev.get("carbs"),
                insulin=ev.get("insulin"),
                duration=ev.get("duration"),
                notes=ev.get("notes")
            )
            inserted_id_doc = await event_repo.create(tenant_id, ev_create)
            inserted_id = inserted_id_doc["_id"]
            inserted_event_ids.append(inserted_id)
        except Exception as e:
            print(f"Failed to log extracted event {ev}: {e}")

    # Save the chat transaction to history
    chat_repo = ChatRepository(db)
    chat_log = ChatCreate(
        tenant_id=tenant_id,
        userMessage=transcript_text,
        aiResponse=ai_response,
        date=now_ms
    )
    chat_id = await chat_repo.create(chat_log)
    
    return {
        "chat_id": chat_id,
        "transcribed_text": transcript_text,
        "ai_response": ai_response,
        "extracted_events": extracted_events,
        "inserted_event_count": len(inserted_event_ids)
    }

