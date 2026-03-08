from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DoctorOnboarding(BaseModel):
    """Used for POST /doctor/onboard — first-time profile creation."""
    specialty: Optional[str] = None
    license_number: Optional[str] = None
    clinic_name: Optional[str] = None
    clinic_address: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None


class DoctorProfileUpdate(BaseModel):
    """Used for PUT /doctor/profile — partial update."""
    specialty: Optional[str] = None
    license_number: Optional[str] = None
    clinic_name: Optional[str] = None
    clinic_address: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    name: Optional[str] = None  # also updates users.name


class DoctorProfileOut(BaseModel):
    """Full doctor profile response."""
    user_id: int
    name: Optional[str]
    email: str
    specialty: Optional[str]
    license_number: Optional[str]
    clinic_name: Optional[str]
    clinic_address: Optional[str]
    phone: Optional[str]
    bio: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class InviteCodeOut(BaseModel):
    """Response for POST /doctor/invite."""
    code: str
    expires_at: datetime
    message: str


class ConnectRequest(BaseModel):
    """Patient submits this to connect to a doctor."""
    code: str = Field(..., min_length=6, max_length=8)


class PatientListItem(BaseModel):
    """One row in the doctor's patient list."""
    id: int
    name: Optional[str]
    email: str
    tenant_id: Optional[str]
    tenant_slug: Optional[str]
    granted_at: Optional[datetime]
    # Live CGM data (may be None if no data yet)
    current_sgv: Optional[int] = None
    current_trend: Optional[str] = None
    current_date: Optional[int] = None   # epoch ms
    time_in_range: Optional[float] = None  # TIR percentage


class PatientDetail(BaseModel):
    """Full patient profile for /doctor/patients/{id}."""
    id: int
    name: Optional[str]
    email: str
    tenant_id: Optional[str]
    tenant_slug: Optional[str]
    granted_at: Optional[datetime]
    additional_data: Optional[dict] = {}
    dob: Optional[str] = None
