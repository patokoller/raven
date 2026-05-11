"""
Raven — Counterparties Router
"""

from typing import Optional, List
from uuid import UUID
import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.database import supabase
from app.core.config import settings
from app.core.auth import get_current_user, CurrentUser

router = APIRouter()


class ScoreOverrideRequest(BaseModel):
    dimension: str
    new_value: float
    rationale: str


@router.get("")
async def list_counterparties(
    entity_type: Optional[str] = Query(None),
    risk_tier: Optional[str] = Query(None),
    is_active: bool = Query(True),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all counterparties with their latest scores."""

    # Simple query — no complex joins that can fail
    q = (
        supabase.table("counterparties")
        .select(
            "counterparty_id,slug,display_name,entity_type,jurisdiction,"
            "regulator,current_risk_tier,latest_score_id,research_status,"
            "last_enriched_at,website,legal_name,is_active"
        )
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", is_active)
    )
    if entity_type:
        q = q.eq("entity_type", entity_type)
    if risk_tier:
        q = q.eq("current_risk_tier", risk_tier)

    # Check cache (30s TTL — reduces DB load on rapid page refreshes)
    from main import _cache_get, _cache_set
    cache_key = f"cp_list_{settings.DEFAULT_TENANT_ID}_{entity_type}_{risk_tier}_{is_active}"
    cached = _cache_get(cache_key, ttl=30)
    if cached is not None:
        return cached

    cps = q.order("display_name").execute().data

    # Fetch latest scores separately for counterparties that have them
    scored_ids = [cp["counterparty_id"] for cp in cps if cp.get("latest_score_id")]
    scores_by_cp = {}

    if scored_ids:
        score_ids = [cp["latest_score_id"] for cp in cps if cp.get("latest_score_id")]
        scores = (
            supabase.table("counterparty_scores")
            .select("score_id, counterparty_id, composite_score, regulatory_score, financial_score, operational_score, liquidity_score, onchain_score, reputation_score, score_delta_7d, score_delta_30d, scored_at")
            .in_("score_id", score_ids)
            .execute()
            .data
        )
        scores_by_cp = {s["score_id"]: s for s in scores}

    # Merge
    result = []
    for cp in cps:
        score = scores_by_cp.get(cp.get("latest_score_id"), {})
        result.append({
            "counterparty_id": cp["counterparty_id"],
            "slug": cp["slug"],
            "display_name": cp["display_name"],
            "entity_type": cp["entity_type"],
            "jurisdiction": cp.get("jurisdiction"),
            "regulator": cp.get("regulator"),
            "current_risk_tier": cp.get("current_risk_tier"),
            "is_active": cp["is_active"],
            "composite_score": score.get("composite_score"),
            "score_delta_7d": score.get("score_delta_7d"),
            "score_delta_30d": score.get("score_delta_30d"),
            "scored_at": score.get("scored_at"),
            "latest_score": score if score else None,
        })

    _cache_set(cache_key, result)
    return result


@router.get("/{counterparty_id}")
async def get_counterparty(
    counterparty_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    cp = (
        supabase.table("counterparties")
        .select("*")
        .eq("counterparty_id", str(counterparty_id))
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .single()
        .execute()
    )
    if not cp.data:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    if cp.data.get("latest_score_id"):
        score = (
            supabase.table("counterparty_scores")
            .select("*")
            .eq("score_id", cp.data["latest_score_id"])
            .single()
            .execute()
        )
        cp.data["latest_score"] = score.data

    return cp.data


@router.get("/{counterparty_id}/scores")
async def get_score_history(
    counterparty_id: UUID,
    days: int = Query(90, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
):
    from_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = (
        supabase.table("counterparty_scores")
        .select("score_id, scored_at, composite_score, risk_tier, regulatory_score, financial_score, operational_score, liquidity_score, onchain_score, reputation_score, score_delta_7d, score_delta_30d, is_overridden")
        .eq("counterparty_id", str(counterparty_id))
        .gte("scored_at", from_date)
        .order("scored_at", desc=False)
        .execute()
    )
    return {"counterparty_id": counterparty_id, "scores": result.data, "days": days}


@router.post("/{counterparty_id}/override")
async def override_score(
    counterparty_id: UUID,
    body: ScoreOverrideRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    valid_dimensions = ["regulatory", "financial", "operational", "liquidity", "onchain", "reputation"]
    if body.dimension not in valid_dimensions:
        raise HTTPException(status_code=400, detail=f"Dimension must be one of: {valid_dimensions}")
    if not 0 <= body.new_value <= 100:
        raise HTTPException(status_code=400, detail="Score must be 0–100")

    cp = (
        supabase.table("counterparties")
        .select("latest_score_id, display_name")
        .eq("counterparty_id", str(counterparty_id))
        .single()
        .execute()
    )
    if not cp.data or not cp.data.get("latest_score_id"):
        raise HTTPException(status_code=404, detail="No score exists yet for this counterparty")

    score_id = cp.data["latest_score_id"]
    current_score = (
        supabase.table("counterparty_scores")
        .select(f"{body.dimension}_score")
        .eq("score_id", score_id)
        .single()
        .execute()
    )
    original_value = current_score.data.get(f"{body.dimension}_score", 0)

    supabase.table("score_overrides").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "score_id": score_id,
        "counterparty_id": str(counterparty_id),
        "user_id": current_user.user_id,
        "dimension": body.dimension,
        "original_value": original_value,
        "override_value": body.new_value,
        "rationale": body.rationale,
    }).execute()

    supabase.table("counterparty_scores").update({
        f"{body.dimension}_score": body.new_value,
        "is_overridden": True,
        "override_by": current_user.user_id,
        "override_rationale": body.rationale,
        "override_at": datetime.utcnow().isoformat(),
    }).eq("score_id", score_id).execute()

    supabase.table("audit_log").insert({
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "event_category": "HUMAN_REVIEW",
        "event_type": "score.overridden",
        "actor_type": "USER",
        "actor_id": current_user.user_id,
        "resource_type": "counterparty_scores",
        "resource_id": score_id,
        "before_state": {body.dimension: original_value},
        "after_state": {body.dimension: body.new_value},
        "metadata": {"counterparty_id": str(counterparty_id), "rationale": body.rationale},
    }).execute()

    from app.workers.scoring import score_single_counterparty
    from app.workers.tasks import run_in_thread
    run_in_thread(score_single_counterparty, str(counterparty_id))

    return {"status": "override_applied", "dimension": body.dimension, "new_value": body.new_value}


# ── Enrichment data ───────────────────────────────────────────

class EnrichmentData(BaseModel):
    # Regulatory
    license_active: Optional[bool] = None
    enforcement_actions_12m: Optional[int] = None

    # Financial
    is_publicly_listed: Optional[bool] = None
    has_audited_financials: Optional[bool] = None
    equity_ratio: Optional[float] = None          # 0.0–1.0
    revenue_stability: Optional[str] = None       # "stable"|"volatile"|"unknown"
    debt_level: Optional[str] = None              # "low"|"moderate"|"high"

    # Operational
    has_soc2: Optional[bool] = None
    has_iso27001: Optional[bool] = None
    has_insurance: Optional[bool] = None
    major_security_incidents: Optional[int] = None
    years_in_operation: Optional[int] = None

    # Liquidity & Reserves
    por_ratio: Optional[float] = None             # assets/liabilities e.g. 1.05
    reserve_quality: Optional[str] = None         # "high"|"medium"|"low"
    withdrawal_restrictions_history: Optional[bool] = None

    # On-Chain
    onchain_reserve_trend_30d: Optional[str] = None  # "increasing"|"stable"|"declining"|"critical_outflow"
    tvl_change_30d_pct: Optional[float] = None    # DeFi only
    audit_count: Optional[int] = None             # DeFi only

    # Reputation
    industry_reputation_score: Optional[float] = None  # 0–100
    leadership_concerns: Optional[bool] = None

    # Notes
    analyst_notes: Optional[str] = None



@router.post("/{counterparty_id}/update")
async def update_counterparty(
    counterparty_id: UUID,
    body: dict,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update counterparty fields."""
    allowed = {"display_name","legal_name","entity_type","jurisdiction",
               "regulator","license_number","website","notes"}
    update = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    supabase.table("counterparties").update(update)         .eq("counterparty_id", str(counterparty_id)).execute()
    return {"status": "updated", "counterparty_id": str(counterparty_id)}


@router.post("/{counterparty_id}/delete")
async def delete_counterparty(
    counterparty_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Soft-delete a counterparty."""
    supabase.table("counterparties").update({"is_active": False})         .eq("counterparty_id", str(counterparty_id)).execute()
    return {"status": "deleted", "counterparty_id": str(counterparty_id)}


@router.post("/{counterparty_id}/enrichment")
async def save_enrichment(
    counterparty_id: UUID,
    body: EnrichmentData,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Save manually-input data signals for a counterparty.
    Triggers immediate rescore using enriched data.
    All fields are optional — only provided fields are updated.
    """
    # Get existing enrichment data and merge
    cp = (
        supabase.table("counterparties")
        .select("enrichment_data, display_name")
        .eq("counterparty_id", str(counterparty_id))
        .single()
        .execute()
    )
    if not cp.data:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    existing = cp.data.get("enrichment_data") or {}

    # Merge: only overwrite fields that were explicitly provided
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    merged  = {**existing, **updates}

    supabase.table("counterparties").update({
        "enrichment_data":   merged,
        "last_enriched_at":  datetime.utcnow().isoformat(),
        "last_enriched_by":  current_user.user_id,
    }).eq("counterparty_id", str(counterparty_id)).execute()

    # Audit log
    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "DATA_WRITE",
        "event_type":     "counterparty.enriched",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "resource_type":  "counterparties",
        "resource_id":    str(counterparty_id),
        "before_state":   existing,
        "after_state":    merged,
        "metadata":       {
            "counterparty_name": cp.data["display_name"],
            "fields_updated": list(updates.keys()),
        },
    }).execute()

    # Trigger rescore with enriched data
    from app.workers.scoring import score_single_counterparty
    from app.workers.tasks import run_in_thread
    run_in_thread(score_single_counterparty, str(counterparty_id))

    return {
        "status":          "saved",
        "fields_updated":  list(updates.keys()),
        "rescore_queued":  True,
        "enrichment_data": merged,
    }


