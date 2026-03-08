from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal, Any, Dict
from datetime import date

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    name: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(default="user", description="'user' for patients, 'doctor' for doctors")
    # All onboarding/personalization data goes here — flexible, app can send any fields
    additional_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    # Example additional_data contents:
    # {
    #   "goals": ["manage_glucose", "reduce_stress"],
    #   "diabetes_type": "type1",
    #   "units": "mg/dl",
    #   "onboarding_completed": true
    # }

class UserLogin(BaseModel):
    user_id: str  # Email or public_id
    password: str

class UserProfile(BaseModel):
    """Embedded in login/signup responses so the app has what it needs immediately."""
    user_id: str
    email: str
    name: Optional[str]
    dob: Optional[date] = None
    additional_data: Dict[str, Any]
    tenant_slug: Optional[str]

class UserUpdateDetails(BaseModel):
    name: Optional[str] = None
    dob: Optional[date] = None
    # Any other fields to be updated in additional_data
    diabetes_type: Optional[str] = None
    insulin_types: Optional[List[str]] = None
    additional_data: Optional[Dict[str, Any]] = None

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: Optional[UserProfile] = None  # Returned on login/signup

class TokenData(BaseModel):
    user_id: Optional[str] = None
