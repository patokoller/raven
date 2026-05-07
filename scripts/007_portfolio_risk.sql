-- Migration: Portfolio risk management enhancements
-- Run in Supabase SQL Editor

-- Add client limits table (exposure limits per client mandate)
CREATE TABLE IF NOT EXISTS client_limits (
  limit_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id),
  client_id       UUID NOT NULL REFERENCES clients(client_id),
  limit_type      TEXT NOT NULL, -- 'counterparty', 'jurisdiction', 'entity_type', 'risk_tier'
  limit_key       TEXT NOT NULL, -- counterparty slug, jurisdiction code, entity_type, risk_tier
  limit_pct       NUMERIC(6,4) NOT NULL, -- max allowed as % of portfolio NAV
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(client_id, limit_type, limit_key)
);

-- Add portfolio risk cache table (pre-computed risk analytics)
CREATE TABLE IF NOT EXISTS portfolio_risk_cache (
  cache_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id        UUID NOT NULL REFERENCES tenants(tenant_id),
  portfolio_id     UUID NOT NULL REFERENCES portfolios(portfolio_id),
  computed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  weighted_risk_score   NUMERIC(5,2),
  risk_tier_breakdown   JSONB,  -- {LOW: chf, MEDIUM: chf, HIGH: chf, CRITICAL: chf}
  jurisdiction_breakdown JSONB, -- {CH: chf, GB: chf, US: chf, ...}
  entity_type_breakdown  JSONB,
  concentration_warnings JSONB, -- [{name, pct, value_chf, tier}]
  limit_breaches        JSONB,  -- [{type, key, limit_pct, actual_pct}]
  finma_compliant       BOOLEAN,
  finma_flags           JSONB,  -- [{name, reason}]
  correlation_groups    JSONB,  -- [{group, entities, combined_pct}]
  score_delta_7d        NUMERIC(5,2),
  score_delta_30d       NUMERIC(5,2),
  open_alert_count      INT DEFAULT 0,
  latest_report_status  TEXT,
  latest_report_date    DATE,
  UNIQUE(portfolio_id)
);

ALTER TABLE client_limits DISABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_risk_cache DISABLE ROW LEVEL SECURITY;
GRANT ALL ON client_limits TO service_role;
GRANT ALL ON portfolio_risk_cache TO service_role;

-- Default limits for all existing clients
INSERT INTO client_limits (tenant_id, client_id, limit_type, limit_key, limit_pct)
SELECT
  c.tenant_id, c.client_id, 'counterparty', 'any_single', 0.20
FROM clients c
ON CONFLICT DO NOTHING;

INSERT INTO client_limits (tenant_id, client_id, limit_type, limit_key, limit_pct)
SELECT
  c.tenant_id, c.client_id, 'jurisdiction', 'any_single', 0.40
FROM clients c
ON CONFLICT DO NOTHING;

INSERT INTO client_limits (tenant_id, client_id, limit_type, limit_key, limit_pct)
SELECT
  c.tenant_id, c.client_id, 'risk_tier', 'HIGH', 0.30
FROM clients c
ON CONFLICT DO NOTHING;

INSERT INTO client_limits (tenant_id, client_id, limit_type, limit_key, limit_pct)
SELECT
  c.tenant_id, c.client_id, 'risk_tier', 'CRITICAL', 0.05
FROM clients c
ON CONFLICT DO NOTHING;

SELECT 'portfolio risk management tables created' as status;

-- AI analysis columns on portfolio_risk_cache (run if not already added)
ALTER TABLE portfolio_risk_cache
  ADD COLUMN IF NOT EXISTS ai_analysis    JSONB,
  ADD COLUMN IF NOT EXISTS ai_analysed_at TIMESTAMPTZ;