@router.get("/{counterparty_id}/enrichment")
async def get_enrichment(
    counterparty_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get current enrichment data for a counterparty."""
    cp = (
        supabase.table("counterparties")
        .select("enrichment_data, last_enriched_at, last_enriched_by")
        .eq("counterparty_id", str(counterparty_id))
        .single()
        .execute()
    )
    if not cp.data:
        raise HTTPException(status_code=404, detail="Counterparty not found")
    return {
        "enrichment_data":  cp.data.get("enrichment_data") or {},
        "last_enriched_at": cp.data.get("last_enriched_at"),
        "last_enriched_by": cp.data.get("last_enriched_by"),
    }


# ── Research Agent endpoints ──────────────────────────────────

@router.post("/{counterparty_id}/research")
async def trigger_research(
    counterparty_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Trigger the AI research agent for a counterparty.
    Runs in background (~2-3 min). Poll GET /research to check status.
    """
    cp = (
        supabase.table("counterparties")
        .select("display_name, research_status")
        .eq("counterparty_id", str(counterparty_id))
        .single()
        .execute()
    )
    if not cp.data:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    if cp.data.get("research_status") == "running":
        raise HTTPException(status_code=409, detail="Research already running for this counterparty")

    from app.agents.research_agent import run_research_agent
    from app.workers.tasks import run_in_thread
    run_in_thread(run_research_agent, str(counterparty_id))

    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "AGENT",
        "event_type":     "counterparty.research_started",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "resource_type":  "counterparties",
        "resource_id":    str(counterparty_id),
        "metadata":       {"entity_name": cp.data["display_name"]},
    }).execute()

    return {
        "status":  "started",
        "message": f"Researching {cp.data['display_name']} — takes 2-3 minutes. Poll GET /research for results.",
    }


