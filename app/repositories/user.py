import random
import string
import json
from app.db.session import get_db_connection
from app.schemas.tenant import DEFAULT_TENANT_SETTINGS
from typing import Optional, Dict, Any

class UserRepository:
    def __init__(self):
        pass

    def _generate_public_id(self, length=10) -> str:
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT id, public_id, email, hashed_password, role, tier, is_active,
                          name, additional_data, dob
                   FROM users WHERE id = %s""",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "public_id": row[1],
                    "email": row[2],
                    "hashed_password": row[3],
                    "role": row[4],
                    "tier": row[5],
                    "is_active": row[6],
                    "name": row[7],
                    "additional_data": row[8] or {},
                    "dob": row[9]
                }
            return None
        finally:
            cursor.close()
            conn.close()

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT id, public_id, email, hashed_password, role, tier, is_active,
                          name, additional_data, dob
                   FROM users WHERE email = %s""",
                (email,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "public_id": row[1],
                    "email": row[2],
                    "hashed_password": row[3],
                    "role": row[4],
                    "tier": row[5],
                    "is_active": row[6],
                    "name": row[7],
                    "additional_data": row[8] or {},
                    "dob": row[9]
                }
            return None
        finally:
            cursor.close()
            conn.close()

    def create(
        self,
        email: str,
        hashed_password: str,
        name: Optional[str] = None,
        role: str = "user",
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            public_id = self._generate_public_id()
            tenant_public_id = self._generate_public_id()
            additional_data = additional_data or {}

            # 1. Create Tenant
            cursor.execute(
                "INSERT INTO tenants (public_id, name, slug, settings) VALUES (%s, %s, %s, %s) RETURNING id",
                (tenant_public_id, f"{email}'s OneTwenty", tenant_public_id.lower(), json.dumps(DEFAULT_TENANT_SETTINGS)) 
            )
            tenant_id = cursor.fetchone()[0]

            # 2. Create User (with role)
            cursor.execute(
                """INSERT INTO users (public_id, email, hashed_password, name, role, additional_data)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id, public_id, email, is_active, name, additional_data, role""",
                (public_id, email, hashed_password, name, role, json.dumps(additional_data))
            )
            user_row = cursor.fetchone()
            user_id = user_row[0]

            # 3. Link to Tenant
            cursor.execute(
                "INSERT INTO tenant_users (user_id, tenant_id, role) VALUES (%s, %s, 'owner')",
                (user_id, tenant_id)
            )

            conn.commit()

            return {
                "id": user_id,
                "public_id": user_row[1],
                "email": user_row[2],
                "is_active": user_row[3],
                "name": user_row[4],
                "additional_data": user_row[5] or {},
                "role": user_row[6],
                "tenant_id": tenant_id,
                "tenant_slug": tenant_public_id.lower(),
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()



    def create_api_key(self, tenant_id: int, description: str = "Default") -> str:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            prefix = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
            secret = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
            key_value = f"{prefix}_{secret}"
            cursor.execute(
                "INSERT INTO api_keys (tenant_id, key_value, description) VALUES (%s, %s, %s) RETURNING key_value",
                (tenant_id, key_value, description)
            )
            conn.commit()
            return cursor.fetchone()[0]
        finally:
            cursor.close()
            conn.close()

    def get_active_api_key(self, tenant_id: int) -> Optional[str]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT key_value FROM api_keys WHERE tenant_id = %s AND is_active = TRUE LIMIT 1",
                (tenant_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            cursor.close()
            conn.close()

    def revoke_api_keys(self, tenant_id: int):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE api_keys SET is_active = FALSE WHERE tenant_id = %s", (tenant_id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def get_tenant_for_user(self, user_id: int) -> Optional[int]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT tenant_id FROM tenant_users WHERE user_id = %s LIMIT 1", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            cursor.close()
            conn.close()

    def get_tenant_slug(self, tenant_id: int) -> Optional[str]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT slug FROM tenants WHERE id = %s", (tenant_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            cursor.close()
            conn.close()
    def get_owner_details(self, tenant_id: int) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT u.name, u.email, u.dob
                   FROM users u
                   JOIN tenant_users tu ON tu.user_id = u.id
                   WHERE tu.tenant_id = %s AND tu.role = 'owner'
                   LIMIT 1""",
                (tenant_id,)
            )
            row = cursor.fetchone()
            if row:
                return {"name": row[0], "email": row[1], "dob": row[2]}
            return None
        finally:
            cursor.close()
            conn.close()

    def update_user_profile(
        self, 
        user_id: int, 
        name: Optional[str] = None, 
        dob: Optional[Any] = None, 
        additional_data_updates: Optional[Dict[str, Any]] = None
    ) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = %s")
                params.append(name)
            
            if dob is not None:
                updates.append("dob = %s")
                params.append(dob)
                
            if additional_data_updates:
                # Use jsonb_set or simple concatenation || for updates
                # For simplicity and to match the plan's "flexible JSONB" approach, we use || 
                updates.append("additional_data = additional_data || %s::jsonb")
                params.append(json.dumps(additional_data_updates))
                
            if not updates:
                return False
                
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(query, tuple(params))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()
