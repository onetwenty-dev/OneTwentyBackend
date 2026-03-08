"""
Doctor API endpoints.

Routes (all require JWT):
  POST   /doctor/onboard                        — first-time profile setup
  GET    /doctor/profile                        — get own profile
  PUT    /doctor/profile                        — update own profile
  POST   /doctor/invite                         — generate patient invite code
  GET    /doctor/patients                       — list all patients with live glucose
  GET    /doctor/patients/{patient_id}          — patient profile detail
  GET    /doctor/patients/{patient_id}/current  — patient's current glucose
  GET    /doctor/patients/{patient_id}/entries  — patient's glucose history
  GET    /doctor/patients/{patient_id}/events   — patient's events/treatments
  DELETE /doctor/patients/{patient_id}          — remove patient from list
  GET    /doctor/overview                       — dashboard stats
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from app.api.deps import get_current_user_id, get_mongo_db
from app.repositories.doctor import DoctorRepository
from app.repositories.user import UserRepository
from app.repositories.entries import EntriesRepository
from app.repositories.event import EventRepository
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.schemas.doctor import (
    DoctorOnboarding,
    DoctorProfileUpdate,
    DoctorProfileOut,
    InviteCodeOut,
    PatientListItem,
    PatientDetail,
)
from app.core.logging import logger

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_doctor(user_id: int) -> dict:
    """Raise 403 if the caller is not a doctor. Returns user dict."""
    repo = UserRepository()
    user = repo.get_by_id(user_id)
    if not user or user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can access this endpoint")
    return user


# ---------------------------------------------------------------------------
# Doctor Profile
# ---------------------------------------------------------------------------

@router.post("/onboard", response_model=DoctorProfileOut)
def doctor_onboard(
    body: DoctorOnboarding,
    user_id: int = Depends(get_current_user_id),
):
    """
    First-time doctor onboarding.
    Sets specialty, license number, clinic info, etc.
    The user account must have role='doctor' (set during signup via additional_data or admin).
    """
    _require_doctor(user_id)
    repo = DoctorRepository()
    profile = repo.upsert_profile(user_id, body.model_dump())

    # Enrich with user info
    user_repo = UserRepository()
    user = user_repo.get_by_id(user_id)
    profile["name"] = user.get("name")
    profile["email"] = user.get("email")
    return profile


@router.get("/profile", response_model=DoctorProfileOut)
def get_doctor_profile(user_id: int = Depends(get_current_user_id)):
    """Get doctor's own profile."""
    _require_doctor(user_id)
    repo = DoctorRepository()
    profile = repo.get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return profile


@router.put("/profile", response_model=DoctorProfileOut)
def update_doctor_profile(
    body: DoctorProfileUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Update doctor profile fields."""
    _require_doctor(user_id)

    # Update name on users table if provided
    if body.name is not None:
        user_repo = UserRepository()
        user_repo.update_user_profile(user_id, name=body.name)

    repo = DoctorRepository()
    data = body.model_dump(exclude={"name"}, exclude_none=True)
    profile = repo.upsert_profile(user_id, data)

    user_repo = UserRepository()
    user = user_repo.get_by_id(user_id)
    profile["name"] = user.get("name")
    profile["email"] = user.get("email")
    return profile


# ---------------------------------------------------------------------------
# Invite Codes
# ---------------------------------------------------------------------------

@router.post("/invite", response_model=InviteCodeOut)
def create_invite(user_id: int = Depends(get_current_user_id)):
    """
    Generate a 6-char invite code (24h TTL).
    Share with patient so they can connect via POST /patient/connect.
    """
    _require_doctor(user_id)
    repo = DoctorRepository()
    invite = repo.create_invite(user_id)
    return InviteCodeOut(
        code=invite["code"],
        expires_at=invite["expires_at"],
        message=f"Share code '{invite['code']}' with your patient. Valid for 24 hours.",
    )


# ---------------------------------------------------------------------------
# Patient Management
# ---------------------------------------------------------------------------

@router.get("/patients", response_model=List[PatientListItem])
async def list_patients(user_id: int = Depends(get_current_user_id)):
    """
    List all patients assigned to this doctor.
    Enriches each patient with their latest CGM reading from MongoDB.
    """
    _require_doctor(user_id)
    doctor_repo = DoctorRepository()
    patients = doctor_repo.get_patients_for_doctor(user_id)

    entries_repo = EntriesRepository()
    result = []
    for p in patients:
        item = PatientListItem(
            id=p["id"],
            name=p["name"],
            email=p["email"],
            tenant_id=p["tenant_id"],
            tenant_slug=p["tenant_slug"],
            granted_at=p["granted_at"],
        )
        # Fetch latest glucose if tenant_id is available
        if p["tenant_id"]:
            try:
                entry = await entries_repo.get_latest_sgv(p["tenant_id"])
                if entry:
                    item.current_sgv = entry.get("sgv")
                    item.current_trend = entry.get("direction")
                    item.current_date = entry.get("date")
            except Exception:
                pass
        result.append(item)
    return result


@router.get("/patients/{patient_id}", response_model=PatientDetail)
def get_patient_detail(
    patient_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Get full profile of a specific patient."""
    _require_doctor(user_id)
    repo = DoctorRepository()
    patient = repo.get_patient_detail(user_id, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found or not assigned to you")
    return patient


@router.get("/patients/{patient_id}/current")
async def get_patient_current_glucose(
    patient_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """
    Get the current (latest) glucose reading for a patient.
    Returns same shape as the Nightscout /api/v1/entries/current endpoint.
    """
    _require_doctor(user_id)
    repo = DoctorRepository()
    patient = repo.get_patient_detail(user_id, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found or not assigned to you")

    if not patient["tenant_id"]:
        raise HTTPException(status_code=404, detail="Patient has no CGM data tenant")

    entries_repo = EntriesRepository()
    entry = await entries_repo.get_latest_sgv(patient["tenant_id"])
    if not entry:
        return []
    return [entry]


@router.get("/patients/{patient_id}/entries")
async def get_patient_entries(
    patient_id: int,
    count: int = Query(default=10, ge=1, le=10000),
    user_id: int = Depends(get_current_user_id),
):
    """Get glucose history entries for a patient."""
    _require_doctor(user_id)
    repo = DoctorRepository()
    patient = repo.get_patient_detail(user_id, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found or not assigned to you")

    if not patient["tenant_id"]:
        return []

    entries_repo = EntriesRepository()
    entries = await entries_repo.get_many(patient["tenant_id"], limit=count)
    return entries


@router.get("/patients/{patient_id}/events")
async def get_patient_events(
    patient_id: int,
    count: int = Query(default=20, ge=1, le=1000),
    user_id: int = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """Get treatments/events for a patient."""
    _require_doctor(user_id)
    repo = DoctorRepository()
    patient = repo.get_patient_detail(user_id, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found or not assigned to you")

    if not patient["tenant_id"]:
        return []

    event_repo = EventRepository(db)
    events = await event_repo.get_multi_by_tenant(patient["tenant_id"], limit=count)
    return events


@router.delete("/patients/{patient_id}")
def remove_patient(
    patient_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Remove a patient from the doctor's list."""
    _require_doctor(user_id)
    repo = DoctorRepository()
    removed = repo.revoke_access(user_id, patient_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Patient not found in your list")
    logger.info("Doctor removed patient", extra={"extra_data": {"doctor_id": user_id, "patient_id": patient_id}})
    return {"status": "ok", "message": "Patient removed successfully"}


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@router.get("/overview")
def get_doctor_overview(user_id: int = Depends(get_current_user_id)):
    """
    Dashboard overview stats:
    - total_patients
    - upcoming_appointments
    (alerts_active and avg_tir require CGM data aggregation — returned as 0 for now)
    """
    _require_doctor(user_id)
    repo = DoctorRepository()
    stats = repo.get_overview_stats(user_id)
    return {
        "total_patients": stats["total_patients"],
        "alerts_active": 0,          # Future: aggregate from CGM anomaly detection
        "avg_time_in_range": None,   # Future: aggregate across all patient tenants
        "upcoming_appointments": stats["upcoming_appointments"],
    }
