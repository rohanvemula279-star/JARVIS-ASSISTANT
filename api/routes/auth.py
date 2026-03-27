from fastapi import APIRouter, Depends, HTTPException, status # pyre-ignore[21]
from typing import Optional
from fastapi.security import OAuth2PasswordRequestForm # pyre-ignore[21]
from sqlalchemy.ext.asyncio import AsyncSession # pyre-ignore[21]
from pydantic import BaseModel # pyre-ignore[21]
from ..auth import verify_pin, create_access_token, create_refresh_token, get_current_user # pyre-ignore[21]
from ..database import get_db, Session # pyre-ignore[21]
from datetime import datetime
import uuid

router = APIRouter()

class LoginRequest(BaseModel):
    pin: str
    device_id: str
    device_name: Optional[str] = None   # pyre-ignore[21]

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # We use OAuth2PasswordRequestForm for compatibility with Swagger UI
    # username is ignored, password is the PIN
    pin = form_data.password
    
    if not verify_pin(pin):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect PIN",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = "owner" # Single user system
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 3600
    }

@router.get("/status")
async def get_status(current_user: str = Depends(get_current_user)):
    return {
        "status": "online",
        "user": current_user,
        "timestamp": datetime.utcnow().isoformat()
    }
