-- ============================================================
-- RAVEN — Counterparty Registry Seed Data
-- 25 entities: exchanges, custodians, OTC desks, DeFi protocols
-- Run AFTER 001_schema.sql
-- ============================================================

-- Stress test scenarios (5 pre-built MVP scenarios)
INSERT INTO stress_scenarios (tenant_id, slug, display_name, description, shocks, is_system) VALUES
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'btc_crash_60',
  'BTC Crash −60%',
  'Severe Bitcoin correction similar to May 2021 or June 2022. All crypto correlated downward.',
  '{
    "BTC": -0.60, "ETH": -0.65, "SOL": -0.75, "BNB": -0.60,
    "ADA": -0.70, "DOT": -0.70, "AVAX": -0.75, "MATIC": -0.75,
    "LINK": -0.65, "UNI": -0.70, "USDT": -0.001, "USDC": -0.001
  }',
  TRUE
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'stablecoin_depeg',
  'Stablecoin Depeg',
  'Major stablecoin loses peg (USDT or USDC −15%), contagion to crypto markets.',
  '{
    "USDT": -0.15, "USDC": -0.08, "DAI": -0.05, "BUSD": -0.12,
    "BTC": -0.20, "ETH": -0.25, "SOL": -0.30, "BNB": -0.20
  }',
  TRUE
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'custodian_insolvency',
  'Custodian Insolvency',
  'Primary custodian becomes insolvent (FTX-style event). Positions custodied there are at risk.',
  '{
    "__custodian_haircut": 1.00,
    "BTC": -0.15, "ETH": -0.18, "SOL": -0.30,
    "USDT": -0.05, "USDC": -0.03
  }',
  TRUE
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'rate_shock_300bps',
  'Rate Shock +300bps',
  'Central bank emergency rate hike +300bps. Risk-off across all assets.',
  '{
    "BTC": -0.35, "ETH": -0.38, "SOL": -0.45, "BNB": -0.35,
    "AAPL": -0.20, "MSFT": -0.18, "SPY": -0.22, "QQQ": -0.28,
    "USDT": 0.00, "USDC": 0.00, "USD": 0.00
  }',
  TRUE
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'crypto_regulatory_ban',
  'Crypto Regulatory Ban',
  'Major jurisdiction (EU or US) announces comprehensive crypto trading ban.',
  '{
    "BTC": -0.45, "ETH": -0.50, "SOL": -0.65, "BNB": -0.70,
    "ADA": -0.70, "DOT": -0.65, "AVAX": -0.70, "UNI": -0.80,
    "AAVE": -0.80, "USDT": -0.05, "USDC": -0.02
  }',
  TRUE
);

-- ============================================================
-- COUNTERPARTY REGISTRY — 25 entities
-- ============================================================

INSERT INTO counterparties (
  tenant_id, slug, display_name, legal_name, entity_type,
  jurisdiction, regulator, license_number, website, external_ids, notes
) VALUES

