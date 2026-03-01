from datetime import datetime, timedelta
from typing import Any, Union, Optional
import hashlib
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Use configured refresh token expiry (default: 7 days)
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt has a 72 byte limit. Truncate silently to prevent crashes.
    return pwd_context.verify(plain_password[:72], hashed_password)

def get_password_hash(password: str) -> str:
    # bcrypt has a 72 byte limit. Truncate silently to prevent crashes.
    return pwd_context.hash(password[:72])

def sha1_hash(text: str) -> str:
    """
    Generate SHA-1 hash of the input text.
    Used for OneTwenty API secret compatibility.
    """
    return hashlib.sha1(text.encode('utf-8')).hexdigest()

def verify_api_secret(provided_secret: str, stored_secret: str) -> bool:
    """
    Verify API secret with backward compatibility for OneTwenty clients.
    
    OneTwenty clients (xDrip, Spike, etc.) send SHA-1 hashed secrets.
    We need to compare:
    1. SHA-1(provided_secret) == stored_secret (plain text stored)
    2. provided_secret == stored_secret (already hashed)
    3. SHA-1(provided_secret) == SHA-1(stored_secret) (both plain)
    
    Args:
        provided_secret: Secret from client (could be plain or SHA-1 hashed)
        stored_secret: Secret from database (plain text)
    
    Returns:
        bool: True if secrets match
    """
    # Method 1: Client sends SHA-1 hash, we hash our stored plain secret and compare
    if sha1_hash(stored_secret) == provided_secret:
        return True
    
    # Method 2: Direct comparison (for non-OneTwenty clients or already hashed)
    if provided_secret == stored_secret:
        return True
    
    # Method 3: Both are plain text
    if sha1_hash(provided_secret) == sha1_hash(stored_secret):
        return True
    
    return False
