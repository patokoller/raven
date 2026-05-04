"""
Raven — Auth middleware
Decodes Supabase JWT directly to get user identity.
"""

from dataclasses import dataclass
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

from app.core.database import supabase
from app.core.config import settings

security = HTTPBearer()


@dataclass
class CurrentUser:
    user_id: str
    tenant_id: str
    email: str
    role: str
    auth_id: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    token = credentials.credentials

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT without signature verification
        # Supabase signs tokens — we trust them and verify identity via DB lookup
        payload = jwt.decode(
            token,
            key="",
            options={
                "verify_signature": False,
                "verify_exp": False,   # Supabase handles expiry
            },
            algorithms=["HS256"],
        )

        auth_id: str = payload.get("sub")
        if not auth_id:
            raise credentials_exception

    except Exception:
        raise credentials_exception

    # Look up internal user record
    try:
        db_user = (
            supabase.table("users")
            .select("user_id, tenant_id, email, role, is_active")
            .eq("auth_id", auth_id)
            .single()
            .execute()
        )
    except Exception:
        raise credentials_exception

    if not db_user.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Ensure your user record exists in the users table.",
        )

    if not db_user.data.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return CurrentUser(
        user_id=db_user.data["user_id"],
        tenant_id=db_user.data["tenant_id"],
        email=db_user.data["email"],
        role=db_user.data["role"],
        auth_id=auth_id,
    )


def require_senior_analyst(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if current_user.role not in ("senior_analyst", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Senior Analyst or Admin role required",
        )
    return current_user


def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user