-- ─── TIER 1 EXCHANGES ───────────────────────────────────────
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'coinbase',
  'Coinbase',
  'Coinbase Global, Inc.',
  'exchange',
  'US', 'SEC/FINRA', 'NASDAQ: COIN',
  'https://www.coinbase.com',
  '{"lei": "5493006MWDIBKQP3UF07", "ticker": "COIN"}',
  'Publicly listed US exchange. Strong regulatory standing. Primary crypto on-ramp for institutional clients.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'kraken',
  'Kraken',
  'Payward, Inc.',
  'exchange',
  'US', 'FinCEN/multiple', NULL,
  'https://www.kraken.com',
  '{}',
  'One of the oldest crypto exchanges. Strong security track record. Never hacked. Pursuing US bank charter.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'binance',
  'Binance',
  'Binance Holdings Limited',
  'exchange',
  'KY', 'Multiple/contested', NULL,
  'https://www.binance.com',
  '{}',
  'Largest exchange by volume. Regulatory challenges in US/EU. High liquidity. Jurisdiction risk elevated.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'bitstamp',
  'Bitstamp',
  'Bitstamp Ltd.',
  'exchange',
  'LU', 'CSSF', NULL,
  'https://www.bitstamp.net',
  '{"lei": "2138007F7A7JO3MFHB79"}',
  'EU-regulated exchange. Luxembourg domicile. Strong compliance posture. Lower risk profile.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'lmax-digital',
  'LMAX Digital',
  'LMAX Digital Ltd.',
  'exchange',
  'GB', 'FCA', NULL,
  'https://www.lmaxdigital.com',
  '{}',
  'Institutional-grade crypto exchange. FCA regulated. Part of established LMAX Group. Low retail exposure.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'deribit',
  'Deribit',
  'Deribit B.V.',
  'exchange',
  'NL', 'DNB', NULL,
  'https://www.deribit.com',
  '{}',
  'Dominant crypto derivatives exchange. Options and futures. Netherlands registered.'
),

-- ─── CUSTODIANS ─────────────────────────────────────────────
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'fireblocks',
  'Fireblocks',
  'Fireblocks Ltd.',
  'custodian',
  'US', 'State regulators', NULL,
  'https://www.fireblocks.com',
  '{}',
  'Leading institutional custody and transfer network. MPC-based security. Used by 1800+ institutions.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'copper',
  'Copper',
  'Copper Technologies (UK) Ltd.',
  'custodian',
  'GB', 'FCA', NULL,
  'https://copper.co',
  '{}',
  'UK custodian with ClearLoop off-exchange settlement. FCA registered. Strong institutional focus.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'bitgo',
  'BitGo',
  'BitGo, Inc.',
  'custodian',
  'US', 'SDOB (SD Trust)', NULL,
  'https://www.bitgo.com',
  '{}',
  'One of the oldest qualified custodians. SOC 2 certified. Regulated trust company in South Dakota.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'anchorage-digital',
  'Anchorage Digital',
  'Anchorage Digital Bank N.A.',
  'custodian',
  'US', 'OCC', NULL,
  'https://www.anchorage.com',
  '{}',
  'First federally chartered crypto bank in the US (OCC charter). Strongest regulatory standing of any crypto custodian.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'taurus',
  'Taurus',
  'Taurus Group SA',
  'custodian',
  'CH', 'FINMA', NULL,
  'https://www.taurusgroup.ch',
  '{}',
  'Swiss-regulated digital asset custodian. FINMA supervised. Relevant for CHF-denominated mandates.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'metaco',
  'METACO',
  'METACO SA',
  'custodian',
  'CH', 'FINMA', NULL,
  'https://www.metaco.com',
  '{}',
  'Swiss digital asset management software and custody. Acquired by Ripple. Used by tier-1 banks.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'coinbase-custody',
  'Coinbase Custody',
  'Coinbase Custody Trust Company, LLC',
  'custodian',
  'US', 'NYDFS', NULL,
  'https://custody.coinbase.com',
  '{}',
  'Regulated NY trust company subsidiary of Coinbase. Separate legal entity. SOC 1 Type 2 certified.'
),

-- ─── OTC DESKS ──────────────────────────────────────────────
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'cumberland',
  'Cumberland DRW',
  'Cumberland DRW LLC',
  'otc_desk',
  'US', 'FinCEN', NULL,
  'https://www.cumberlandmining.com',
  '{}',
  'Subsidiary of DRW. One of the most established institutional crypto OTC desks. Strong credit.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'wintermute',
  'Wintermute',
  'Wintermute Trading Ltd.',
  'otc_desk',
  'GB', 'FCA', NULL,
  'https://www.wintermute.com',
  '{}',
  'Top-tier market maker and OTC desk. FCA regulated. Active in both CeFi and DeFi. High volume.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'galaxy-digital',
  'Galaxy Digital',
  'Galaxy Digital Trading LLC',
  'otc_desk',
  'US', 'CFTC/FinCEN', NULL,
  'https://www.galaxydigital.io',
  '{"ticker": "GLXY"}',
  'Publicly listed digital assets firm. OTC, lending, asset management. Strong institutional reputation.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'b2c2',
  'B2C2',
  'B2C2 Ltd.',
  'otc_desk',
  'GB', 'FCA', NULL,
  'https://www.b2c2.com',
  '{}',
  'Acquired by SBI Group. FCA regulated. Institutional OTC liquidity provider. Strong credit profile.'
),

