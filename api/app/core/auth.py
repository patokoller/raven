"""
Raven — Auth middleware
JWT verification via Supabase. MFA enforcement for senior_analyst and admin roles.
"""

from dataclasses import dataclass
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx

from app.core.config import settings
from app.core.database import supabase

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
        # Verify token with Supabase
        user_resp = supabase.auth.get_user(token)
        if not user_resp or not user_resp.user:
            raise credentials_exception

        auth_id = user_resp.user.id

        # Fetch internal user record
        db_user = (
            supabase.table("users")
            .select("user_id, tenant_id, email, role, is_active")
            .eq("auth_id", auth_id)
            .single()
            .execute()
        )

        if not db_user.data or not db_user.data.get("is_active"):
            raise credentials_exception

        return CurrentUser(
            user_id=db_user.data["user_id"],
            tenant_id=db_user.data["tenant_id"],
            email=db_user.data["email"],
            role=db_user.data["role"],
            auth_id=auth_id,
        )

    except Exception as e:
        raise credentials_exception


def require_senior_analyst(current_user: CurrentUser = Depends(get_current_user)):
    """Only senior_analyst or admin can call this endpoint."""
    if current_user.role not in ("senior_analyst", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Senior Analyst or Admin role required",
        )
    return current_user


def require_admin(current_user: CurrentUser = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user
