from fastapi import Header, HTTPException, Depends, status, Request
from app.db.session import get_db_connection
from typing import Generator, Optional
from app.core import security
from app.core.security import verify_api_secret
from app.api.v1.endpoints.auth import get_current_user_id
from app.repositories.user import UserRepository

def get_tenant_from_api_key(
    request: Request,
    api_secret: str = Header(..., alias="api-secret")
):
    """
    Legacy Auth: Resolves tenant via API Key in header.
    Used by: xDrip, Loop, Uploader devices.
    
    Supports both plain text and SHA-1 hashed secrets for backward compatibility
    with original OneTwenty clients.
    
    OPTIMIZATION: Tries to identify tenant from subdomain first to avoid 
    iterating through all API keys in the database.
    This also restricts the API key to match the subdomain tenant, preventing cross-tenant access.
    """
    
    # Extract slug from host
    host = request.headers.get("host", "")
    slug = None
    if host:
        parts = host.split(".")
        if len(parts) >= 2:
            candidate = parts[0]
            # Filter out common prefixes/reserved words if necessary
            if candidate not in ["api", "app", "backend"]:
                slug = candidate

    conn = get_db_connection()
    try:
        # 1. If we have a subdomain, check ONLY that tenant's keys
        if slug:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ak.tenant_id, ak.key_value 
                    FROM api_keys ak
                    JOIN tenants t ON t.id = ak.tenant_id
                    WHERE t.slug = %s AND t.is_active = TRUE AND ak.is_active = TRUE
                    """, 
                    (slug,)
                )
                rows = cursor.fetchall()
                
                # Check provided secret against stored secrets for this tenant
                for row in rows:
                    tenant_id, stored_secret = row
                    if verify_api_secret(api_secret, stored_secret):
                        return str(tenant_id)
                
                # If we are on a specific subdomain, we strict fail if auth doesn't match
                # This prevents "User A's key working on User B's subdomain"
                raise HTTPException(status_code=401, detail="Invalid API Secret for this domain")

        # 2. Fallback: Check ALL active keys (Only for IP access or unknown domains)
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT tenant_id, key_value FROM api_keys WHERE is_active = TRUE"
            )
            rows = cursor.fetchall()
            
            if not rows:
                raise HTTPException(status_code=401, detail="Invalid API Secret")
            
            for row in rows:
                tenant_id, stored_secret = row
                if verify_api_secret(api_secret, stored_secret):
                    return str(tenant_id)
            
            raise HTTPException(status_code=401, detail="Invalid API Secret")
            
    except Exception as e:
         if isinstance(e, HTTPException):
             raise e
         raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

def get_tenant_from_jwt(user_id: int = Depends(get_current_user_id)) -> str:
    """
    Dashboard Auth: Resolves tenant via JWT (User ID).
    Used by: React/EJS Dashboard.
    """
    repo = UserRepository()
    tenant_id = repo.get_tenant_for_user(user_id)
    if not tenant_id:
        raise HTTPException(status_code=404, detail="User has no tenant")
    return str(tenant_id)

# For backward compatibility / alias
get_current_tenant = get_tenant_from_api_key

def get_tenant_from_subdomain(request: Request = None) -> Optional[str]:
    """
    Resolves tenant via Subdomain (e.g. slug.domain.com).
    """
    if not request:
        return None
        
    host = request.headers.get("host", "")
    if not host:
        return None
        
    # Extract subdomain
    # Logic: assume <slug>.domain.com or <slug>.localhost
    # If using IP or localhost without subdomain, return None
    
    parts = host.split(".")
    if len(parts) < 2: # e.g. localhost or 127.0.0.1
        return None
        
    # Check against known domains? or just take the first part?
    # For now, take the first part as slug if it's not 'www' or 'api'
    slug = parts[0]
    
    # Ignore common prefixes if needed, but 'slug' should be unique
    if slug in ["www", "api", "app", "OneTwenty-saas"]:
        return None

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM tenants WHERE slug = %s AND is_active = TRUE LIMIT 1", 
                (slug,)
            )
            row = cursor.fetchone()
            if row:
                return str(row[0])
            return None
    except Exception:
        return None
    finally:
        conn.close()

from app.core.config import settings

def get_current_tenant_from_api_secret_or_jwt(
    request: Request,
    api_secret: Optional[str] = Header(None, alias="api-secret")
) -> str:
    tenant_id = None
    target_tenant_id = get_tenant_from_subdomain(request)
    
    if api_secret:
        try:
            tenant_id = get_tenant_from_api_key(request, api_secret)
        except Exception:
            pass
            
    if not tenant_id:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from jose import jwt
                from app.repositories.user import UserRepository
                token = auth_header.replace("Bearer ", "")
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = int(payload.get("sub"))
                repo = UserRepository()
                user_tenant_id = repo.get_tenant_for_user(user_id)
                
                if target_tenant_id and str(target_tenant_id) != str(user_tenant_id):
                    # Cross-tenant check for doctors
                    conn = get_db_connection()
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("SELECT role, additional_data FROM users WHERE id = %s", (user_id,))
                            row = cursor.fetchone()
                            if row:
                                role, add_data = row[0], row[1] or {}
                                actual_role = "doctor" if role == "doctor" or add_data.get("role") == "doctor" else role
                                
                                if actual_role == "doctor":
                                    cursor.execute("SELECT user_id FROM tenant_users WHERE tenant_id = %s AND role = 'owner' LIMIT 1", (target_tenant_id,))
                                    owner_row = cursor.fetchone()
                                    if owner_row:
                                        patient_id = owner_row[0]
                                        cursor.execute("SELECT 1 FROM doctor_patients WHERE doctor_id = %s AND patient_id = %s", (user_id, patient_id))
                                        if cursor.fetchone():
                                            tenant_id = str(target_tenant_id)
                    finally:
                        conn.close()
                    
                    if not tenant_id:
                        raise HTTPException(status_code=403, detail="Not authorized to access this tenant")
                else:
                    tenant_id = str(user_tenant_id) if user_tenant_id else None
            except HTTPException as e:
                raise e
            except Exception:
                pass
                
    if not tenant_id and getattr(request, "method", "") == "GET" and target_tenant_id:
        # Fallback for public dashboards (temporary/legacy behavior)
        tenant_id = target_tenant_id
        
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    return tenant_id

def get_mongo_db():
    from app.db.mongo import db
    return db.get_db()