-- ─── PRIME BROKERS / LENDERS ────────────────────────────────
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'falconx',
  'FalconX',
  'FalconX Limited',
  'prime_broker',
  'US', 'CFTC/State', NULL,
  'https://www.falconx.io',
  '{}',
  'Digital asset prime broker. Clearing, credit, and execution. Regulated across multiple jurisdictions.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'hidden-road',
  'Hidden Road',
  'Hidden Road Partners CIV LLC',
  'prime_broker',
  'US', 'SEC/FINRA', NULL,
  'https://www.hiddenroad.com',
  '{}',
  'Multi-asset prime broker including crypto. FINRA member. Acquired by Ripple 2025.'
),

-- ─── DEFI PROTOCOLS ─────────────────────────────────────────
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'aave',
  'Aave',
  'Aave Protocol (DAO)',
  'defi_protocol',
  NULL, 'None (DAO)', NULL,
  'https://aave.com',
  '{"governance": "AAVE token"}',
  'Leading DeFi lending protocol. $10B+ TVL. Battle-tested smart contracts. Multiple security audits.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'uniswap',
  'Uniswap',
  'Uniswap Protocol (DAO)',
  'defi_protocol',
  NULL, 'None (DAO)', NULL,
  'https://uniswap.org',
  '{"governance": "UNI token"}',
  'Largest DEX by volume. AMM model. Highly audited. Smart contract risk but strong track record.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'compound',
  'Compound',
  'Compound Protocol (DAO)',
  'defi_protocol',
  NULL, 'None (DAO)', NULL,
  'https://compound.finance',
  '{"governance": "COMP token"}',
  'Established DeFi lending protocol. Lower TVL growth vs Aave but strong audit history.'
),

-- ─── MARKET MAKERS ──────────────────────────────────────────
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'jump-crypto',
  'Jump Crypto',
  'Jump Crypto (div. of Jump Trading)',
  'market_maker',
  'US', 'CFTC/FinCEN', NULL,
  'https://jumpcrypto.com',
  '{}',
  'Division of established HFT firm Jump Trading. Large market maker. Regulatory scrutiny increased post-2022.'
),
(
  'aaaaaaaa-0000-0000-0000-000000000001',
  'gsrmarkets',
  'GSR Markets',
  'GSR Markets Limited',
  'market_maker',
  'SG', 'MAS', NULL,
  'https://www.gsr.io',
  '{}',
  'MAS-regulated market maker. Singapore domicile. Active in structured products and treasury management.'
);

-- ============================================================
-- Sample client and portfolio for demo/testing
-- ============================================================

INSERT INTO clients (tenant_id, client_ref, display_name, legal_name, domicile, risk_profile, aum_chf)
VALUES (
  'aaaaaaaa-0000-0000-0000-000000000001',
  'CLT-001',
  'Helvetic Capital AG',
  'Helvetic Capital AG',
  'CH',
  'moderate',
  45000000.00
);

-- ============================================================
-- Verify seed data
-- ============================================================

DO $$
DECLARE
  cp_count INT;
  scenario_count INT;
BEGIN
  SELECT COUNT(*) INTO cp_count FROM counterparties;
  SELECT COUNT(*) INTO scenario_count FROM stress_scenarios;
  RAISE NOTICE 'Seed complete: % counterparties, % stress scenarios', cp_count, scenario_count;
END $$;
