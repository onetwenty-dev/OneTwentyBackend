"""
Appointments API endpoints.

Routes (all require JWT — doctor-scoped):
  GET    /appointments              — list appointments (filter: upcoming/past/all)
  POST   /appointments              — schedule a new appointment
  GET    /appointments/{id}         — get a single appointment
  PUT    /appointments/{id}         — update appointment details/status
  DELETE /appointments/{id}         — cancel/delete an appointment
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from app.api.deps import get_current_user_id
from app.repositories.appointment import AppointmentRepository
from app.repositories.doctor import DoctorRepository
from app.repositories.user import UserRepository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentOut
from app.core.logging import logger

router = APIRouter()


def _require_doctor(user_id: int):
    """Raise 403 if the caller is not a doctor."""
    repo = UserRepository()
    user = repo.get_by_id(user_id)
    if not user or (user.get("role") != "doctor" and user.get("additional_data", {}).get("role") != "doctor"):
        raise HTTPException(status_code=403, detail="Only doctors can manage appointments")


@router.get("", response_model=List[AppointmentOut])
def list_appointments(
    filter: Optional[str] = Query(default=None, description="'upcoming', 'past', or omit for all"),
    user_id: int = Depends(get_current_user_id),
):
    """
    List all appointments for the logged-in doctor.
    - `filter=upcoming` → only future/scheduled appointments
    - `filter=past` → only past appointments
    - (no filter) → all appointments
    """
    _require_doctor(user_id)
    repo = AppointmentRepository()
    return repo.get_for_doctor(user_id, filter_status=filter)


@router.post("", response_model=AppointmentOut, status_code=201)
def create_appointment(
    body: AppointmentCreate,
    user_id: int = Depends(get_current_user_id),
):
    """
    Schedule a new appointment.
    The patient must already be connected to this doctor.
    """
    _require_doctor(user_id)

    # Verify patient is linked to this doctor
    doctor_repo = DoctorRepository()
    if not doctor_repo.is_doctor_assigned_to_patient(user_id, body.patient_id):
        raise HTTPException(
            status_code=400,
            detail="Patient is not connected to you. Ask them to use your invite code first."
        )

    repo = AppointmentRepository()
    appt = repo.create(user_id, body.model_dump())

    logger.info(
        "Appointment created",
        extra={"extra_data": {"doctor_id": user_id, "patient_id": body.patient_id, "scheduled_at": str(body.scheduled_at)}},
    )
    return appt


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Get a single appointment by ID."""
    _require_doctor(user_id)
    repo = AppointmentRepository()
    appt = repo.get_by_id(appointment_id, user_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appt


@router.put("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: int,
    body: AppointmentUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """
    Update appointment time, type, notes, or status.
    Status values: 'scheduled', 'completed', 'cancelled'
    """
    _require_doctor(user_id)
    repo = AppointmentRepository()
    appt = repo.update(appointment_id, user_id, body.model_dump(exclude_none=True))
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appt


@router.delete("/{appointment_id}")
def delete_appointment(
    appointment_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Cancel/delete an appointment."""
    _require_doctor(user_id)
    repo = AppointmentRepository()
    deleted = repo.delete(appointment_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"status": "ok", "message": "Appointment deleted"}
