"""Raven — Auth Router"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.database import supabase
from app.core.config import settings

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "analyst"

@router.post("/login")
async def login(body: LoginRequest):
    try:
        resp = supabase.auth.sign_in_with_password({"email": body.email, "password": body.password})
        if not resp.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {
            "access_token": resp.session.access_token,
            "token_type": "bearer",
            "user": {"email": resp.user.email, "id": resp.user.id},
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@router.post("/register")
async def register(body: RegisterRequest):
    """Register a new internal user. Only callable by admins in production."""
    try:
        auth_resp = supabase.auth.sign_up({"email": body.email, "password": body.password})
        if not auth_resp.user:
            raise HTTPException(status_code=400, detail="Registration failed")

        supabase.table("users").insert({
            "tenant_id": settings.DEFAULT_TENANT_ID,
            "auth_id": auth_resp.user.id,
            "email": body.email,
            "full_name": body.full_name,
            "role": body.role,
        }).execute()

        return {"status": "registered", "email": body.email}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/me")
async def me(current_user = None):
    from app.core.auth import get_current_user
    from fastapi import Depends
    return {"message": "use Bearer token"}