@router.get("/{counterparty_id}/research")
async def get_research(
    counterparty_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get the latest research report for a counterparty."""
    cp = (
        supabase.table("counterparties")
        .select("research_data, research_status, last_researched_at, display_name")
        .eq("counterparty_id", str(counterparty_id))
        .single()
        .execute()
    )
    if not cp.data:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    return {
        "counterparty_id":   str(counterparty_id),
        "entity_name":       cp.data["display_name"],
        "research_status":   cp.data.get("research_status", "none"),
        "last_researched_at": cp.data.get("last_researched_at"),
        "research_data":     cp.data.get("research_data"),
    }


@router.post("/{counterparty_id}/research/apply")
async def apply_research(
    counterparty_id: UUID,
    body: dict,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Apply selected research findings to enrichment data.
    body: { "fields": ["license_active", "has_soc2", ...] } or { "apply_all": true }
    Triggers rescore after apply.
    """
    cp = (
        supabase.table("counterparties")
        .select("research_data, enrichment_data, display_name")
        .eq("counterparty_id", str(counterparty_id))
        .single()
        .execute()
    )
    if not cp.data or not cp.data.get("research_data"):
        raise HTTPException(status_code=404, detail="No research data found. Run research first.")

    from app.agents.research_agent import extract_enrichment_from_research
    all_enrichment = extract_enrichment_from_research(cp.data["research_data"])

    apply_all     = body.get("apply_all", False)
    selected      = body.get("fields", [])
    fields_to_apply = list(all_enrichment.keys()) if apply_all else selected

    existing  = cp.data.get("enrichment_data") or {}
    updates   = {k: v for k, v in all_enrichment.items() if k in fields_to_apply}
    merged    = {**existing, **updates}

    supabase.table("counterparties").update({
        "enrichment_data":  merged,
        "last_enriched_at": datetime.utcnow().isoformat(),
        "last_enriched_by": current_user.user_id,
    }).eq("counterparty_id", str(counterparty_id)).execute()

    supabase.table("audit_log").insert({
        "tenant_id":      settings.DEFAULT_TENANT_ID,
        "event_category": "HUMAN_REVIEW",
        "event_type":     "counterparty.research_applied",
        "actor_type":     "USER",
        "actor_id":       current_user.user_id,
        "resource_type":  "counterparties",
        "resource_id":    str(counterparty_id),
        "metadata": {
            "entity_name":    cp.data["display_name"],
            "fields_applied": fields_to_apply,
            "apply_all":      apply_all,
        },
    }).execute()

    from app.workers.scoring import score_single_counterparty
    from app.workers.tasks import run_in_thread
    run_in_thread(score_single_counterparty, str(counterparty_id))

    return {
        "status":         "applied",
        "fields_applied": fields_to_apply,
        "rescore_queued": True,
    }


@router.get("/{counterparty_id}/data-sources")
async def get_data_sources(
    counterparty_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Fetch live data from all providers for a counterparty.
    Runs with a 50s overall timeout to avoid 502 on slow providers.
    """
    from app.services.providers import defillama, edgar, fca as fca_provider, zefix as zefix_provider, finma as finma_provider, uid_gleif, nansen as nansen_provider, defillama_cex, sanctions as sanctions_provider, regulatory_intelligence as reg_intel, snb as snb_provider

    cp = (
        supabase.table("counterparties")
        .select("*")
        .eq("counterparty_id", str(counterparty_id))
        .single()
        .execute()
        .data
    )
    if not cp:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    sources = {}

    # DefiLlama
    if cp.get("entity_type") in ("defi_protocol", "exchange"):
        dl = defillama.enrich_counterparty(cp.get("slug",""), cp.get("entity_type",""))
        sources["defillama"] = {
            "name": "DefiLlama",
            "available": bool(dl.get("tvl_usd") or dl.get("volume_24h_usd")),
            "data": dl,
            "url": f"https://defillama.com/protocol/{cp.get('slug','')}",
        }

    # SEC EDGAR
    edgar_result = edgar.enrich_counterparty(cp.get("slug",""))
    sources["edgar"] = {
        "name": "SEC EDGAR",
        "available": edgar_result.get("available", False),
        "data": {k: v for k, v in edgar_result.items()
                 if k not in ("source","available","fetched_at")} if edgar_result.get("available") else {},
        "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={edgar_result.get('cik','')}",
    }

    # FCA Register
    if cp.get("jurisdiction") == "GB" or "FCA" in (cp.get("regulator","").upper()):
        fca_result = fca_provider.enrich_counterparty(cp.get("slug",""), cp.get("display_name",""))
        sources["fca"] = {
            "name": "FCA Register",
            "available": fca_result.get("available", False),
            "data": {k: v for k, v in fca_result.items()
                     if k not in ("source","available","fetched_at")} if fca_result.get("available") else {},
            "url": f"https://register.fca.org.uk/s/firm?id={fca_result.get('frn','')}",
        }

    # DefiLlama CEX Transparency
    if cp.get("entity_type") == "exchange":
        cex_result = defillama_cex.enrich_counterparty(cp.get("slug",""))
        sources["defillama_cex"] = {
            "name": "DefiLlama CEX Transparency",
            "available": cex_result.get("available", False),
            "data": {k: v for k, v in cex_result.items()
                     if k not in ("source","available","fetched_at","reserve_trend") and v is not None
                    } if cex_result.get("available") else {},
            "url": cex_result.get("dl_url", "https://defillama.com/cexs"),
        }

    # Sanctions Screening
    sanctions_result = sanctions_provider.screen_counterparty(
        cp.get("display_name",""), cp.get("legal_name")
    )
    sources["sanctions"] = {
        "name": "Sanctions Screening (OFAC + EU + UN)",
        "available": True,
        "data": {
            "risk_level":    sanctions_result.get("risk_level"),
            "matched_lists": sanctions_result.get("matched_lists", []),
            "screened_at":   sanctions_result.get("screened_at"),
        },
        "url": "https://ofac.treasury.gov/sanctions-list-service",
    }

    # Regulatory Intelligence (FINMA, SECO, SNB, EBA, GLEIF via Claude web search)
    EU_EEA = {"AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR",
               "HU","IS","IE","IT","LV","LI","LT","LU","MT","NL","NO","PL",
               "PT","RO","SK","SI","ES","SE"}
    jur = cp.get("jurisdiction", "")
    is_swiss = jur == "CH" or "FINMA" in cp.get("regulator","").upper()
    is_eu    = jur in EU_EEA

    if is_swiss:
        # FINMA — direct Excel download from finma.ch/en/.../beh.xlsx
        try:
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor(max_workers=1) as _ex:
                _fut = _ex.submit(finma_provider.enrich_counterparty,
                                  cp.get("slug",""), cp.get("display_name",""))
                try:
                    finma_result = _fut.result(timeout=8)
                except _cf.TimeoutError:
                    print("[data_sources] FINMA timeout - using cache or skip")
                    finma_result = {"available": False, "reason": "timeout"}
        except Exception as _e:
            print(f"[data_sources] FINMA error: {_e}")
            finma_result = {"available": False}
        sources["finma"] = {
            "name": "FINMA Supervised Institutions",
            "available": finma_result.get("available", False),
            "data": {k: v for k, v in finma_result.items()
                     if k not in ("source","available","fetched_at","reason","xlsx_url") and v
                    } if finma_result.get("available") else {},
            "url": "https://www.finma.ch/en/finma-public/authorised-institutions-individuals-and-products/",
        }

        # OpenSanctions — ch_seco_sanctions dataset
        from app.services.providers import seco as seco_provider
        try:
            seco_result = seco_provider.screen(
                cp.get("display_name",""), cp.get("legal_name")
            )
        except Exception as _e:
            print(f"[data_sources] OpenSanctions error: {_e}")
            seco_result = {"available": False}
        sources["opensanctions_ch"] = {
            "name": "OpenSanctions (SECO CH)",
            "available": seco_result.get("available", False),
            "data": {
                "dataset":      "ch_seco_sanctions",
                "result":       "CLEAR" if not seco_result.get("match") else "MATCH - REVIEW REQUIRED",
                "match":        seco_result.get("match", False),
                "score":        seco_result.get("score"),
                "matched_name": seco_result.get("matched_name"),
                "method":       seco_result.get("method"),
                "screened_at":  seco_result.get("screened_at"),
            },
            "url": "https://www.opensanctions.org/datasets/ch_seco_sanctions/",
        }

        # SNB Banking Statistics — direct warehouse API
        try:
            snb_result = snb_provider.enrich_counterparty(
                cp.get("slug",""), cp.get("display_name",""), cp.get("jurisdiction","CH")
            )
        except Exception as _e:
            print(f"[data_sources] SNB error: {_e}")
            snb_result = {"available": False}
        sources["snb"] = {
            "name": "SNB Banking Statistics",
            "available": snb_result.get("available", False),
            "data": {k: v for k, v in snb_result.items()
                     if k not in ("source","available","fetched_at","reason") and v
                    } if snb_result.get("available") else {},
            "url": "https://data.snb.ch/en/warehouse/BSTA/json",
        }

    if is_eu:
        # EBA Register — direct API
        from app.services.providers import eba as eba_provider
        eba_result = eba_provider.enrich_counterparty(
            cp.get("slug",""), cp.get("display_name",""), jur
        )
        sources["eba"] = {
            "name": "EBA Register of Institutions",
            "available": eba_result.get("available", False),
            "data": {k: v for k, v in eba_result.items()
                     if k not in ("source","available","fetched_at","reason") and v
                    } if eba_result.get("available") else {},
            "url": "https://registers.eba.europa.eu/solrweb/public",
        }

    if is_swiss or is_eu:
        # GLEIF — direct REST API (no auth)
        try:
            gleif_result = uid_gleif.enrich_gleif(cp.get("slug",""), cp.get("display_name",""), jur)
        except Exception as _e:
            print(f"[data_sources] GLEIF error: {_e}")
            gleif_result = {"available": False}
        sources["gleif"] = {
            "name": "GLEIF LEI Register",
            "available": gleif_result.get("available", False),
            "data": {k: v for k, v in gleif_result.items()
                     if k not in ("source","available","fetched_at") and v
                    } if gleif_result.get("available") else {},
            "url": gleif_result.get("gleif_url", "https://search.gleif.org"),
        }

    # Nansen (on-chain intelligence)
    if cp.get("entity_type") in ("exchange", "custodian", "defi_protocol"):
        nansen_result = nansen_provider.enrich_counterparty(
            cp.get("slug",""), cp.get("entity_type",""), cp.get("display_name","")
        )
        sources["nansen"] = {
            "name": "Nansen On-Chain Intelligence",
            "available": nansen_result.get("available", False),
            "data": {k: v for k, v in nansen_result.items()
                     if k not in ("source","available","fetched_at","agent_answer") and v is not None
                     } if nansen_result.get("available") else {},
            "url": nansen_result.get("nansen_reserves_url", f"https://app.nansen.ai"),
        }

    # Zefix (Swiss Commercial Register)
    if cp.get("jurisdiction") == "CH" or "FINMA" in (cp.get("regulator","").upper()):
        zefix_result = zefix_provider.enrich_counterparty(cp.get("slug",""), cp.get("display_name",""))
        sources["zefix"] = {
            "name": "Zefix (Swiss Commercial Register)",
            "available": zefix_result.get("available", False),
            "data": {k: v for k, v in zefix_result.items()
                     if k not in ("source","available","fetched_at") and v is not None} if zefix_result.get("available") else {},
            "url": zefix_result.get("registry_url", "https://www.zefix.admin.ch"),
        }

    # FINMA
    if cp.get("jurisdiction") == "CH" or "FINMA" in (cp.get("regulator","").upper()):
        finma_result = finma_provider.enrich_counterparty(cp.get("slug",""), cp.get("display_name",""))
        sources["finma"] = {
            "name": "FINMA Supervised Institutions",
            "available": finma_result.get("available", False),
            "data": {k: v for k, v in finma_result.items()
                     if k not in ("source","available","fetched_at") and v is not None} if finma_result.get("available") else {},
            "url": finma_result.get("finma_url", "https://www.finma.ch/en/authorisation/supervised-institutions/"),
        }

    # GLEIF LEI
    gleif_result = uid_gleif.enrich_gleif(cp.get("slug",""), cp.get("display_name",""))
    sources["gleif"] = {
        "name": "GLEIF LEI Register",
        "available": gleif_result.get("available", False),
        "data": {k: v for k, v in gleif_result.items()
                 if k not in ("source","available","fetched_at") and v is not None} if gleif_result.get("available") else {},
        "url": gleif_result.get("gleif_url", "https://search.gleif.org"),
    }

    # CoinGecko
    if cp.get("entity_type") == "exchange":
        sources["coingecko"] = {
            "name": "CoinGecko",
            "available": bool(settings.COINGECKO_API_KEY),
            "data": {"note": "Volume and trust score fetched during scoring"},
            "url": f"https://www.coingecko.com/en/exchanges/{cp.get('slug','')}",
        }

    return {
        "counterparty_id": str(counterparty_id),
        "entity_name":     cp.get("display_name", ""),
        "sources":         sources,
        "fetched_at":      datetime.utcnow().isoformat(),
    }
