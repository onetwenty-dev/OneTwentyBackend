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

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, public_id, email, hashed_password, role, tier, is_active FROM users WHERE email = %s", 
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
                    "is_active": row[6]
                }
            return None
        finally:
            cursor.close()
            conn.close()

    def create(self, email: str, hashed_password: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            public_id = self._generate_public_id()
            # Also create a default tenant? Yes, 1:1 for now is simplest for SaaS onboarding
            tenant_public_id = self._generate_public_id()
            
            # Start Transaction
            # 1. Create Tenant with default settings
            cursor.execute(
                "INSERT INTO tenants (public_id, name, slug, settings) VALUES (%s, %s, %s, %s) RETURNING id",
                (tenant_public_id, f"{email}'s OneTwenty", tenant_public_id.lower(), json.dumps(DEFAULT_TENANT_SETTINGS)) 
            )
            tenant_id = cursor.fetchone()[0]

            # 2. Create User
            cursor.execute(
                "INSERT INTO users (public_id, email, hashed_password) VALUES (%s, %s, %s) RETURNING id, public_id, email, is_active",
                (public_id, email, hashed_password)
            )
            user_row = cursor.fetchone()
            user_id = user_row[0]
            
            # 3. Link User to Tenant (Owner)
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
                "tenant_id": tenant_id
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
            # Generate key: 10char prefix + 32char random
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
            if row:
                return row[0]
            return None
        finally:
            cursor.close()
            conn.close()

    def revoke_api_keys(self, tenant_id: int):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE api_keys SET is_active = FALSE WHERE tenant_id = %s",
                (tenant_id,)
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def get_tenant_for_user(self, user_id: int) -> int:
         conn = get_db_connection()
         cursor = conn.cursor()
         try:
             # Just get the first tenant they own for now
             cursor.execute("SELECT tenant_id FROM tenant_users WHERE user_id = %s LIMIT 1", (user_id,))
             row = cursor.fetchone()
             if row:
                 return row[0]
             return None
         finally:
             cursor.close()
             conn.close()
