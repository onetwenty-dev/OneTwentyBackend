from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

class EventBase(BaseModel):
    eventType: str = Field(description="Type of event (e.g., Meal Bolus, Correction Bolus, Exercise, Note, Temp Basal, Profile Switch)")
    dateString: Optional[str] = Field(None, description="ISO date string of the event time")
    date: Optional[int] = Field(None, description="Timestamp in milliseconds")
    created_at: Optional[str] = Field(None, description="ISO string of when the event was generated")
    enteredBy: Optional[str] = Field(default="OneTwenty", description="Who or what system entered the event")
    notes: Optional[str] = Field(None, description="General notes about the event")
    
    # Optional fields depending on the event type
    carbs: Optional[float] = Field(None, description="Grams of carbohydrates")
    insulin: Optional[float] = Field(None, description="Units of insulin")
    duration: Optional[float] = Field(None, description="Duration in minutes (e.g. for exercise or temp basal)")
    percent: Optional[float] = Field(None, description="Percentage of normal basal (e.g. for temp basal)")
    absolute: Optional[float] = Field(None, description="Absolute units/hr for temp basal")
    profile: Optional[str] = Field(None, description="Profile name if profile switch event")
    
    # Allow extra fields for OneTwenty compatibility
    class Config:
        extra = "allow"

class EventCreate(EventBase):
    pass

class EventUpdate(EventBase):
    eventType: Optional[str] = None

class EventInDB(EventBase):
    tenant_id: str
    _id: Any
