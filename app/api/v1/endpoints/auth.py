from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.auth import UserCreate, UserLogin, Token, UserUpdateDetails
from app.services.auth import AuthService
from app.core import security
from jose import jwt, JWTError
from app.core.config import settings
from fastapi.security import OAuth2PasswordBearer

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        return int(user_id)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


@router.post("/signup", response_model=Token)
def signup(user_in: UserCreate):
    """
    Register a new user. Returns tokens + user profile immediately.

    All onboarding data goes into `additional_data` (flexible JSONB):
    ```json
    {
      "email": "user@example.com",
      "password": "securepass",
      "name": "Ayush",
      "additional_data": {
        "goals": ["manage_glucose", "reduce_stress"],
        "diabetes_type": "type1",
        "units": "mg/dl",
        "onboarding_completed": true
      }
    }
    ```
    """
    service = AuthService()
    result = service.signup(user_in)
    return Token(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type="bearer",
        user=result["profile"],
    )


@router.post("/login", response_model=Token)
def login(login_in: UserLogin):
    """
    Login with email + password.
    Returns tokens and full user profile (name, additional_data, tenant_slug).
    """
    service = AuthService()
    return service.login(login_in)


@router.post("/refresh-token", response_model=Token)
def refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Invalid token type")
        user_id = payload.get("sub")
        new_access = security.create_access_token(subject=user_id)
        return Token(
            access_token=new_access,
            refresh_token=refresh_token,
            token_type="bearer"
        )
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")


@router.get("/profile")
def get_profile(user_id: int = Depends(get_current_user_id)):
    """Returns the current user's profile including tenant slug and additional_data."""
    from app.db.session import get_db_connection

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT u.public_id, u.email, u.name, u.dob, u.additional_data,
                          t.slug, t.name as tenant_name
                   FROM users u
                   JOIN tenant_users tu ON tu.user_id = u.id
                   JOIN tenants t ON t.id = tu.tenant_id
                   WHERE u.id = %s
                   LIMIT 1""",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")

            return {
                "user_id": row[0],
                "email": row[1],
                "name": row[2],
                "dob": row[3],
                "additional_data": row[4] or {},
                "tenant_slug": row[5],
                "tenant_name": row[6],
                "subdomain_url": f"https://{row[5]}.onetwenty.dev",
            }
    finally:
        conn.close()


@router.post("/api-secret")
def get_api_secret(user_id: int = Depends(get_current_user_id)):
    """Returns the existing API secret for the user's tenant, or creates one."""
    service = AuthService()
    return {"api_secret": service.get_or_create_api_key(user_id)}


@router.post("/reset-api-secret")
def reset_api_secret(user_id: int = Depends(get_current_user_id)):
    """Revokes the old API Secret and generates a new one."""
    service = AuthService()
@router.post("/details")
def update_details(
    details: UserUpdateDetails, 
    user_id: int = Depends(get_current_user_id)
):
    """
    Onboarding/Profile Update API.
    Captures dob, name, diabetes_type, insulin_types, and any other additional_data.
    """
    service = AuthService()
    success = service.update_details(user_id, details)
    if not success:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"status": "success", "message": "Profile updated"}
