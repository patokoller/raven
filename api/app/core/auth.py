"""
Raven — Auth middleware
Decodes Supabase JWT payload using raw base64 — no library dependencies.
"""

import base64
import json
from dataclasses import dataclass
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.database import supabase

security = HTTPBearer()


@dataclass
class CurrentUser:
    user_id: str
    tenant_id: str
    email: str
    role: str
    auth_id: str


def _decode_jwt_payload(token: str) -> dict:
    """
    Decode JWT payload using raw base64. No signature verification.
    Works with any JWT regardless of algorithm or signing key.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Not a JWT")
        payload_b64 = parts[1]
        # Fix base64 padding
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception as e:
        raise ValueError(f"Failed to decode JWT: {e}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    token = credentials.credentials

    unauth = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Step 1: Decode JWT payload
    try:
        payload = _decode_jwt_payload(token)
        auth_id = payload.get("sub")
        if not auth_id:
            raise unauth
    except ValueError:
        raise unauth

    # Step 2: Look up user in DB
    try:
        result = (
            supabase.table("users")
            .select("user_id, tenant_id, email, role, is_active")
            .eq("auth_id", auth_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"No user found with auth_id={auth_id}. Run the INSERT users SQL.",
            )
        db_user = result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )

    return CurrentUser(
        user_id=db_user["user_id"],
        tenant_id=db_user["tenant_id"],
        email=db_user["email"],
        role=db_user["role"],
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user
