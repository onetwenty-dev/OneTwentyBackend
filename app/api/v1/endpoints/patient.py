"""
Patient-side API endpoints.

Routes (all require JWT for the patient):
  POST   /patient/connect           — patient submits an invite code to link to a doctor
  GET    /patient/my-doctors        — patient sees which doctors have access
  DELETE /patient/revoke/{doctor_id} — patient revokes a doctor's access
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.api.deps import get_current_user_id
from app.repositories.doctor import DoctorRepository
from app.schemas.doctor import ConnectRequest
from app.core.logging import logger

router = APIRouter()


@router.post("/connect")
def connect_to_doctor(
    body: ConnectRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Patient submits a 6-char invite code received from their doctor.
    On success, the doctor gains read access to the patient's CGM data.
    """
    repo = DoctorRepository()
    result = repo.claim_invite(body.code.upper(), user_id)
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired invite code. Please ask your doctor for a new one."
        )

    logger.info(
        "Patient connected to doctor",
        extra={"extra_data": {"patient_id": user_id, "doctor_id": result["doctor_id"]}},
    )
    return {"status": "ok", "message": "Successfully connected to your doctor."}


@router.get("/my-doctors")
def get_my_doctors(user_id: int = Depends(get_current_user_id)):
    """
    Patient sees all doctors who currently have access to their data.
    Returns doctor name, specialty, clinic, and when access was granted.
    """
    repo = DoctorRepository()
    doctors = repo.get_doctors_for_patient(user_id)
    return doctors


@router.delete("/revoke/{doctor_id}")
def revoke_doctor_access(
    doctor_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """
    Patient revokes a specific doctor's access to their data.
    The doctor_patients row is deleted permanently.
    """
    repo = DoctorRepository()
    removed = repo.revoke_access(doctor_id, user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Doctor not found in your connected list")

    logger.info(
        "Patient revoked doctor access",
        extra={"extra_data": {"patient_id": user_id, "doctor_id": doctor_id}},
    )
    return {"status": "ok", "message": "Doctor access revoked successfully."}
