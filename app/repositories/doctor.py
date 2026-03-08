from app.db.session import get_db_connection
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import random
import string


def _generate_invite_code(length=6) -> str:
    """Generate a random uppercase alphanumeric code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


class DoctorRepository:
    def __init__(self):
        pass

    # -----------------------------------------------------------------------
    # Doctor Profile
    # -----------------------------------------------------------------------

    def upsert_profile(self, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update doctor profile. Returns full profile."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            fields = ["specialty", "license_number", "clinic_name", "clinic_address", "phone", "bio"]
            set_clauses = ", ".join(f"{f} = EXCLUDED.{f}" for f in fields)
            placeholders = ", ".join(["%s"] * len(fields))
            col_names = ", ".join(fields)
            values = [data.get(f) for f in fields]

            cursor.execute(
                f"""
                INSERT INTO doctor_profiles (user_id, {col_names})
                VALUES (%s, {placeholders})
                ON CONFLICT (user_id) DO UPDATE SET
                    {set_clauses},
                    updated_at = CURRENT_TIMESTAMP
                RETURNING user_id, specialty, license_number, clinic_name,
                          clinic_address, phone, bio, created_at, updated_at
                """,
                [user_id] + values,
            )
            row = cursor.fetchone()
            conn.commit()
            return {
                "user_id": row[0], "specialty": row[1], "license_number": row[2],
                "clinic_name": row[3], "clinic_address": row[4], "phone": row[5],
                "bio": row[6], "created_at": row[7], "updated_at": row[8],
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def get_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get doctor profile joined with users table."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT u.id, u.name, u.email,
                       dp.specialty, dp.license_number, dp.clinic_name,
                       dp.clinic_address, dp.phone, dp.bio,
                       dp.created_at, dp.updated_at
                FROM users u
                LEFT JOIN doctor_profiles dp ON dp.user_id = u.id
                WHERE u.id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "user_id": row[0], "name": row[1], "email": row[2],
                "specialty": row[3], "license_number": row[4], "clinic_name": row[5],
                "clinic_address": row[6], "phone": row[7], "bio": row[8],
                "created_at": row[9], "updated_at": row[10],
            }
        finally:
            cursor.close()
            conn.close()

    # -----------------------------------------------------------------------
    # Invite Codes
    # -----------------------------------------------------------------------

    def create_invite(self, doctor_id: int, ttl_hours: int = 24) -> Dict[str, Any]:
        """Generate a unique invite code for the doctor."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
            # Try a few times in case of collision
            for _ in range(5):
                code = _generate_invite_code()
                cursor.execute(
                    """
                    INSERT INTO patient_invites (doctor_id, code, expires_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (code) DO NOTHING
                    RETURNING id, code, expires_at
                    """,
                    (doctor_id, code, expires_at),
                )
                row = cursor.fetchone()
                if row:
                    conn.commit()
                    return {"id": row[0], "code": row[1], "expires_at": row[2]}
            raise ValueError("Could not generate unique code after 5 attempts")
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def claim_invite(self, code: str, patient_id: int) -> Optional[Dict[str, Any]]:
        """
        Patient claims an invite code.
        Returns doctor_id if successful, None if code is invalid/expired/used.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Fetch valid, unused, unexpired invite
            cursor.execute(
                """
                SELECT id, doctor_id FROM patient_invites
                WHERE code = %s
                  AND used_at IS NULL
                  AND expires_at > NOW()
                  AND patient_id IS NULL
                FOR UPDATE
                """,
                (code,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            invite_id, doctor_id = row

            # Mark used
            cursor.execute(
                "UPDATE patient_invites SET used_at = NOW(), patient_id = %s WHERE id = %s",
                (patient_id, invite_id),
            )

            # Create doctor_patients link
            cursor.execute(
                """
                INSERT INTO doctor_patients (doctor_id, patient_id)
                VALUES (%s, %s)
                ON CONFLICT (doctor_id, patient_id) DO NOTHING
                """,
                (doctor_id, patient_id),
            )
            conn.commit()
            return {"doctor_id": doctor_id}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    # -----------------------------------------------------------------------
    # Doctor–Patient Access
    # -----------------------------------------------------------------------

    def assign_patient(self, doctor_id: int, patient_id: int) -> bool:
        """Assign a patient to a doctor. Returns True if newly assigned."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO doctor_patients (doctor_id, patient_id)
                VALUES (%s, %s)
                ON CONFLICT (doctor_id, patient_id) DO NOTHING
                RETURNING doctor_id
                """,
                (doctor_id, patient_id),
            )
            result = cursor.fetchone()
            conn.commit()
            return result is not None
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def revoke_access(self, doctor_id: int, patient_id: int) -> bool:
        """Remove a doctor_patients link. Returns True if a row was deleted."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM doctor_patients WHERE doctor_id = %s AND patient_id = %s",
                (doctor_id, patient_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()

    def get_patients_for_doctor(self, doctor_id: int) -> List[Dict[str, Any]]:
        """
        Get all patients assigned to a doctor, with tenant info.
        Returns list of dicts with id, name, email, tenant_id, tenant_slug, granted_at.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    u.id,
                    u.name,
                    u.email,
                    tu.tenant_id,
                    t.slug AS tenant_slug,
                    dp.granted_at,
                    u.additional_data,
                    u.dob
                FROM doctor_patients dp
                JOIN users u ON dp.patient_id = u.id
                LEFT JOIN tenant_users tu ON u.id = tu.user_id
                LEFT JOIN tenants t ON tu.tenant_id = t.id
                WHERE dp.doctor_id = %s
                ORDER BY dp.granted_at DESC
                """,
                (doctor_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "tenant_id": str(row[3]) if row[3] else None,
                    "tenant_slug": row[4],
                    "granted_at": row[5],
                    "additional_data": row[6] or {},
                    "dob": str(row[7]) if row[7] else None,
                }
                for row in rows
            ]
        finally:
            cursor.close()
            conn.close()

    def get_patient_detail(self, doctor_id: int, patient_id: int) -> Optional[Dict[str, Any]]:
        """Get a single patient's detail, verifying doctor has access."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    u.id, u.name, u.email,
                    tu.tenant_id, t.slug AS tenant_slug,
                    dp.granted_at,
                    u.additional_data, u.dob
                FROM doctor_patients dp
                JOIN users u ON dp.patient_id = u.id
                LEFT JOIN tenant_users tu ON u.id = tu.user_id
                LEFT JOIN tenants t ON tu.tenant_id = t.id
                WHERE dp.doctor_id = %s AND dp.patient_id = %s
                LIMIT 1
                """,
                (doctor_id, patient_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "tenant_id": str(row[3]) if row[3] else None,
                "tenant_slug": row[4],
                "granted_at": row[5],
                "additional_data": row[6] or {},
                "dob": str(row[7]) if row[7] else None,
            }
        finally:
            cursor.close()
            conn.close()

    def get_doctors_for_patient(self, patient_id: int) -> List[Dict[str, Any]]:
        """Get all doctors who have access to a patient's data."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    u.id, u.name, u.email,
                    dp.specialty, dp.clinic_name,
                    dpat.granted_at
                FROM doctor_patients dpat
                JOIN users u ON dpat.doctor_id = u.id
                LEFT JOIN doctor_profiles dp ON dp.user_id = u.id
                WHERE dpat.patient_id = %s
                ORDER BY dpat.granted_at DESC
                """,
                (patient_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "specialty": row[3],
                    "clinic_name": row[4],
                    "granted_at": row[5],
                }
                for row in rows
            ]
        finally:
            cursor.close()
            conn.close()

    def is_doctor_assigned_to_patient(self, doctor_id: int, patient_id: int) -> bool:
        """Check if a doctor has access to a patient."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM doctor_patients WHERE doctor_id = %s AND patient_id = %s",
                (doctor_id, patient_id),
            )
            return cursor.fetchone() is not None
        finally:
            cursor.close()
            conn.close()

    def get_overview_stats(self, doctor_id: int) -> Dict[str, Any]:
        """Aggregate stats for the doctor dashboard overview."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Total patients
            cursor.execute(
                "SELECT COUNT(*) FROM doctor_patients WHERE doctor_id = %s",
                (doctor_id,),
            )
            total_patients = cursor.fetchone()[0]

            # Upcoming appointments count
            cursor.execute(
                """
                SELECT COUNT(*) FROM appointments
                WHERE doctor_id = %s AND status = 'scheduled' AND scheduled_at >= NOW()
                """,
                (doctor_id,),
            )
            upcoming_appointments = cursor.fetchone()[0]

            return {
                "total_patients": total_patients,
                "upcoming_appointments": upcoming_appointments,
            }
        finally:
            cursor.close()
            conn.close()
