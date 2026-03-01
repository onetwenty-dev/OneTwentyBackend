from pydantic import BaseModel
from typing import Dict, Any, Optional

class TenantSettings(BaseModel):
    """
    OneTwenty tenant-specific settings.
    These replace environment variables in the SaaS model.
    """
    # Display
    title: str = "OneTwenty"
    units: str = "mg/dl"  # or "mmol"
    theme: str = "default"
    language: str = "en"
    
    # Alarms
    alarm_urgent_high: int = 260
    alarm_high: int = 180
    alarm_low: int = 70
    alarm_urgent_low: int = 55
    
    # Target Range
    bg_target_top: int = 180
    bg_target_bottom: int = 80
    
    # Plugins (enabled by default)
    enable: list[str] = [
        "careportal", "boluscalc", "food", "rawbg", "iob", "cob", 
        "bwp", "cage", "sage", "iage", "treatmentnotify", "basal", "bridge"
    ]
    
    # Additional settings can be stored in extra
    class Config:
        extra = "allow"

class TenantSettingsUpdate(BaseModel):
    """
    Schema for updating tenant settings.
    All fields are optional to allow partial updates.
    """
    title: Optional[str] = None
    units: Optional[str] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    alarm_urgent_high: Optional[int] = None
    alarm_high: Optional[int] = None
    alarm_low: Optional[int] = None
    alarm_urgent_low: Optional[int] = None
    bg_target_top: Optional[int] = None
    bg_target_bottom: Optional[int] = None
    enable: Optional[list[str]] = None
    
    class Config:
        extra = "allow"

DEFAULT_TENANT_SETTINGS = TenantSettings().dict()
