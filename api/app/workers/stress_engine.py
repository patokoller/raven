"""
Raven — Stress Test Engine

Applies scenario shocks to portfolio positions and computes P&L impact.

Scenario types:
1. Asset-level shocks: symbol → price change %
2. Asset-class shocks: crypto/equity/fixed_income/etc → uniform shock
3. Custodian haircut: positions at specific custodian → loss %
4. Macro factor shocks: applies factor models to correlated assets

The engine is asset-class aware — equities, ETFs, fixed income,
stablecoins, and crypto are treated differently under each scenario.
"""

from datetime import date, datetime
from typing import Optional
from app.core.database import supabase
from app.core.config import settings


# ── Scenario shock library ─────────────────────────────────────

SCENARIOS = [
    # ── CRYPTO SCENARIOS ──────────────────────────────────────
    {
        "slug":         "btc_crash_60",
        "display_name": "BTC Crash −60%",
        "category":     "crypto",
        "description":  "Severe Bitcoin correction (May 2021 / June 2022 redux). All crypto correlated downward. Stablecoins hold. Equities mildly affected via risk-off.",
        "shocks": {
            "__asset_class": {
                "crypto":       -0.55,
                "stablecoin":   -0.002,
                "equity":       -0.05,
                "etf":          -0.04,
                "fixed_income": -0.01,
            },
            "__symbol_override": {
                "BTC":  -0.60, "WBTC": -0.60,
                "ETH":  -0.65, "WETH": -0.65,
                "SOL":  -0.75, "BNB":  -0.60,
                "ADA":  -0.70, "AVAX": -0.75,
                "LINK": -0.65, "UNI":  -0.70,
                "AAVE": -0.70, "COMP": -0.70,
            },
        },
    },
    {
        "slug":         "stablecoin_depeg",
        "display_name": "Stablecoin Depeg",
        "category":     "crypto",
        "description":  "Major stablecoin loses peg (USDT −15%). Crypto markets panic-sell. Equities unaffected. DeFi protocols collapse.",
        "shocks": {
            "__asset_class": {
                "crypto":     -0.22,
                "stablecoin": -0.12,
                "equity":     -0.02,
            },
            "__symbol_override": {
                "USDT": -0.15, "USDC": -0.08, "DAI": -0.06,
                "BUSD": -0.15, "TUSD": -0.10,
                "BTC":  -0.20, "ETH":  -0.25,
                "AAVE": -0.45, "UNI":  -0.40,
            },
        },
    },
    {
        "slug":         "exchange_insolvency",
        "display_name": "Exchange Insolvency (FTX Scenario)",
        "category":     "crypto",
        "description":  "Primary exchange becomes insolvent. Assets held on that exchange are frozen/lost. Broad crypto contagion as confidence collapses.",
        "shocks": {
            "__custodian_type": "exchange",
            "__custodian_haircut": 0.85,  # 85% loss on exchange-held assets
            "__asset_class": {
                "crypto":     -0.40,
                "stablecoin": -0.05,
                "equity":     -0.03,
            },
        },
    },
    {
        "slug":         "crypto_regulatory_ban",
        "display_name": "Crypto Regulatory Ban",
        "category":     "crypto",
        "description":  "Major jurisdiction (US or EU) bans crypto trading/custody. Broad sell-off. DeFi and CeFi both impacted. TradFi slightly positive (rotation).",
        "shocks": {
            "__asset_class": {
                "crypto":       -0.50,
                "stablecoin":   -0.08,
                "equity":       -0.01,
                "etf":          -0.01,
                "fixed_income":  0.01,
            },
            "__symbol_override": {
                "BTC":  -0.50, "ETH":  -0.55,
                "AAVE": -0.65, "UNI":  -0.60,
                "SOL":  -0.65, "BNB":  -0.45,
            },
        },
    },
    {
        "slug":         "custodian_insolvency",
        "display_name": "Custodian Insolvency",
        "category":     "crypto",
        "description":  "Primary custodian (non-exchange) becomes insolvent. Assets in custody at risk. Partial recovery assumed under bankruptcy law.",
        "shocks": {
            "__custodian_type": "custodian",
            "__custodian_haircut": 0.40,  # 40% loss (partial recovery in bankruptcy)
            "__asset_class": {
                "crypto":     -0.20,
                "stablecoin": -0.02,
                "equity":     -0.02,
            },
        },
    },

    # ── MACRO / RATE SCENARIOS ────────────────────────────────
    {
        "slug":         "rate_shock_300bps",
        "display_name": "Rate Shock +300bps",
        "category":     "macro",
        "description":  "Emergency central bank rate hike +300bps. Duration risk hits fixed income hard. Growth equities sell off. Value/financials outperform. Crypto down.",
        "shocks": {
            "__asset_class": {
                "crypto":       -0.35,
                "stablecoin":   -0.002,
                "equity":       -0.15,
                "etf":          -0.12,
                "fixed_income": -0.18,
                "fund":         -0.10,
            },
            "__symbol_override": {
                # Growth equities hit harder
                "NVDA": -0.28, "GOOGL": -0.22, "AMZN": -0.25,
                "AAPL": -0.18, "MSFT":  -0.20,
                # ETFs
                "QQQ":  -0.25, "SPY":   -0.15, "IWM":  -0.18,
                # Financials outperform
                "JPM":   0.05, "BLK":    0.02, "GS":    0.04,
                # Crypto
                "BTC":  -0.35, "ETH":   -0.40,
                # Bonds crushed
                "TLT":  -0.25, "IEF":   -0.14, "SHY":  -0.05,
            },
        },
    },
    {
        "slug":         "recession_2008",
        "display_name": "Recession 2008-Style",
        "category":     "macro",
        "description":  "Global financial crisis scenario. Equities −40%, credit collapse, liquidity drought. Risk-off across all asset classes. Correlations converge to 1.",
        "shocks": {
            "__asset_class": {
                "crypto":       -0.70,
                "stablecoin":   -0.005,
                "equity":       -0.40,
                "etf":          -0.38,
                "fixed_income": -0.08,
                "fund":         -0.35,
                "commodity":    -0.30,
            },
            "__symbol_override": {
                "BTC":  -0.70, "ETH":  -0.75,
                "SPY":  -0.40, "QQQ":  -0.48, "IWM":  -0.50,
                "NVDA": -0.55, "GOOGL": -0.45, "AMZN": -0.50,
                "AAPL": -0.40, "MSFT":  -0.42,
                "JPM":  -0.65, "GS":   -0.60, "BLK":  -0.55,
                # Flight to safety
                "TLT":   0.20, "GLD":   0.15, "SHY":   0.05,
            },
        },
    },
    {
        "slug":         "stagflation",
        "display_name": "Stagflation Shock",
        "category":     "macro",
        "description":  "1970s-style stagflation: high inflation + recession. Equities and bonds both fall. Commodities and real assets hold. Crypto ambiguous.",
        "shocks": {
            "__asset_class": {
                "crypto":       -0.40,
                "stablecoin":   -0.005,
                "equity":       -0.25,
                "etf":          -0.22,
                "fixed_income": -0.15,
                "commodity":     0.25,
            },
            "__symbol_override": {
                "BTC":  -0.40, "ETH":  -0.45,
                "SPY":  -0.25, "QQQ":  -0.35,
                "NVDA": -0.38, "GOOGL": -0.30, "AMZN": -0.28,
                "AAPL": -0.22, "JPM":  -0.20, "BLK":  -0.18,
                "TLT":  -0.20, "IEF":  -0.12,
                "GLD":   0.30, "SLV":   0.25,
            },
        },
    },
    {
        "slug":         "chf_shock_20pct",
        "display_name": "Swiss Franc Shock +20%",
        "category":     "macro",
        "description":  "SNB removes EUR/CHF floor (2015 redux). CHF appreciates 20%. All non-CHF assets lose 20% in CHF terms. Swiss exporters collapse.",
        "shocks": {
            "__fx_chf_appreciation": 0.20,  # 20% CHF appreciation = 20% loss on all non-CHF assets
            "__asset_class": {
                "crypto":       -0.20,  # USD-denominated assets
                "equity":       -0.20,  # USD-denominated
                "etf":          -0.20,
                "fixed_income": -0.20,
                "stablecoin":   -0.20,  # USD stablecoins
            },
            "__symbol_override": {
                # Swiss equities also hit (export competitiveness)
                "NESN": -0.12, "NOVN": -0.08, "ROG": -0.10,
            },
        },
    },

    # ── EQUITY SCENARIOS ──────────────────────────────────────
    {
        "slug":         "tech_selloff_35pct",
        "display_name": "Tech Selloff −35%",
        "category":     "equity",
        "description":  "2022-style tech selloff. Growth/momentum stocks collapse as rates rise and AI hype fades. Value and dividend stocks outperform.",
        "shocks": {
            "__asset_class": {
                "equity":       -0.20,
                "etf":          -0.18,
                "crypto":       -0.30,
                "stablecoin":    0.0,
                "fixed_income": -0.05,
            },
            "__symbol_override": {
                # Tech/growth hit hardest
                "NVDA": -0.55, "GOOGL": -0.40, "AMZN": -0.42,
                "AAPL": -0.35, "MSFT":  -0.38, "META": -0.50,
                "TSLA": -0.60, "NFLX":  -0.50,
                # Tech ETFs
                "QQQ":  -0.38, "XLK":   -0.40,
                # Broad market less affected
                "SPY":  -0.22, "IWM":   -0.25, "DIA":  -0.15,
                # Value outperforms
                "BLK":  -0.10, "JPM":   -0.08, "XOM":   0.05,
                # Crypto correlated
                "BTC":  -0.30, "ETH":   -0.35, "AAVE": -0.50,
            },
        },
    },
    {
        "slug":         "ai_bubble_burst",
        "display_name": "AI Bubble Burst",
        "category":     "equity",
        "description":  "AI/semiconductor hype collapses. NVDA and AI-exposed stocks crash −60%+. Broad tech down. Value stocks and defensive sectors mildly positive.",
        "shocks": {
            "__asset_class": {
                "equity":  -0.08,
                "etf":     -0.10,
                "crypto":  -0.25,  # crypto/AI narrative link
                "stablecoin": 0.0,
            },
            "__symbol_override": {
                "NVDA": -0.65, "AMD":   -0.55, "INTC":  -0.30,
                "GOOGL": -0.35, "MSFT": -0.28, "AMZN": -0.25,
                "AAPL": -0.18, "META": -0.40,
                "QQQ":  -0.28, "XLK":  -0.30, "SOXX": -0.50,
                "SPY":  -0.12, "DIA":  -0.05,
                # Defensives outperform
                "XLU":   0.05, "XLP":   0.04, "GLD":   0.08,
                "BTC":  -0.25, "ETH":   -0.28,
            },
        },
    },
    {
        "slug":         "equity_crash_30pct",
        "display_name": "Equity Market Crash −30%",
        "category":     "equity",
        "description":  "Broad equity market crash. All equities and ETFs down 30%+. Similar to Q4 2018 or COVID March 2020. Bonds rally as flight to safety.",
        "shocks": {
            "__asset_class": {
                "equity":       -0.30,
                "etf":          -0.28,
                "crypto":       -0.50,
                "stablecoin":   -0.002,
                "fixed_income":  0.08,  # flight to safety
                "fund":         -0.25,
            },
            "__symbol_override": {
                "SPY":  -0.30, "QQQ":   -0.35, "IWM":  -0.38,
                "DIA":  -0.28, "VTI":   -0.30,
                "NVDA": -0.40, "GOOGL": -0.32, "AMZN": -0.35,
                "AAPL": -0.28, "MSFT":  -0.30, "JPM":  -0.35,
                "BLK":  -0.32, "GS":    -0.38,
                "TLT":   0.15, "GLD":    0.10, "SHY":   0.04,
                "BTC":  -0.50, "ETH":   -0.55,
            },
        },
    },

    # ── GEOPOLITICAL / TAIL SCENARIOS ─────────────────────────
    {
        "slug":         "liquidity_crisis",
        "display_name": "Liquidity Crisis",
        "category":     "tail",
        "description":  "Sudden market liquidity collapse. Bid/ask spreads blow out. Correlations converge to 1. Forced selling across all asset classes. Similar to March 2020.",
        "shocks": {
            "__asset_class": {
                "crypto":       -0.60,
                "stablecoin":   -0.03,
                "equity":       -0.35,
                "etf":          -0.33,
                "fixed_income": -0.12,
                "fund":         -0.30,
            },
            "__liquidity_discount": 0.05,  # additional 5% illiquidity haircut
        },
    },
    {
        "slug":         "geopolitical_black_swan",
        "display_name": "Geopolitical Black Swan",
        "category":     "tail",
        "description":  "Major geopolitical shock — energy crisis, sanctions escalation, or military conflict. Energy commodities +50%. Broad risk-off. Supply chain disruption.",
        "shocks": {
            "__asset_class": {
                "crypto":       -0.45,
                "equity":       -0.20,
                "etf":          -0.18,
                "fixed_income": -0.08,
                "stablecoin":   -0.002,
                "commodity":     0.40,
            },
            "__symbol_override": {
                "BTC":  -0.45, "ETH":   -0.50,
                "SPY":  -0.20, "QQQ":   -0.25,
                "NVDA": -0.25, "GOOGL": -0.22, "AMZN": -0.18,
                "XOM":   0.30, "CVX":    0.28, "GLD":   0.20,
                "TLT":  -0.05, "SHY":    0.02,
                "JPM":  -0.15, "BLK":   -0.18,
            },
        },
    },
]


def apply_shock(positions: list, scenario: dict) -> dict:
    """
    Apply scenario shocks to a list of positions.
    Returns P&L impact per position and totals.
    """
    shocks   = scenario.get("shocks", {})
    class_shocks    = shocks.get("__asset_class", {})
    symbol_overrides = shocks.get("__symbol_override", {})
    custodian_type  = shocks.get("__custodian_type")  # 'exchange' or 'custodian'
    custodian_haircut = shocks.get("__custodian_haircut", 0)
    fx_chf_appreciation = shocks.get("__fx_chf_appreciation", 0)
    liquidity_discount  = shocks.get("__liquidity_discount", 0)

    position_impacts = []
    total_pnl   = 0.0
    pre_nav     = 0.0

    # Load custodian entity types if we need them for custodian_type filter
    custodian_types_cache = {}

    for pos in positions:
        symbol      = (pos.get("asset_symbol") or "").upper()
        asset_class = (pos.get("asset_class") or "crypto").lower()
        value       = float(pos.get("market_value_chf") or 0)
        custodian   = pos.get("custodian_name") or pos.get("custodian_id", "")
        pre_nav    += value

        # Determine base shock
        shock = 0.0

        # 1. Symbol-level override (highest priority)
        if symbol in symbol_overrides:
            shock = symbol_overrides[symbol]
        # 2. Asset class shock
        elif asset_class in class_shocks:
            shock = class_shocks[asset_class]

        # 3. FX appreciation haircut (additional to asset-level shock)
        if fx_chf_appreciation > 0:
            fx_shock = class_shocks.get(asset_class, 0)
            shock = fx_shock  # override with FX-adjusted shock

        # 4. Custodian haircut (applied ON TOP of market shock)
        custodian_shock = 0.0
        if custodian_type and custodian_haircut:
            # Load custodian entity type
            cp_id = pos.get("custodian_id")
            if cp_id and cp_id not in custodian_types_cache:
                cp_row = (
                    supabase.table("counterparties")
                    .select("entity_type")
                    .eq("counterparty_id", cp_id)
                    .execute()
                    .data
                )
                custodian_types_cache[cp_id] = (cp_row[0]["entity_type"] if cp_row else "custodian")

            cp_type = custodian_types_cache.get(cp_id, "custodian")
            if cp_type == custodian_type:
                custodian_shock = -custodian_haircut

        # 5. Liquidity discount
        if liquidity_discount:
            shock = shock - liquidity_discount

        # Combined shock
        total_shock = shock + custodian_shock
        pnl         = value * total_shock

        position_impacts.append({
            "asset_symbol": symbol,
            "asset_class":  asset_class,
            "custodian":    custodian,
            "pre_value_chf": round(value, 2),
            "shock_pct":    round(total_shock * 100, 2),
            "pnl_chf":      round(pnl, 2),
            "post_value_chf": round(value + pnl, 2),
        })
        total_pnl += pnl

    post_nav  = pre_nav + total_pnl
    pnl_pct   = total_pnl / pre_nav if pre_nav else 0

    # Worst positions by absolute P&L
    worst = sorted(position_impacts, key=lambda x: x["pnl_chf"])[:5]

    return {
        "pre_nav_chf":    round(pre_nav, 2),
        "post_nav_chf":   round(post_nav, 2),
        "pnl_chf":        round(total_pnl, 2),
        "pnl_pct":        round(pnl_pct * 100, 2),
        "position_impacts": position_impacts,
        "worst_positions":  worst,
    }


