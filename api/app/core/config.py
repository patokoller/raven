"""
Raven — Core configuration
All settings loaded from environment variables.
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str                    # used for JWT signing

    # ── Database (Supabase) ──────────────────────────────────
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    DATABASE_URL: str                  # postgres://... direct connection

    # ── Anthropic ────────────────────────────────────────────
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-opus-4-5"

    # ── Market Data ──────────────────────────────────────────
    COINGECKO_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    POLYGON_API_KEY: str = ""          # for equities (optional at MVP)

    # ── Storage ──────────────────────────────────────────────
    STORAGE_BUCKET: str = "raven-reports"   # Supabase Storage bucket

    # ── CORS ─────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://raven.vercel.app"]

    # ── Tenant ───────────────────────────────────────────────
    DEFAULT_TENANT_ID: str = "aaaaaaaa-0000-0000-0000-000000000001"

    # ── Scoring weights (calibrated by domain expert) ────────
    SCORING_WEIGHTS: dict = {
        "regulatory":  0.25,
        "financial":   0.20,
        "operational": 0.20,
        "liquidity":   0.15,
        "onchain":     0.10,
        "reputation":  0.10,
    }

    # ── Alert thresholds ─────────────────────────────────────
    ALERT_SCORE_DROP_THRESHOLD: float = 10.0   # trigger if score drops > 10 pts
    ALERT_TIER_CHANGE: bool = True

    # ── Celery / Task queue ──────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"


settings = Settings()
