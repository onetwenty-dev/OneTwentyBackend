from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from app.repositories.user import UserRepository
from app.core import security
from app.schemas.auth import UserCreate, UserLogin, Token, UserProfile

class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()

    def _build_user_profile(self, user: Dict[str, Any], tenant_slug: Optional[str]) -> UserProfile:
        return UserProfile(
            user_id=user["public_id"],
            email=user["email"],
            name=user.get("name"),
            dob=user.get("dob"),
            additional_data=user.get("additional_data") or {},
            tenant_slug=tenant_slug,
        )

    def signup(self, user_in: UserCreate) -> Dict[str, Any]:
        """
        Registers a new user + tenant.
        Returns tokens + profile immediately — no second login call needed.
        """
        if self.user_repo.get_by_email(user_in.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        hashed_password = security.get_password_hash(user_in.password)
        user = self.user_repo.create(
            email=user_in.email,
            hashed_password=hashed_password,
            name=user_in.name,
            role=user_in.role or "user",
            additional_data=user_in.additional_data or {},
        )

        access_token = security.create_access_token(subject=user["id"])
        refresh_token = security.create_refresh_token(subject=user["id"])
        profile = self._build_user_profile(user, tenant_slug=user.get("tenant_slug"))

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "profile": profile,
        }

    def login(self, login_in: UserLogin) -> Token:
        user = self.user_repo.get_by_email(login_in.user_id)
        if not user or not security.verify_password(login_in.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        tenant_id = self.user_repo.get_tenant_for_user(user["id"])
        tenant_slug = self.user_repo.get_tenant_slug(tenant_id) if tenant_id else None

        access_token = security.create_access_token(subject=user["id"])
        refresh_token = security.create_refresh_token(subject=user["id"])
        profile = self._build_user_profile(user, tenant_slug=tenant_slug)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=profile,
        )

    def get_or_create_api_key(self, user_id: int) -> str:
        tenant_id = self.user_repo.get_tenant_for_user(user_id)
        if not tenant_id:
            raise HTTPException(status_code=404, detail="User has no tenant")
        existing_key = self.user_repo.get_active_api_key(tenant_id)
        return existing_key or self.user_repo.create_api_key(tenant_id)

    def rotate_api_key(self, user_id: int) -> str:
        tenant_id = self.user_repo.get_tenant_for_user(user_id)
        if not tenant_id:
            raise HTTPException(status_code=404, detail="User has no tenant")
        self.user_repo.revoke_api_keys(tenant_id)
        return self.user_repo.create_api_key(tenant_id, description="Rotated Key")

    def update_details(self, user_id: int, details: Any) -> bool:
        # Extract direct fields
        name = details.name
        dob = details.dob
        
        # Extract additional_data updates
        additional_updates = details.additional_data or {}
        if details.diabetes_type:
            additional_updates["diabetes_type"] = details.diabetes_type
        if details.insulin_types:
            additional_updates["insulin_types"] = details.insulin_types
            
        return self.user_repo.update_user_profile(
            user_id=user_id,
            name=name,
            dob=dob,
            additional_data_updates=additional_updates
        )
