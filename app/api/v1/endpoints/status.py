"""
OneTwenty-compatible /status endpoint.

Content negotiation mirrors original OneTwenty lib/api/status.js res.format():
  Accept: application/json  (default)  → full JSON status object
  Accept: text/html         / .html    → <h1>STATUS OK</h1>
  Accept: image/png         / .png     → 302 redirect to shields.io badge (PNG)
  Accept: image/svg+xml     / .svg     → 302 redirect to shields.io badge (SVG)
  Accept: application/javascript / .js → this.serverSettings = {...};
  Accept: text/plain        / .txt     → STATUS OK

URL extensions (.json, .html, .png, .svg, .js, .txt) are handled via separate
route aliases and take precedence over the Accept header — matching the
wares.extensions() middleware behaviour in the original.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response

from app.api.deps import get_tenant_from_api_key, get_tenant_from_subdomain
from app.repositories.tenant import TenantRepository

router = APIRouter()

_BADGE_BASE = "http://img.shields.io/badge/OneTwenty-OK-green"


# ---------------------------------------------------------------------------
# Auth helper (same multi-strategy pattern as entries)
# ---------------------------------------------------------------------------

async def _resolve_tenant(request: Request, api_secret: Optional[str]) -> str:
    tenant_id: Optional[str] = None

    if api_secret:
        tenant_id = get_tenant_from_api_key(request, api_secret)

    if not tenant_id:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from jose import jwt
                from app.core.config import settings
                from app.repositories.user import UserRepository

                token = auth_header[7:]
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = int(payload.get("sub"))
                repo = UserRepository()
                tid = repo.get_tenant_for_user(user_id)
                tenant_id = str(tid) if tid else None
            except Exception:
                pass

    if not tenant_id:
        tenant_id = get_tenant_from_subdomain(request)

    if not tenant_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    return tenant_id


# ---------------------------------------------------------------------------
# Status payload builder
# ---------------------------------------------------------------------------

def _build_status_info(tenant_info: dict) -> dict:
    """Build the canonical status dict matching original OneTwenty's `info` object."""
    now = datetime.now(tz=timezone.utc)
    settings = tenant_info.get("settings", {})

    return {
        "status": "ok",
        "name": tenant_info.get("name", "OneTwenty"),
        "version": "15.0.0-saas",
        "serverTime": now.isoformat(),
        "serverTimeEpoch": int(now.timestamp() * 1000),
        "apiEnabled": True,
        "careportalEnabled": True,
        "boluscalcEnabled": True,
        "settings": settings,
        "extendedSettings": {
            "devicestatus": {"advanced": True}
        },
        # Convenience top-level fields used directly by the OneTwenty UI
        "units": settings.get("units", "mg/dl"),
        "enable": settings.get("enable", []),
        "thresholds": {
            "bg_high": settings.get("alarm_high", 180),
            "bg_target_top": settings.get("bg_target_top", 180),
            "bg_target_bottom": settings.get("bg_target_bottom", 80),
            "bg_low": settings.get("alarm_low", 70),
        },
    }


# ---------------------------------------------------------------------------
# Content-type dispatch helper
# ---------------------------------------------------------------------------

def _format_response(info: dict, fmt: str) -> Response:
    """
    Return the correct response type for `fmt`.
    `fmt` is one of: json, html, png, svg, js, text
    """
    if fmt == "html":
        return HTMLResponse(content="<h1>STATUS OK</h1>")
    if fmt == "png":
        return RedirectResponse(url=_BADGE_BASE + ".png", status_code=302)
    if fmt == "svg":
        return RedirectResponse(url=_BADGE_BASE + ".svg", status_code=302)
    if fmt == "js":
        body = "this.serverSettings = " + _json_dumps(info) + ";"
        return PlainTextResponse(content=body, media_type="application/javascript; charset=utf-8")
    if fmt == "text":
        return PlainTextResponse(content="STATUS OK", media_type="text/plain; charset=utf-8")
    # Default: JSON
    return JSONResponse(content=info)


def _json_dumps(obj) -> str:
    import json
    return json.dumps(obj, default=str)


def _accept_to_fmt(accept: str) -> str:
    """
    Parse the Accept header and return the format key.
    Follows the same priority as Express res.format().
    """
    a = accept.lower()
    if "text/html" in a:
        return "html"
    if "image/png" in a:
        return "png"
    if "image/svg" in a:
        return "svg"
    if "application/javascript" in a or "text/javascript" in a:
        return "js"
    if "text/plain" in a:
        return "text"
    # application/json or */* or anything else → JSON
    return "json"


# ---------------------------------------------------------------------------
# Routes — extension aliases take precedence over Accept header
# ---------------------------------------------------------------------------

async def _handle(request: Request, api_secret: Optional[str], forced_fmt: Optional[str] = None) -> Response:
    tenant_id = await _resolve_tenant(request, api_secret)

    repo = TenantRepository()
    tenant_info = repo.get_tenant_info(int(tenant_id))
    if not tenant_info:
        raise HTTPException(status_code=404, detail="Tenant not found")

    info = _build_status_info(tenant_info)

    # Extension routes force a format; otherwise negotiate from Accept header
    fmt = forced_fmt or _accept_to_fmt(request.headers.get("Accept", "application/json"))
    return _format_response(info, fmt)


@router.get("/status")
async def get_status(
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    """Status endpoint — honours Accept header for content negotiation."""
    return await _handle(request, api_secret)


@router.get("/status.json")
async def get_status_json(
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    return await _handle(request, api_secret, forced_fmt="json")


@router.get("/status.html")
async def get_status_html(
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    return await _handle(request, api_secret, forced_fmt="html")


@router.get("/status.png")
async def get_status_png(
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    return await _handle(request, api_secret, forced_fmt="png")


@router.get("/status.svg")
async def get_status_svg(
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    return await _handle(request, api_secret, forced_fmt="svg")


@router.get("/status.js")
async def get_status_js(
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    return await _handle(request, api_secret, forced_fmt="js")


@router.get("/status.txt")
async def get_status_txt(
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    return await _handle(request, api_secret, forced_fmt="text")


# ---------------------------------------------------------------------------
# PUT /settings  (unchanged)
# ---------------------------------------------------------------------------

@router.put("/settings")
async def update_settings(
    settings_update: dict,
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret"),
):
    """
    Update tenant settings. Accepts partial updates — only provided fields are merged.
    JWT auth required for writes.
    """
    from app.core.logging import logger

    # Writes require JWT — extract inline
    tenant_id: Optional[str] = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from jose import jwt
            from app.core.config import settings as app_settings
            from app.repositories.user import UserRepository

            token = auth_header[7:]
            payload = jwt.decode(token, app_settings.SECRET_KEY, algorithms=[app_settings.ALGORITHM])
            user_id = int(payload.get("sub"))
            repo = UserRepository()
            tid = repo.get_tenant_for_user(user_id)
            tenant_id = str(tid) if tid else None
        except Exception:
            pass

    if not tenant_id:
        raise HTTPException(status_code=401, detail="JWT required for settings update")

    repo = TenantRepository()
    current_settings = repo.get_settings(int(tenant_id))
    updated_settings = {**current_settings, **settings_update}
    repo.update_settings(int(tenant_id), updated_settings)

    logger.info(
        "Tenant settings updated",
        extra={"extra_data": {"tenant_id": tenant_id, "updated_fields": list(settings_update.keys())}}
    )

    return {
        "status": "ok",
        "message": "Settings updated successfully",
        "settings": updated_settings,
    }

