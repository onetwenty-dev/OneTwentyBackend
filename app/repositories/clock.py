from app.db.session import get_db_connection
from typing import Optional, List, Dict, Any
from datetime import datetime

class ClockRepository:
    def _row_to_dict(self, row) -> Dict[str, Any]:
        return {
            "id": row[0],
            "clock_id": row[1],
            "wifi_name": row[2],
            "wifi_password": row[3],
            "user_subdomain_url": row[4],
            "tenant_id": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }

    def get_by_clock_id(self, clock_id: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT id, clock_id, wifi_name, wifi_password, user_subdomain_url,
                          tenant_id, created_at, updated_at
                   FROM clock_configs WHERE clock_id = %s""",
                (clock_id,)
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            cursor.close()
            conn.close()

    def create(
        self,
        clock_id: str,
        wifi_name: Optional[str],
        wifi_password: Optional[str],
        user_subdomain_url: Optional[str],
        tenant_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO clock_configs (clock_id, wifi_name, wifi_password, user_subdomain_url, tenant_id)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id, clock_id, wifi_name, wifi_password, user_subdomain_url,
                             tenant_id, created_at, updated_at""",
                (clock_id, wifi_name, wifi_password, user_subdomain_url, tenant_id)
            )
            row = cursor.fetchone()
            conn.commit()
            return self._row_to_dict(row)
        finally:
            cursor.close()
            conn.close()

    def update(
        self,
        clock_id: str,
        wifi_name: Optional[str] = None,
        wifi_password: Optional[str] = None,
        user_subdomain_url: Optional[str] = None,
        tenant_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            updates = []
            params = []

            if wifi_name is not None:
                updates.append("wifi_name = %s")
                params.append(wifi_name)
            if wifi_password is not None:
                updates.append("wifi_password = %s")
                params.append(wifi_password)
            if user_subdomain_url is not None:
                updates.append("user_subdomain_url = %s")
                params.append(user_subdomain_url)
            if tenant_id is not None:
                updates.append("tenant_id = %s")
                params.append(tenant_id)

            if not updates:
                return self.get_by_clock_id(clock_id)

            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(clock_id)

            query = (
                f"UPDATE clock_configs SET {', '.join(updates)} WHERE clock_id = %s "
                f"RETURNING id, clock_id, wifi_name, wifi_password, user_subdomain_url, "
                f"tenant_id, created_at, updated_at"
            )
            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            conn.commit()
            return self._row_to_dict(row) if row else None
        finally:
            cursor.close()
            conn.close()

    def assign_to_tenant(
        self,
        clock_id: str,
        tenant_id: int,
        user_subdomain_url: str,
    ) -> Optional[Dict[str, Any]]:
        """Assign a clock to a tenant, storing both tenant_id and the subdomain URL."""
        return self.update(
            clock_id=clock_id,
            tenant_id=tenant_id,
            user_subdomain_url=user_subdomain_url,
        )

    def get_by_tenant_id(self, tenant_id: int) -> List[Dict[str, Any]]:
        """Return all clocks assigned to a given tenant."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT id, clock_id, wifi_name, wifi_password, user_subdomain_url,
                          tenant_id, created_at, updated_at
                   FROM clock_configs WHERE tenant_id = %s ORDER BY created_at DESC""",
                (tenant_id,)
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()
