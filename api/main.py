"""
Raven — Risk & Portfolio Intelligence Engine
FastAPI Backend — main.py
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.database import engine
from app.routers import (
    auth,
    counterparties,
    portfolios,
    reports,
    alerts,
    agents,
    stress_tests,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print(f"🦅 Raven API starting — environment: {settings.ENVIRONMENT}")
    yield
    print("Raven API shutting down.")


app = FastAPI(
    title="Raven API",
    description="Risk & Portfolio Intelligence Engine — Internal API",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# ── ROUTERS ───────────────────────────────────────────────────
app.include_router(auth.router,           prefix="/api/v1/auth",           tags=["Auth"])
app.include_router(counterparties.router, prefix="/api/v1/counterparties", tags=["Counterparties"])
app.include_router(portfolios.router,     prefix="/api/v1/portfolios",     tags=["Portfolios"])
app.include_router(reports.router,        prefix="/api/v1/reports",        tags=["Reports"])
app.include_router(alerts.router,         prefix="/api/v1/alerts",         tags=["Alerts"])
app.include_router(agents.router,         prefix="/api/v1/agents",         tags=["Agents"])
app.include_router(stress_tests.router,   prefix="/api/v1/stress",         tags=["Stress Tests"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "raven-api", "version": "0.1.0"}