def run_stress_test(portfolio_id: str, scenario_id: str) -> dict:
    """
    Run a stress test. scenario_id can be either:
    - A slug string like "btc_crash_60" (built-in scenario)
    - A UUID string (DB scenario)
    """
    # ── Step 1: Load positions ────────────────────────────────
    positions = (
        supabase.table("portfolio_positions")
        .select("asset_symbol, asset_class, market_value_chf, custodian_id, custodian_name")
        .eq("portfolio_id", portfolio_id)
        .execute()
        .data
    ) or []

    if not positions:
        return {"error": "No positions found for this portfolio"}

    portfolio = (
        supabase.table("portfolios")
        .select("portfolio_id, display_name, total_nav_chf, valuation_date")
        .eq("portfolio_id", portfolio_id)
        .single()
        .execute()
        .data
    )

    # ── Step 2: Find the scenario ─────────────────────────────
    # Priority: built-in SCENARIOS library (by slug) → DB (by UUID or slug)
    scenario = next((s for s in SCENARIOS if s["slug"] == scenario_id), None)

    if scenario is None:
        # Not a built-in slug — try DB
        import re as _re
        _is_uuid = bool(_re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            str(scenario_id), _re.I
        ))
        try:
            if _is_uuid:
                row = (supabase.table("stress_scenarios")
                       .select("*").eq("scenario_id", scenario_id)
                       .single().execute().data)
            else:
                rows = (supabase.table("stress_scenarios")
                        .select("*").eq("slug", scenario_id)
                        .execute().data)
                row = rows[0] if rows else None

            if row:
                shocks = row.get("shocks", {})
                if not any(k.startswith("__") for k in shocks.keys()):
                    shocks = {
                        "__symbol_override": shocks,
                        "__asset_class": {
                            "crypto": -0.30, "stablecoin": -0.02, "equity": -0.05
                        }
                    }
                scenario = {
                    "slug":         row["slug"],
                    "display_name": row["display_name"],
                    "shocks":       shocks,
                }
        except Exception as e:
            print(f"[stress] DB scenario lookup failed: {e}")

    if scenario is None:
        return {"error": f"Scenario '{scenario_id}' not found"}

    # ── Step 3: Apply shocks ──────────────────────────────────
    result = apply_shock(positions, scenario)

    # ── Step 4: Resolve DB UUID for storage (best-effort) ─────
    db_scenario_id = None
    try:
        rows = (supabase.table("stress_scenarios")
                .select("scenario_id")
                .eq("slug", scenario["slug"])
                .execute().data)
        db_scenario_id = rows[0]["scenario_id"] if rows else None
    except Exception as e:
        print(f"[stress] UUID resolution skipped: {e}")

    # ── Step 5: Store result (best-effort) ────────────────────
    as_of = (portfolio or {}).get("valuation_date") or date.today().isoformat()
    if db_scenario_id:
        try:
            stored = supabase.table("stress_test_results").insert({
                "tenant_id":            settings.DEFAULT_TENANT_ID,
                "portfolio_id":         portfolio_id,
                "scenario_id":          db_scenario_id,
                "as_of_date":           as_of,
                "portfolio_pnl_chf":    result["pnl_chf"],
                "portfolio_pnl_pct":    result["pnl_pct"] / 100,
                "pre_shock_nav_chf":    result["pre_nav_chf"],
                "post_shock_nav_chf":   result["post_nav_chf"],
                "position_impacts":     result["position_impacts"],
                "worst_positions":      result["worst_positions"],
                "counterparty_impacts": [],
                "summary_text":         scenario["display_name"] + ": " + str(round(result["pnl_pct"], 1)) + "%",
            }).execute()
            result["result_id"]  = stored.data[0]["result_id"]
            result["scenario_id"] = db_scenario_id
        except Exception as e:
            print(f"[stress] Store skipped: {e}")
            result["scenario_id"] = scenario_id
    else:
        result["scenario_id"] = scenario_id
        result["slug"]        = scenario["slug"]

    return result


