-- ============================================================
-- RAVEN — Migration: Regulatory Intelligence Engine
-- Run in Supabase SQL Editor
-- ============================================================

CREATE TABLE IF NOT EXISTS regulatory_documents (
  doc_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id),

  -- Source
  source          TEXT NOT NULL,         -- 'finma' | 'fca' | 'sec' | 'bis' | 'manual'
  regulator       TEXT NOT NULL,         -- 'FINMA' | 'FCA' | 'SEC' | 'BIS'
  doc_type        TEXT NOT NULL,         -- 'guidance' | 'circular' | 'notice' | 'consultation'
  doc_ref         TEXT,                  -- e.g. 'FINMA Guidance 01/2026'
  title           TEXT NOT NULL,
  url             TEXT NOT NULL UNIQUE,
  published_date  DATE,
  language        TEXT DEFAULT 'en',

  -- Analysis
  status          TEXT NOT NULL DEFAULT 'new',
  -- 'new' | 'analysing' | 'analysed' | 'reviewed' | 'applied' | 'dismissed'

  -- Claude analysis output
  summary         TEXT,
  criticality     TEXT,    -- 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  affected_entity_types   TEXT[],
  affected_counterparties TEXT[],
  scoring_impacts JSONB,   -- dimension → suggested weight change
  recommended_actions     JSONB,
  full_analysis   JSONB,   -- complete structured analysis

  -- Review
  reviewed_by     UUID REFERENCES users(user_id),
  reviewed_at     TIMESTAMPTZ,
  applied_at      TIMESTAMPTZ,
  analyst_notes   TEXT,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_regdoc_source   ON regulatory_documents(source);
CREATE INDEX IF NOT EXISTS idx_regdoc_status   ON regulatory_documents(status);
CREATE INDEX IF NOT EXISTS idx_regdoc_crit     ON regulatory_documents(criticality);
CREATE INDEX IF NOT EXISTS idx_regdoc_date     ON regulatory_documents(published_date DESC);

-- Disable RLS for MVP
ALTER TABLE regulatory_documents DISABLE ROW LEVEL SECURITY;

SELECT 'regulatory_documents table created' as status;
