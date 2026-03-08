from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


AppointmentType = Literal["Follow-up", "Urgent", "Review", "Initial"]
AppointmentStatus = Literal["scheduled", "completed", "cancelled"]


class AppointmentCreate(BaseModel):
    patient_id: int
    scheduled_at: datetime
    duration_min: int = Field(default=30, ge=5, le=480)
    type: AppointmentType = "Follow-up"
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    duration_min: Optional[int] = Field(default=None, ge=5, le=480)
    type: Optional[AppointmentType] = None
    notes: Optional[str] = None
    status: Optional[AppointmentStatus] = None


class AppointmentOut(BaseModel):
    id: int
    doctor_id: int
    patient_id: int
    patient_name: Optional[str] = None
    patient_email: Optional[str] = None
    scheduled_at: datetime
    duration_min: int
    type: str
    notes: Optional[str]
    status: str
    created_at: datetime
