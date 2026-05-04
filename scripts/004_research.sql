-- ============================================================
-- RAVEN — Migration: Counterparty Research Data
-- Run in Supabase SQL Editor
-- ============================================================

ALTER TABLE counterparties
  ADD COLUMN IF NOT EXISTS research_data   JSONB,
  ADD COLUMN IF NOT EXISTS research_status TEXT DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS last_researched_at TIMESTAMPTZ;

-- research_status values: 'none' | 'running' | 'complete' | 'error'

SELECT display_name, research_status FROM counterparties LIMIT 3;