def get_all_scenarios():
    """Return all scenarios including built-in library."""
    # DB scenarios
    db_scenarios = (
        supabase.table("stress_scenarios")
        .select("scenario_id, slug, display_name, description, is_system")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", True)
        .execute()
        .data
    ) or []

    # Built-in scenarios not in DB
    db_slugs = {s["slug"] for s in db_scenarios}
    builtin  = [s for s in SCENARIOS if s["slug"] not in db_slugs]

    # Return combined with category grouping
    combined = []
    for s in db_scenarios:
        combined.append({
            "scenario_id":  s["scenario_id"],
            "slug":         s["slug"],
            "display_name": s["display_name"],
            "description":  s.get("description", ""),
            "category":     _infer_category(s["slug"]),
            "source":       "db",
        })
    for s in builtin:
        combined.append({
            "scenario_id":  s["slug"],  # use slug as ID for built-ins
            "slug":         s["slug"],
            "display_name": s["display_name"],
            "description":  s.get("description", ""),
            "category":     s.get("category", "macro"),
            "source":       "builtin",
        })

    return combined


def _infer_category(slug: str) -> str:
    if any(k in slug for k in ["btc", "crypto", "stablecoin", "exchange", "custodian"]):
        return "crypto"
    if any(k in slug for k in ["rate", "recession", "stagflation", "chf"]):
        return "macro"
    if any(k in slug for k in ["tech", "equity", "ai", "bubble"]):
        return "equity"
    return "tail"
