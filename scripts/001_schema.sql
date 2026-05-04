-- ============================================================
-- RAVEN — Database Schema v1.1 (Supabase-Compatible)
-- Fixed: removed TimescaleDB dependency, unique RLS policy names
-- Run entirely in one go in Supabase SQL Editor
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ── ENUMS ─────────────────────────────────────────────────────
DO $$ BEGIN CREATE TYPE counterparty_type AS ENUM (
  'exchange','custodian','otc_desk','defi_protocol','prime_broker','market_maker','lender'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE risk_tier AS ENUM ('LOW','MEDIUM','HIGH','CRITICAL');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE alert_status AS ENUM ('OPEN','ACKNOWLEDGED','ESCALATED','DISMISSED','RESOLVED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE alert_severity AS ENUM ('INFO','WARNING','HIGH','CRITICAL');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE report_status AS ENUM ('DRAFT','IN_REVIEW','CHANGES_REQUESTED','APPROVED','DELIVERED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE user_role AS ENUM ('analyst','senior_analyst','admin');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE actor_type AS ENUM ('USER','AGENT','SYSTEM','EXTERNAL_API');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE event_category AS ENUM (
  'DATA_ACCESS','DATA_WRITE','AUTH','AGENT','HUMAN_REVIEW','DELIVERY','CONFIG_CHANGE','SECURITY'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE asset_class AS ENUM (
  'crypto','equity','etf','fund','cash','fixed_income','commodity','stablecoin'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── TENANTS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
  tenant_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  slug       TEXT UNIQUE NOT NULL,
  name       TEXT NOT NULL,
  plan_tier  TEXT NOT NULL DEFAULT 'starter',
  settings   JSONB NOT NULL DEFAULT '{}',
  is_active  BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO tenants (tenant_id, slug, name, plan_tier)
VALUES ('aaaaaaaa-0000-0000-0000-000000000001','raven-internal','Raven Internal','professional')
ON CONFLICT DO NOTHING;

-- ── USERS ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  user_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id     UUID NOT NULL REFERENCES tenants(tenant_id),
  auth_id       UUID UNIQUE,
  email         TEXT UNIQUE NOT NULL,
  full_name     TEXT NOT NULL,
  role          user_role NOT NULL DEFAULT 'analyst',
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  last_login_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_tenant  ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_auth_id ON users(auth_id);

-- ── COUNTERPARTIES ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS counterparties (
  counterparty_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id            UUID NOT NULL REFERENCES tenants(tenant_id),
  slug                 TEXT UNIQUE NOT NULL,
  display_name         TEXT NOT NULL,
  legal_name           TEXT,
  entity_type          counterparty_type NOT NULL,
  jurisdiction         TEXT,
  regulator            TEXT,
  license_number       TEXT,
  website              TEXT,
  blockchain_addresses JSONB NOT NULL DEFAULT '[]',
  external_ids         JSONB NOT NULL DEFAULT '{}',
  latest_score_id      UUID,
  current_risk_tier    risk_tier,
  is_active            BOOLEAN NOT NULL DEFAULT TRUE,
  notes                TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cp_tenant ON counterparties(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cp_type   ON counterparties(entity_type);
CREATE INDEX IF NOT EXISTS idx_cp_tier   ON counterparties(current_risk_tier);
CREATE INDEX IF NOT EXISTS idx_cp_slug   ON counterparties(slug);

-- ── COUNTERPARTY SCORES ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS counterparty_scores (
  score_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id          UUID NOT NULL REFERENCES tenants(tenant_id),
  counterparty_id    UUID NOT NULL REFERENCES counterparties(counterparty_id),
  scored_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  composite_score    NUMERIC(5,2) NOT NULL CHECK (composite_score BETWEEN 0 AND 100),
  risk_tier          risk_tier NOT NULL,
  regulatory_score   NUMERIC(5,2),
  financial_score    NUMERIC(5,2),
  operational_score  NUMERIC(5,2),
  liquidity_score    NUMERIC(5,2),
  onchain_score      NUMERIC(5,2),
  reputation_score   NUMERIC(5,2),
  weights            JSONB NOT NULL DEFAULT '{}',
  data_snapshot      JSONB NOT NULL DEFAULT '{}',
  agent_run_id       UUID,
  model_version      TEXT,
  confidence         NUMERIC(4,3),
  is_overridden      BOOLEAN NOT NULL DEFAULT FALSE,
  override_by        UUID REFERENCES users(user_id),
  override_rationale TEXT,
  override_at        TIMESTAMPTZ,
  score_delta_7d     NUMERIC(5,2),
  score_delta_30d    NUMERIC(5,2),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_scores_cp     ON counterparty_scores(counterparty_id, scored_at DESC);
CREATE INDEX IF NOT EXISTS idx_scores_tenant ON counterparty_scores(tenant_id, scored_at DESC);

-- ── SCORE OVERRIDES ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS score_overrides (
  override_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id),
  score_id        UUID NOT NULL REFERENCES counterparty_scores(score_id),
  counterparty_id UUID NOT NULL REFERENCES counterparties(counterparty_id),
  user_id         UUID NOT NULL REFERENCES users(user_id),
  dimension       TEXT NOT NULL,
  original_value  NUMERIC(5,2) NOT NULL,
  override_value  NUMERIC(5,2) NOT NULL,
  rationale       TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── ALERTS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
  alert_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id),
  counterparty_id UUID REFERENCES counterparties(counterparty_id),
  alert_type      TEXT NOT NULL,
  severity        alert_severity NOT NULL DEFAULT 'WARNING',
  status          alert_status NOT NULL DEFAULT 'OPEN',
  title           TEXT NOT NULL,
  body            TEXT NOT NULL,
  metadata        JSONB NOT NULL DEFAULT '{}',
  assigned_to     UUID REFERENCES users(user_id),
  acknowledged_by UUID REFERENCES users(user_id),
  acknowledged_at TIMESTAMPTZ,
  resolved_by     UUID REFERENCES users(user_id),
  resolved_at     TIMESTAMPTZ,
  resolution_note TEXT,
  triggered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alerts_tenant ON alerts(tenant_id, status, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_cp     ON alerts(counterparty_id, status);

-- ── CLIENTS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clients (
  client_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id            UUID NOT NULL REFERENCES tenants(tenant_id),
  client_ref           TEXT UNIQUE NOT NULL,
  display_name         TEXT NOT NULL,
  legal_name           TEXT,
  domicile             TEXT,
  risk_profile         TEXT,
  aum_chf              NUMERIC(18,2),
  relationship_manager TEXT,
  mandate_params       JSONB NOT NULL DEFAULT '{}',
  is_active            BOOLEAN NOT NULL DEFAULT TRUE,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_clients_tenant ON clients(tenant_id);

-- ── PORTFOLIOS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolios (
  portfolio_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id        UUID NOT NULL REFERENCES tenants(tenant_id),
  client_id        UUID NOT NULL REFERENCES clients(client_id),
  portfolio_ref    TEXT UNIQUE NOT NULL,
  display_name     TEXT NOT NULL,
  base_currency    TEXT NOT NULL DEFAULT 'CHF',
  valuation_date   DATE,
  total_nav_chf    NUMERIC(18,2),
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  source_file_path TEXT,
  last_uploaded_at TIMESTAMPTZ,
  last_uploaded_by UUID REFERENCES users(user_id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_portfolios_client ON portfolios(client_id);
CREATE INDEX IF NOT EXISTS idx_portfolios_tenant ON portfolios(tenant_id);

-- ── PORTFOLIO POSITIONS ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_positions (
  position_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id        UUID NOT NULL REFERENCES tenants(tenant_id),
  portfolio_id     UUID NOT NULL REFERENCES portfolios(portfolio_id),
  asset_symbol     TEXT NOT NULL,
  asset_name       TEXT,
  asset_class      asset_class NOT NULL,
  quantity         NUMERIC(28,10) NOT NULL,
  cost_basis_chf   NUMERIC(18,2),
  market_value_chf NUMERIC(18,2),
  weight_pct       NUMERIC(6,4),
  custodian_id     UUID REFERENCES counterparties(counterparty_id),
  custodian_name   TEXT,
  exchange_id      UUID REFERENCES counterparties(counterparty_id),
  exchange_name    TEXT,
  chain            TEXT,
  contract_address TEXT,
  raw_row          JSONB,
  as_of_date       DATE NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pos_portfolio ON portfolio_positions(portfolio_id, as_of_date DESC);
CREATE INDEX IF NOT EXISTS idx_pos_custodian ON portfolio_positions(custodian_id);

-- ── PORTFOLIO METRICS ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_metrics (
  metric_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id            UUID NOT NULL REFERENCES tenants(tenant_id),
  portfolio_id         UUID NOT NULL REFERENCES portfolios(portfolio_id),
  computed_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  as_of_date           DATE NOT NULL,
  var_95_1d            NUMERIC(18,2),
  var_99_1d            NUMERIC(18,2),
  cvar_95_1d           NUMERIC(18,2),
  cvar_99_1d           NUMERIC(18,2),
  return_30d           NUMERIC(8,4),
  return_90d           NUMERIC(8,4),
  max_drawdown_30d     NUMERIC(8,4),
  max_drawdown_90d     NUMERIC(8,4),
  sharpe_ratio_30d     NUMERIC(8,4),
  volatility_30d       NUMERIC(8,4),
  volatility_90d       NUMERIC(8,4),
  hhi                  NUMERIC(8,4),
  top1_weight          NUMERIC(6,4),
  top3_weight          NUMERIC(6,4),
  top5_weight          NUMERIC(6,4),
  custodian_hhi        NUMERIC(8,4),
  top_custodian_name   TEXT,
  top_custodian_pct    NUMERIC(6,4),
  illiquid_pct         NUMERIC(6,4),
  risk_score_composite NUMERIC(5,2),
  risk_tier            risk_tier,
  metrics_detail       JSONB NOT NULL DEFAULT '{}',
  agent_run_id         UUID,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pm_portfolio ON portfolio_metrics(portfolio_id, computed_at DESC);

-- ── STRESS SCENARIOS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stress_scenarios (
  scenario_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id    UUID NOT NULL REFERENCES tenants(tenant_id),
  slug         TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  description  TEXT,
  shocks       JSONB NOT NULL,
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  is_system    BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── STRESS TEST RESULTS ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS stress_test_results (
  result_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id            UUID NOT NULL REFERENCES tenants(tenant_id),
  portfolio_id         UUID NOT NULL REFERENCES portfolios(portfolio_id),
  scenario_id          UUID NOT NULL REFERENCES stress_scenarios(scenario_id),
  run_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  as_of_date           DATE NOT NULL,
  portfolio_pnl_chf    NUMERIC(18,2),
  portfolio_pnl_pct    NUMERIC(8,4),
  pre_shock_nav_chf    NUMERIC(18,2),
  post_shock_nav_chf   NUMERIC(18,2),
  position_impacts     JSONB NOT NULL DEFAULT '[]',
  worst_positions      JSONB NOT NULL DEFAULT '[]',
  counterparty_impacts JSONB NOT NULL DEFAULT '[]',
  summary_text         TEXT,
  agent_run_id         UUID,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stress_portfolio ON stress_test_results(portfolio_id, run_at DESC);

-- ── REPORTS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
  report_id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id                     UUID NOT NULL REFERENCES tenants(tenant_id),
  client_id                     UUID NOT NULL REFERENCES clients(client_id),
  portfolio_id                  UUID NOT NULL REFERENCES portfolios(portfolio_id),
  report_ref                    TEXT UNIQUE NOT NULL,
  title                         TEXT NOT NULL,
  report_period                 TEXT NOT NULL,
  status                        report_status NOT NULL DEFAULT 'DRAFT',
  agent_run_id                  UUID,
  model_version                 TEXT,
  generation_started_at         TIMESTAMPTZ,
  generation_completed_at       TIMESTAMPTZ,
  generation_error              TEXT,
  section_executive_summary     JSONB,
  section_portfolio_composition JSONB,
  section_risk_scorecard        JSONB,
  section_counterparty_analysis JSONB,
  section_stress_test_results   JSONB,
  section_recommendations       JSONB,
  assigned_reviewer             UUID REFERENCES users(user_id),
  review_started_at             TIMESTAMPTZ,
  review_completed_at           TIMESTAMPTZ,
  reviewer_notes                TEXT,
  approved_by                   UUID REFERENCES users(user_id),
  approved_at                   TIMESTAMPTZ,
  delivered_by                  UUID REFERENCES users(user_id),
  delivered_at                  TIMESTAMPTZ,
  delivery_channel              TEXT,
  delivery_note                 TEXT,
  pdf_path                      TEXT,
  pdf_generated_at              TIMESTAMPTZ,
  pdf_page_count                INT,
  data_snapshot_ids             JSONB NOT NULL DEFAULT '{}',
  created_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reports_tenant ON reports(tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_client ON reports(client_id, created_at DESC);

-- ── AUDIT LOG (IMMUTABLE) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
  log_id           BIGSERIAL PRIMARY KEY,
  tenant_id        UUID NOT NULL REFERENCES tenants(tenant_id),
  event_ts         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  event_category   event_category NOT NULL,
  event_type       TEXT NOT NULL,
  actor_type       actor_type NOT NULL,
  actor_id         UUID,
  actor_ip         INET,
  actor_user_agent TEXT,
  resource_type    TEXT,
  resource_id      UUID,
  before_state     JSONB,
  after_state      JSONB,
  metadata         JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant   ON audit_log(tenant_id, event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor    ON audit_log(actor_id, event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id, event_ts DESC);

CREATE OR REPLACE FUNCTION audit_log_immutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'audit_log is immutable'; END;
$$;
DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log;
CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log;
CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();

-- ── MARKET SNAPSHOTS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_snapshots (
  snapshot_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  asset_symbol     TEXT NOT NULL,
  source           TEXT NOT NULL,
  price_usd        NUMERIC(28,10),
  price_chf        NUMERIC(28,10),
  volume_24h_usd   NUMERIC(28,2),
  market_cap_usd   NUMERIC(28,2),
  price_change_24h NUMERIC(8,4),
  price_change_7d  NUMERIC(8,4),
  price_change_30d NUMERIC(8,4),
  raw_response     JSONB,
  snapshot_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_snapshots_symbol ON market_snapshots(asset_symbol, snapshot_at DESC);

-- ── AUTO updated_at ───────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

DO $$ DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['tenants','users','counterparties','alerts','clients','portfolios','reports'] LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_updated ON %s', t, t);
    EXECUTE format('CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
  END LOOP;
END $$;

-- ── ROW LEVEL SECURITY ────────────────────────────────────────
ALTER TABLE tenants             ENABLE ROW LEVEL SECURITY;
ALTER TABLE users               ENABLE ROW LEVEL SECURITY;
ALTER TABLE counterparties      ENABLE ROW LEVEL SECURITY;
ALTER TABLE counterparty_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE score_overrides     ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts              ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients             ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolios          ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_metrics   ENABLE ROW LEVEL SECURITY;
ALTER TABLE stress_scenarios    ENABLE ROW LEVEL SECURITY;
ALTER TABLE stress_test_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports             ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log           ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_snapshots    ENABLE ROW LEVEL SECURITY;

-- Drop all existing policies first
DO $$ DECLARE r RECORD;
BEGIN
  FOR r IN SELECT policyname, tablename FROM pg_policies WHERE schemaname = 'public' LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', r.policyname, r.tablename);
  END LOOP;
END $$;

-- Helper function for tenant isolation
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS UUID LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT tenant_id FROM users WHERE auth_id = auth.uid() LIMIT 1;
$$;

-- RLS Policies (unique names per table)
CREATE POLICY rls_counterparties      ON counterparties      FOR ALL USING (tenant_id = current_tenant_id());
CREATE POLICY rls_cp_scores           ON counterparty_scores FOR ALL USING (tenant_id = current_tenant_id());
CREATE POLICY rls_score_overrides     ON score_overrides     FOR ALL USING (tenant_id = current_tenant_id());
CREATE POLICY rls_alerts              ON alerts              FOR ALL USING (tenant_id = current_tenant_id());
CREATE POLICY rls_clients             ON clients             FOR ALL USING (tenant_id = current_tenant_id());
CREATE POLICY rls_portfolios          ON portfolios          FOR ALL USING (tenant_id = current_tenant_id());
CREATE POLICY rls_positions           ON portfolio_positions FOR ALL USING (tenant_id = current_tenant_id());
CREATE POLICY rls_metrics             ON portfolio_metrics   FOR ALL USING (tenant_id = current_tenant_id());
CREATE POLICY rls_scenarios           ON stress_scenarios    FOR ALL USING (tenant_id = current_tenant_id());
CREATE POLICY rls_stress_results      ON stress_test_results FOR ALL USING (tenant_id = current_tenant_id());
CREATE POLICY rls_reports             ON reports             FOR ALL USING (tenant_id = current_tenant_id());
CREATE POLICY rls_audit_read          ON audit_log           FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY rls_market_snapshots    ON market_snapshots    FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY rls_users               ON users               FOR ALL USING (
  auth_id = auth.uid()
  OR (SELECT role FROM users WHERE auth_id = auth.uid() LIMIT 1) IN ('admin','senior_analyst')
);

-- ── DONE ──────────────────────────────────────────────────────
DO $$
DECLARE tbl_count INT;
BEGIN
  SELECT COUNT(*) INTO tbl_count FROM information_schema.tables
  WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
  RAISE NOTICE '✅ Raven schema v1.1 complete. % tables ready.', tbl_count;
END $$;
