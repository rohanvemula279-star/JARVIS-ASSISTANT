from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt  # pyre-ignore[21]
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status  # pyre-ignore[21]
from fastapi.security import OAuth2PasswordBearer
from .config import settings  # pyre-ignore[21]
from .database import get_db  # pyre-ignore[21]
from sqlalchemy.ext.asyncio import AsyncSession  # pyre-ignore[21]
import bcrypt
import os

# Password hashing context (for internal use if needed)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

# Path to the shared enrollment PIN hash (sync with desktop)
from config.face_config import ENROLLMENT_PIN_HASH_PATH # pyre-ignore[21]

def verify_pin(plain_pin: str) -> bool:
    if not os.path.exists(ENROLLMENT_PIN_HASH_PATH):
        return False
    try:
        stored_hash = open(ENROLLMENT_PIN_HASH_PATH, "r").read().strip()
        # The desktop app uses bcrypt.checkpw
        return bcrypt.checkpw(plain_pin.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception as e:
        print(f"Auth Error: {e}")
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception
