from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ClockConfigBase(BaseModel):
    clock_id: str = Field(..., description="Alphanumeric unique identifier for the clock")
    wifi_name: Optional[str] = None
    wifi_password: Optional[str] = None
    user_subdomain_url: Optional[str] = None

class ClockConfigCreate(ClockConfigBase):
    pass

class ClockConfigUpdate(BaseModel):
    """Used for PUT /clock-config. clock_id identifies the record; subdomain is derived from JWT."""
    clock_id: str = Field(..., description="Clock to update")
    wifi_name: Optional[str] = None
    wifi_password: Optional[str] = None

class ClockConfigResponse(BaseModel):
    id: int
    clock_id: str
    wifi_name: Optional[str] = None
    wifi_password: Optional[str] = None
    user_subdomain_url: Optional[str] = None
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ClockAssignment(BaseModel):
    """Used for POST /assign-clock. subdomain is derived from the JWT — not accepted as input."""
    clock_id: str = Field(..., description="Clock to assign to the logged-in user's account")
