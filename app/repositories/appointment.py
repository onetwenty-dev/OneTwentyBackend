from app.db.session import get_db_connection
from typing import List, Optional, Dict, Any
from datetime import datetime


class AppointmentRepository:
    def __init__(self):
        pass

    def create(self, doctor_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a new appointment."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO appointments (doctor_id, patient_id, scheduled_at, duration_min, type, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, doctor_id, patient_id, scheduled_at, duration_min, type, notes, status, created_at
                """,
                (
                    doctor_id,
                    data["patient_id"],
                    data["scheduled_at"],
                    data.get("duration_min", 30),
                    data.get("type", "Follow-up"),
                    data.get("notes"),
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return self._row_to_dict(row)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def get_for_doctor(
        self,
        doctor_id: int,
        filter_status: Optional[str] = None,  # 'upcoming', 'past', or None for all
    ) -> List[Dict[str, Any]]:
        """List appointments for a doctor, optionally filtered."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            base_query = """
                SELECT
                    a.id, a.doctor_id, a.patient_id,
                    u.name AS patient_name, u.email AS patient_email,
                    a.scheduled_at, a.duration_min, a.type, a.notes, a.status, a.created_at
                FROM appointments a
                JOIN users u ON a.patient_id = u.id
                WHERE a.doctor_id = %s
            """
            params = [doctor_id]

            if filter_status == "upcoming":
                base_query += " AND a.scheduled_at >= NOW() AND a.status = 'scheduled'"
            elif filter_status == "past":
                base_query += " AND a.scheduled_at < NOW()"

            base_query += " ORDER BY a.scheduled_at ASC"

            cursor.execute(base_query, params)
            rows = cursor.fetchall()
            return [self._row_to_dict_full(row) for row in rows]
        finally:
            cursor.close()
            conn.close()

    def get_by_id(self, appointment_id: int, doctor_id: int) -> Optional[Dict[str, Any]]:
        """Get a single appointment, verifying it belongs to the doctor."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    a.id, a.doctor_id, a.patient_id,
                    u.name AS patient_name, u.email AS patient_email,
                    a.scheduled_at, a.duration_min, a.type, a.notes, a.status, a.created_at
                FROM appointments a
                JOIN users u ON a.patient_id = u.id
                WHERE a.id = %s AND a.doctor_id = %s
                """,
                (appointment_id, doctor_id),
            )
            row = cursor.fetchone()
            return self._row_to_dict_full(row) if row else None
        finally:
            cursor.close()
            conn.close()

    def update(self, appointment_id: int, doctor_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an appointment. Returns updated record or None if not found."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            allowed = ["scheduled_at", "duration_min", "type", "notes", "status"]
            updates = []
            params = []
            for field in allowed:
                if field in data and data[field] is not None:
                    updates.append(f"{field} = %s")
                    params.append(data[field])

            if not updates:
                return self.get_by_id(appointment_id, doctor_id)

            params += [appointment_id, doctor_id]
            cursor.execute(
                f"""
                UPDATE appointments SET {', '.join(updates)}
                WHERE id = %s AND doctor_id = %s
                RETURNING id, doctor_id, patient_id, scheduled_at, duration_min, type, notes, status, created_at
                """,
                params,
            )
            row = cursor.fetchone()
            conn.commit()
            return self._row_to_dict(row) if row else None
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def delete(self, appointment_id: int, doctor_id: int) -> bool:
        """Delete an appointment. Returns True if deleted."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM appointments WHERE id = %s AND doctor_id = %s",
                (appointment_id, doctor_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Map a basic appointments row (no joined columns)."""
        return {
            "id": row[0],
            "doctor_id": row[1],
            "patient_id": row[2],
            "patient_name": None,
            "patient_email": None,
            "scheduled_at": row[3],
            "duration_min": row[4],
            "type": row[5],
            "notes": row[6],
            "status": row[7],
            "created_at": row[8],
        }

    def _row_to_dict_full(self, row) -> Dict[str, Any]:
        """Map a full appointments row including joined patient columns."""
        return {
            "id": row[0],
            "doctor_id": row[1],
            "patient_id": row[2],
            "patient_name": row[3],
            "patient_email": row[4],
            "scheduled_at": row[5],
            "duration_min": row[6],
            "type": row[7],
            "notes": row[8],
            "status": row[9],
            "created_at": row[10],
        }
