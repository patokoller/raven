"""Raven — Risk & Portfolio Intelligence Engine · FastAPI Backend"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, counterparties, portfolios, reports, alerts, agents, stress_tests


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🦅 Raven API starting — {settings.ENVIRONMENT}")
    yield
    print("Raven API shut down.")


app = FastAPI(
    title="Raven API",
    description="Risk & Portfolio Intelligence Engine",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten after MVP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,           prefix="/api/v1/auth",           tags=["Auth"])
app.include_router(counterparties.router, prefix="/api/v1/counterparties", tags=["Counterparties"])
app.include_router(portfolios.router,     prefix="/api/v1/portfolios",     tags=["Portfolios"])
app.include_router(reports.router,        prefix="/api/v1/reports",        tags=["Reports"])
app.include_router(alerts.router,         prefix="/api/v1/alerts",         tags=["Alerts"])
app.include_router(agents.router,         prefix="/api/v1/agents",         tags=["Agents"])
app.include_router(stress_tests.router,   prefix="/api/v1/stress",         tags=["Stress Tests"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "raven-api", "version": "0.1.0"}


# Clients endpoint (lightweight — used by portfolio upload UI)
from fastapi import Depends as _Depends
from app.core.auth import get_current_user as _gcu

@app.get("/api/v1/clients", tags=["Clients"])
async def list_clients(current_user=_Depends(_gcu)):
    from app.core.database import supabase as _sb
    from app.core.config import settings as _s
    return _sb.table("clients").select("client_id,client_ref,display_name,aum_chf").eq("tenant_id", _s.DEFAULT_TENANT_ID).execute().data
