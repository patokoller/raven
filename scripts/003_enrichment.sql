-- ============================================================
-- RAVEN — Migration: Counterparty Enrichment Data
-- Run in Supabase SQL Editor
-- ============================================================

-- Add enrichment_data column to store manually input signal data
ALTER TABLE counterparties
  ADD COLUMN IF NOT EXISTS enrichment_data JSONB NOT NULL DEFAULT '{}';

-- Add last_enriched_at for tracking when data was last updated
ALTER TABLE counterparties
  ADD COLUMN IF NOT EXISTS last_enriched_at TIMESTAMPTZ;

ALTER TABLE counterparties
  ADD COLUMN IF NOT EXISTS last_enriched_by UUID REFERENCES users(user_id);

-- Index for querying enriched vs unenriched counterparties
CREATE INDEX IF NOT EXISTS idx_cp_enriched
  ON counterparties((enrichment_data != '{}'));

-- Verify
SELECT
  counterparty_id,
  display_name,
  enrichment_data,
  last_enriched_at
FROM counterparties
LIMIT 3;
