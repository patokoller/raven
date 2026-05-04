"""Raven — Core configuration. All settings from environment variables."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    DATABASE_URL: str = ""   # optional — not used directly in MVP

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-4-5"

    # Market data
    COINGECKO_API_KEY: str = ""
    NEWS_API_KEY: str = ""

    # Storage
    STORAGE_BUCKET: str = "raven-reports"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "https://raven.vercel.app",
        "https://*.vercel.app",
    ]

    # Tenant
    DEFAULT_TENANT_ID: str = "aaaaaaaa-0000-0000-0000-000000000001"

    # Scoring weights
    SCORING_WEIGHTS: dict = {
        "regulatory":  0.25,
        "financial":   0.20,
        "operational": 0.20,
        "liquidity":   0.15,
        "onchain":     0.10,
        "reputation":  0.10,
    }

    # Alert thresholds
    ALERT_SCORE_DROP_THRESHOLD: float = 10.0


settings = Settings()
