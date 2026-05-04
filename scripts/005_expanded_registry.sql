-- ============================================================
-- RAVEN — Migration: System Config + Expanded Counterparty Registry
-- Run in Supabase SQL Editor
-- ============================================================

-- System configuration table (for weights and other settings)
CREATE TABLE IF NOT EXISTS system_config (
  config_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id  UUID NOT NULL REFERENCES tenants(tenant_id),
  key        TEXT NOT NULL,
  value      JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_by UUID REFERENCES users(user_id),
  UNIQUE(tenant_id, key)
);

-- Insert default scoring weights
INSERT INTO system_config (tenant_id, key, value)
VALUES (
  'aaaaaaaa-0000-0000-0000-000000000001',
  'scoring_weights',
  '{"regulatory":0.25,"financial":0.20,"operational":0.20,"liquidity":0.15,"onchain":0.10,"reputation":0.10}'
) ON CONFLICT (tenant_id, key) DO NOTHING;

-- ── EXPANDED COUNTERPARTY REGISTRY ───────────────────────────
-- 16 additional entities: traditional finance, Swiss banks,
-- new exchanges, and Alpaca Markets

INSERT INTO counterparties (
  tenant_id, slug, display_name, legal_name, entity_type,
  jurisdiction, regulator, license_number, website, external_ids, notes
) VALUES

-- ─── TRADITIONAL FINANCE / PRIME BROKERS ────────────────────
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'goldman-sachs-digital',
  'Goldman Sachs Digital Assets',
  'Goldman Sachs & Co. LLC',
  'prime_broker',
  'US', 'SEC/FINRA/Fed', NULL,
  'https://www.goldmansachs.com',
  '{"ticker": "GS", "lei": "784F5XWPLTWKTBV3E584"}',
  'Tier 1 investment bank with digital asset division. Full prime brokerage services for crypto institutions. Federal Reserve supervised.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'jpmorgan-onyx',
  'JPMorgan Onyx',
  'JPMorgan Chase & Co.',
  'prime_broker',
  'US', 'OCC/Fed/SEC', NULL,
  'https://www.jpmorgan.com/onyx',
  '{"ticker": "JPM", "lei": "8I5DZWZKVSZI1NUHU748"}',
  'JPMorgan blockchain and digital asset division. Onyx platform for institutional settlement and tokenisation.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'bbva-digital',
  'BBVA Digital Assets',
  'Banco Bilbao Vizcaya Argentaria SA',
  'custodian',
  'ES', 'Banco de España/ECB', NULL,
  'https://www.bbva.com',
  '{"ticker": "BBVA"}',
  'Spanish bank with regulated digital asset custody services in Switzerland and Spain. FINMA-supervised Swiss subsidiary.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'alpaca-markets',
  'Alpaca Markets',
  'Alpaca Securities LLC',
  'exchange',
  'US', 'SEC/FINRA/SIPC', NULL,
  'https://alpaca.markets',
  '{"sipc_member": true}',
  'Commission-free trading API for equities and crypto. FINRA member, SIPC insured. Institutional API access. Used as equity data provider.'
),

-- ─── SWISS CRYPTO INSTITUTIONS ──────────────────────────────
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'sygnum',
  'Sygnum Bank',
  'Sygnum Bank AG',
  'custodian',
  'CH', 'FINMA', NULL,
  'https://www.sygnum.com',
  '{}',
  'First digital asset bank with FINMA banking licence. Dual domicile Switzerland/Singapore. Institutional-grade digital asset banking.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'seba-bank',
  'SEBA Bank',
  'SEBA Bank AG',
  'custodian',
  'CH', 'FINMA', NULL,
  'https://www.seba.swiss',
  '{}',
  'FINMA-licensed crypto bank. Full banking and securities dealer licence. Swiss domicile. Strong regulatory standing for CHF mandates.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'bitcoin-suisse',
  'Bitcoin Suisse',
  'Bitcoin Suisse AG',
  'custodian',
  'CH', 'FINMA', NULL,
  'https://www.bitcoinsuisse.com',
  '{}',
  'Pioneer Swiss crypto financial services firm. FINMA-regulated. Staking, custody, and brokerage. Long operating history since 2013.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'maerki-baumann',
  'Maerki Baumann',
  'Maerki Baumann & Co. AG',
  'custodian',
  'CH', 'FINMA', NULL,
  'https://www.maerki-baumann.ch',
  '{}',
  'Traditional Swiss private bank with regulated digital asset custody. Founded 1932. FINMA banking licence. Conservative institutional profile.'
),

-- ─── NEW EXCHANGES ───────────────────────────────────────────
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'okx',
  'OKX',
  'Aux Cayes FinTech Co. Ltd.',
  'exchange',
  'SC', 'Multiple/contested', NULL,
  'https://www.okx.com',
  '{}',
  'Third-largest global exchange by volume. Regulatory challenges in multiple jurisdictions. Seychelles domicile. High liquidity but elevated jurisdictional risk.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'bybit',
  'Bybit',
  'Bybit Fintech Limited',
  'exchange',
  'AE', 'Multiple', NULL,
  'https://www.bybit.com',
  '{}',
  'Large derivatives exchange. Dubai HQ post-relocation. Regulatory status improving but contested in several markets.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'cex-io',
  'CEX.IO',
  'CEX.IO Limited',
  'exchange',
  'GB', 'FCA', NULL,
  'https://cex.io',
  '{}',
  'UK-regulated exchange established 2013. FCA registered. Institutional services available. Mid-tier volume.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'gemini',
  'Gemini',
  'Gemini Trust Company, LLC',
  'exchange',
  'US', 'NYDFS', NULL,
  'https://www.gemini.com',
  '{}',
  'NYDFS-chartered trust company. Founded by Winklevoss twins. Strong US regulatory standing. SOC2 certified. Lower volume but high compliance.'
),

-- ─── LENDING / STRUCTURED PRODUCTS ──────────────────────────
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'ledn',
  'Ledn',
  'Ledn Inc.',
  'lender',
  'CA', 'FINTRAC', NULL,
  'https://www.ledn.io',
  '{}',
  'Bitcoin-backed lending platform. Canadian domicile. Monthly attestations by Marygold & Co. Focus on BTC-collateralised loans.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'maple-finance',
  'Maple Finance',
  'Maple Finance Protocol (DAO)',
  'lender',
  NULL, 'None (DAO)', NULL,
  'https://www.maple.finance',
  '{"governance": "MPL token"}',
  'Institutional DeFi lending protocol. Undercollateralised lending to institutions. Smart contract risk plus credit risk. Post-Orthogonal Trading default (2022) — monitor closely.'
),

-- ─── CLEARING / SETTLEMENT ───────────────────────────────────
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'clear-street',
  'Clear Street',
  'Clear Street LLC',
  'prime_broker',
  'US', 'SEC/FINRA', NULL,
  'https://clearstreet.io',
  '{}',
  'Modern prime brokerage built on cloud infrastructure. FINRA member. Growing institutional base. Equities and some crypto clearing.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'bitpanda-custody',
  'Bitpanda Custody',
  'Bitpanda GmbH',
  'custodian',
  'AT', 'FMA', NULL,
  'https://www.bitpanda.com/institutional',
  '{}',
  'Austrian regulated exchange and custody provider. FMA licensed. European institutional focus. Growing AuM under management.'
);

-- Verify final count
DO $$
DECLARE cp_count INT;
BEGIN
  SELECT COUNT(*) INTO cp_count FROM counterparties
  WHERE tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001';
  RAISE NOTICE '✓ Registry now contains % counterparties', cp_count;
END $$;
