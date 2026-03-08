from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.clock import ClockConfigResponse, ClockConfigCreate, ClockConfigUpdate, ClockAssignment
from app.repositories.clock import ClockRepository
from app.repositories.user import UserRepository
from typing import Optional, List
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


def get_current_user_tenant(user_id: int = Depends(get_current_user_id)):
    """
    Resolves the logged-in user's tenant_id and tenant_slug from the DB.
    Returns a dict: {"tenant_id": int, "tenant_slug": str, "subdomain_url": str}
    """
    user_repo = UserRepository()
    tenant_id = user_repo.get_tenant_for_user(user_id)
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User has no associated tenant")
    tenant_slug = user_repo.get_tenant_slug(tenant_id)
    if not tenant_slug:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant slug not found")
    return {
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "subdomain_url": f"https://{tenant_slug}.onetwenty.dev",
    }


@router.get("/clock-config", response_model=ClockConfigResponse)
async def get_clock_config(clock_id: str, repo: ClockRepository = Depends()):
    """
    Fetch clock configuration by clock_id.
    """
    config = repo.get_by_clock_id(clock_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration for clock '{clock_id}' not found"
        )
    return config


@router.post("/clock-config", response_model=ClockConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_clock_config(config_in: ClockConfigCreate, repo: ClockRepository = Depends()):
    """
    Create a new clock configuration.
    """
    existing = repo.get_by_clock_id(config_in.clock_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuration for clock '{config_in.clock_id}' already exists. Use PUT to update."
        )
    return repo.create(
        clock_id=config_in.clock_id,
        wifi_name=config_in.wifi_name,
        wifi_password=config_in.wifi_password,
        user_subdomain_url=config_in.user_subdomain_url
    )


@router.put("/clock-config", response_model=ClockConfigResponse)
async def update_clock_config(
    config_in: ClockConfigUpdate,
    tenant: dict = Depends(get_current_user_tenant),
    repo: ClockRepository = Depends(),
):
    """
    Update an existing clock configuration for the logged-in user's tenant.
    The clock must already be assigned to this user's tenant (via tenant_id).
    JWT authentication required — the subdomain is derived from the token, not accepted as input.
    """
    clock_id = config_in.clock_id
    existing = repo.get_by_clock_id(clock_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clock '{clock_id}' not found"
        )

    # Ensure the clock belongs to this user's tenant
    if existing.get("tenant_id") != tenant["tenant_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This clock is not assigned to your account"
        )

    return repo.update(
        clock_id=clock_id,
        wifi_name=config_in.wifi_name,
        wifi_password=config_in.wifi_password,
    )


@router.post("/assign-clock", response_model=ClockConfigResponse)
async def assign_clock(
    assignment: ClockAssignment,
    tenant: dict = Depends(get_current_user_tenant),
    repo: ClockRepository = Depends(),
):
    """
    Assign a clock to the currently logged-in user's subdomain.
    JWT authentication required — the subdomain is derived from the token, not accepted as input.
    """
    config = repo.assign_to_tenant(
        clock_id=assignment.clock_id,
        tenant_id=tenant["tenant_id"],
        user_subdomain_url=tenant["subdomain_url"],
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clock '{assignment.clock_id}' not found"
        )
    return config


@router.get("/my-clocks", response_model=List[ClockConfigResponse])
async def get_my_clocks(
    tenant: dict = Depends(get_current_user_tenant),
    repo: ClockRepository = Depends(),
):
    """
    Returns all clocks assigned to the currently logged-in user's account.
    JWT authentication required.
    """
    return repo.get_by_tenant_id(tenant["tenant_id"])
