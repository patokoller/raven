"""
Raven — Regulatory Analysis Engine

Uses Claude to read regulatory documents (PDFs, HTML) and produce
structured impact assessments for Swiss institutional digital asset mandates.

Output includes:
- Plain English summary
- Criticality (LOW/MEDIUM/HIGH/CRITICAL)
- Affected counterparty types and specific entities
- Scoring dimension impact (which dimensions need weight adjustments)
- Recommended enrichment fields to re-verify
- Specific compliance actions for portfolio managers
"""

import httpx
import json
from datetime import datetime
from typing import Optional
from anthropic import Anthropic

from app.core.database import supabase
from app.core.config import settings

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)


ANALYSIS_SYSTEM = """You are a Swiss regulatory compliance expert specialising in digital asset regulation.
Your role is to analyse regulatory documents and assess their impact on institutional digital asset risk scoring.

Context: You are analysing documents for Raven, a counterparty risk platform used by Swiss wealth managers
and portfolio managers. Raven scores counterparties across 6 dimensions:
- Regulatory (25%): licence status, regulator tier, jurisdiction, enforcement actions
- Financial (20%): listing, audited financials, equity ratio, debt level
- Operational (20%): SOC2/ISO27001, security incidents, insurance, years operating
- Liquidity (15%): Proof of Reserves, reserve quality, withdrawal restrictions
- On-Chain (10%): reserve trends, TVL change, audit count
- Reputation (10%): news sentiment, industry standing, leadership concerns

You must output ONLY valid JSON. No preamble or explanation outside JSON."""


ANALYSIS_PROMPT = """Analyse this regulatory document and assess its impact on institutional digital asset counterparty risk scoring.

DOCUMENT:
{text}

Return a JSON object with this exact structure:
{{
  "doc_ref": "Official document reference number if found (e.g. 'FINMA Guidance 01/2026')",
  "title": "Official document title",
  "published_date": "YYYY-MM-DD if found, else null",
  "regulator": "Issuing regulator (FINMA/FCA/SEC/BIS/other)",
  "doc_type": "guidance/circular/notice/consultation/enforcement",

  "summary": "2-3 paragraph plain English summary of what this document says and why it matters for Swiss institutional digital asset mandates",

  "criticality": "CRITICAL|HIGH|MEDIUM|LOW",
  "criticality_rationale": "One sentence explaining the criticality rating",

  "key_requirements": [
    "Specific requirement 1 that institutions must comply with",
    "Specific requirement 2..."
  ],

  "affected_entity_types": ["custodian", "exchange", "prime_broker", "defi_protocol", "lender"],

  "affected_counterparties": [
    {{
      "name": "Entity name from our registry",
      "slug": "entity-slug",
      "impact": "HIGH|MEDIUM|LOW",
      "reason": "Why this entity is specifically affected"
    }}
  ],

  "scoring_dimension_impacts": [
    {{
      "dimension": "regulatory|financial|operational|liquidity|onchain|reputation",
      "current_weight_pct": 25,
      "suggested_weight_pct": 30,
      "rationale": "Why this dimension weight should change",
      "applies_to": "all|custodian|exchange|defi_protocol"
    }}
  ],

  "enrichment_fields_to_reverify": [
    {{
      "field": "license_active",
      "reason": "Why this field needs re-verification given the new guidance",
      "entity_types": ["custodian"]
    }}
  ],

  "compliance_actions": [
    {{
      "priority": "IMMEDIATE|SHORT_TERM|MEDIUM_TERM",
      "action": "Specific action the analyst or portfolio manager should take",
      "deadline": "within X days/weeks/months",
      "rationale": "Why this action is required under the new guidance"
    }}
  ],

  "key_thresholds": [
    "Any specific quantitative thresholds, limits, or conditions mentioned"
  ],

  "exceptions_and_carve_outs": [
    "Any exceptions, transitional arrangements, or carve-outs for specific entities"
  ],

  "related_regulations": [
    "Other regulations or circulars this document references or amends"
  ]
}}

For 'affected_counterparties', only include entities from this registry:
Sygnum Bank, SEBA Bank, Bitcoin Suisse, Taurus, Maerki Baumann, Copper, Fireblocks, BitGo,
Anchorage Digital, Coinbase Custody, B2C2, LMAX Digital, Wintermute, Binance, Coinbase,
Kraken, Bitstamp, FalconX, Hidden Road, Galaxy Digital, Aave, Uniswap, Compound, Maple Finance,
Ledn, Cumberland DRW, Goldman Sachs Digital, JPMorgan Onyx, Clear Street, Gemini,
OKX, Bybit, CEX.IO, Alpaca Markets, Deribit, Anchorage Digital"""


def _fetch_document_text(url: str) -> Optional[str]:
    """
    Fetch and extract text from a regulatory document.
    Handles PDF and HTML documents.
    """
    try:
        r = httpx.get(
            url,
            headers={"User-Agent": "Raven Risk Intelligence / regulatory-reader contact@raven.internal"},
            timeout=30,
            follow_redirects=True,
        )
        if r.status_code != 200:
            print(f"[reg_analysis] Failed to fetch {url}: HTTP {r.status_code}")
            return None

        content_type = r.headers.get("content-type", "")

        if "pdf" in content_type or url.lower().endswith(".pdf"):
            return _extract_pdf_text(r.content)
        else:
            # HTML — extract text content
            import re
            text = re.sub(r'<[^>]+>', ' ', r.text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:20000]  # limit for Claude context

    except Exception as e:
        print(f"[reg_analysis] Fetch error for {url}: {e}")
        return None


def _extract_pdf_text(pdf_bytes: bytes) -> Optional[str]:
    """Extract text from PDF bytes using pdfminer."""
    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams
        from io import BytesIO, StringIO

        output = StringIO()
        extract_text_to_fp(BytesIO(pdf_bytes), output, laparams=LAParams())
        text = output.getvalue()
        # Clean up
        import re
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        return text[:25000]  # ~6000 tokens

    except ImportError:
        # Fallback: try pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text[:25000]
        except Exception as e2:
            print(f"[reg_analysis] PDF extraction failed: {e2}")
            return None
    except Exception as e:
        print(f"[reg_analysis] PDF extraction error: {e}")
        return None


def analyse_document(doc_id: str) -> dict:
    """
    Main entry point. Fetches a stored document, reads it, and produces
    a structured impact analysis using Claude.
    """
    # Mark as analysing
    supabase.table("regulatory_documents").update({
        "status": "analysing",
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("doc_id", doc_id).execute()

    try:
        doc = (
            supabase.table("regulatory_documents")
            .select("*")
            .eq("doc_id", doc_id)
            .single()
            .execute()
            .data
        )
        if not doc:
            raise ValueError(f"Document {doc_id} not found")

        # Fetch document text
        text = _fetch_document_text(doc["url"])
        if not text:
            raise ValueError(f"Could not extract text from {doc['url']}")

        # Analyse with Claude
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,  # Opus for regulatory analysis
            max_tokens=4000,
            system=ANALYSIS_SYSTEM,
            messages=[{
                "role": "user",
                "content": ANALYSIS_PROMPT.format(text=text[:20000])
            }],
        )

        raw = response.content[0].text
        # Strip markdown if present
        for tag in ["```json", "```"]:
            if tag in raw:
                raw = raw.split(tag)[1].split("```")[0].strip()
                break

        analysis = json.loads(raw)

        # Update the document with analysis results
        supabase.table("regulatory_documents").update({
            "status":              "analysed",
            "doc_ref":             analysis.get("doc_ref"),
            "title":               analysis.get("title", doc["title"]),
            "published_date":      analysis.get("published_date"),
            "summary":             analysis.get("summary"),
            "criticality":         analysis.get("criticality"),
            "affected_entity_types":    analysis.get("affected_entity_types", []),
            "affected_counterparties":  [c["name"] for c in analysis.get("affected_counterparties", [])],
            "scoring_impacts":     analysis.get("scoring_dimension_impacts", []),
            "recommended_actions": analysis.get("compliance_actions", []),
            "full_analysis":       analysis,
            "updated_at":          datetime.utcnow().isoformat(),
        }).eq("doc_id", doc_id).execute()

        # Create a regulatory alert
        criticality = analysis.get("criticality", "MEDIUM")
        severity_map = {"CRITICAL": "CRITICAL", "HIGH": "HIGH", "MEDIUM": "WARNING", "LOW": "INFO"}

        supabase.table("alerts").insert({
            "tenant_id":    settings.DEFAULT_TENANT_ID,
            "alert_type":   "regulatory_update",
            "severity":     severity_map.get(criticality, "WARNING"),
            "title":        f"New {doc['regulator']} guidance — {analysis.get('title', doc['title'])[:80]}",
            "body":         analysis.get("summary", "")[:500],
            "metadata": {
                "doc_id":               doc_id,
                "doc_ref":              analysis.get("doc_ref"),
                "criticality":          criticality,
                "affected_entities":    [c["name"] for c in analysis.get("affected_counterparties", [])],
                "dimension_impacts":    analysis.get("scoring_dimension_impacts", []),
            },
        }).execute()

        print(f"[reg_analysis] ✓ {analysis.get('doc_ref', doc_id)}: {criticality}")
        # Auto-apply to affected counterparties
        try:
            apply_result = apply_to_affected_counterparties(doc_id)
            print(f"[reg_analysis] Auto-applied to {len(apply_result.get('updated', []))} counterparties")
        except Exception as e:
            print(f"[reg_analysis] Auto-apply error (non-fatal): {e}")

        return {"status": "analysed", "doc_id": doc_id, "criticality": criticality}

    except Exception as e:
        supabase.table("regulatory_documents").update({
            "status":     "error",
            "summary":    f"Analysis failed: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("doc_id", doc_id).execute()
        print(f"[reg_analysis] Error on {doc_id}: {e}")
        raise


def apply_weight_recommendations(doc_id: str, entity_type_filter: Optional[str] = None) -> dict:
    """
    Apply the scoring weight recommendations from a regulatory analysis.
    Can be filtered to apply only for specific entity types.
    """
    doc = (
        supabase.table("regulatory_documents")
        .select("full_analysis, doc_ref, title")
        .eq("doc_id", doc_id)
        .single()
        .execute()
        .data
    )
    if not doc or not doc.get("full_analysis"):
        return {"error": "No analysis found"}

    impacts = doc["full_analysis"].get("scoring_dimension_impacts", [])
    if not impacts:
        return {"error": "No dimension impacts in analysis"}

    # Build new weights from recommendations
    # Get current weights
    weights_row = (
        supabase.table("system_config")
        .select("value")
        .eq("key", "scoring_weights")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .execute()
        .data
    )
    current = (weights_row[0]["value"] if weights_row else settings.SCORING_WEIGHTS).copy()

    applied = []
    for impact in impacts:
        applies_to = impact.get("applies_to", "all")
        if entity_type_filter and applies_to not in ("all", entity_type_filter):
            continue

        dim = impact.get("dimension")
        new_pct = impact.get("suggested_weight_pct")
        if dim and new_pct is not None:
            current[dim] = round(new_pct / 100, 3)
            applied.append(f"{dim}: {impact.get('current_weight_pct')}% → {new_pct}%")

    # Normalise to sum to 1.0
    total = sum(current.values())
    if total > 0:
        current = {k: round(v / total, 3) for k, v in current.items()}
        adj = 1.0 - sum(current.values())
        first_key = list(current.keys())[0]
        current[first_key] = round(current[first_key] + adj, 3)

    # Save to DB
    supabase.table("system_config").upsert({
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "key":       "scoring_weights",
        "value":     current,
        "updated_at": datetime.utcnow().isoformat(),
    }, on_conflict="tenant_id,key").execute()

    # Also update in-memory settings so scoring engine uses new weights immediately
    settings.SCORING_WEIGHTS.update(current)

    # Mark document as applied
    supabase.table("regulatory_documents").update({
        "status":     "applied",
        "applied_at": datetime.utcnow().isoformat(),
    }).eq("doc_id", doc_id).execute()

    return {
        "status":          "applied",
        "weights_updated": current,
        "changes":         applied,
        "doc_ref":         doc["doc_ref"],
    }


def apply_to_affected_counterparties(doc_id: str) -> dict:
    """
    Apply regulatory findings directly to enrichment_data of affected counterparties.
    Matches by name against the full registry, updates enrichment and rescores.
    """
    doc = (
        supabase.table("regulatory_documents")
        .select("full_analysis, doc_ref, title, regulator")
        .eq("doc_id", doc_id)
        .single()
        .execute()
        .data
    )
    if not doc or not doc.get("full_analysis"):
        return {"error": "No analysis found"}

    analysis  = doc["full_analysis"]
    affected_cps = analysis.get("affected_counterparties", [])
    doc_ref   = doc.get("doc_ref") or doc.get("title", "Unknown")

    print(f"[reg_apply] Starting apply for doc {doc_id}, {len(affected_cps)} affected CPs")

    # Load all counterparties once for matching
    all_cps = (
        supabase.table("counterparties")
        .select("counterparty_id, display_name, enrichment_data, entity_type, slug")
        .eq("tenant_id", settings.DEFAULT_TENANT_ID)
        .eq("is_active", True)
        .execute()
        .data
    ) or []

    # Build name lookup map
    cp_by_name = {}
    for cp in all_cps:
        cp_by_name[cp["display_name"].lower()] = cp
        cp_by_name[cp["slug"].lower()] = cp

    updated = []
    skipped = []

    for affected in affected_cps:
        if not isinstance(affected, dict):
            continue

        name   = affected.get("name", "").strip()
        impact = affected.get("impact", "LOW")
        reason = affected.get("reason", "")
        if not name:
            continue

        # Find counterparty — exact match first, then partial
        cp = cp_by_name.get(name.lower())
        if not cp:
            # Try partial match on first word
            first_word = name.lower().split()[0] if name else ""
            for key, candidate in cp_by_name.items():
                if first_word and first_word in key:
                    cp = candidate
                    break

        if not cp:
            skipped.append(name)
            continue

        existing = cp.get("enrichment_data") or {}

        # Build regulatory flag entry
        reg_note = {
            "doc_ref":    doc_ref,
            "impact":     impact,
            "reason":     reason,
            "applied_at": datetime.utcnow().isoformat(),
        }

        # Safe list append — handle case where _regulatory_flags isn't a list
        existing_flags = existing.get("_regulatory_flags", [])
        if not isinstance(existing_flags, list):
            existing_flags = []

        updates = {"_regulatory_flags": existing_flags + [reg_note]}

        # HIGH impact custodians from FINMA guidance → flag licence issue
        if impact in ("HIGH", "CRITICAL") and cp.get("entity_type") == "custodian":
            updates["_finma_compliance_flag"] = reason
            # All HIGH/CRITICAL impact custodians fail the FINMA requirement
            # (the analysis already determined impact level — trust it)
            updates["license_active"] = False
            current_ea = existing.get("enforcement_actions_12m")
            updates["enforcement_actions_12m"] = max(int(current_ea) if current_ea else 0, 1)

        merged = {**existing, **updates}

        try:
            supabase.table("counterparties").update({
                "enrichment_data":  merged,
                "last_enriched_at": datetime.utcnow().isoformat(),
            }).eq("counterparty_id", cp["counterparty_id"]).execute()

            # Trigger individual rescore
            from app.workers.scoring import score_single_counterparty
            from app.workers.tasks import run_in_thread
            run_in_thread(score_single_counterparty, cp["counterparty_id"])

            updated.append({"name": cp["display_name"], "impact": impact, "changes": list(updates.keys())})
            print(f"[reg_apply] Updated {cp['display_name']}: {list(updates.keys())}")

        except Exception as e:
            print(f"[reg_apply] Error updating {cp['display_name']}: {e}")
            skipped.append(name)

    try:
        supabase.table("audit_log").insert({
            "tenant_id":      settings.DEFAULT_TENANT_ID,
            "event_category": "HUMAN_REVIEW",
            "event_type":     "regulatory.applied_to_counterparties",
            "metadata": {
                "doc_ref": doc_ref,
                "doc_id":  doc_id,
                "updated": [u["name"] for u in updated],
                "skipped": skipped,
            },
        }).execute()
    except Exception:
        pass

    return {
        "status":  "applied",
        "updated": updated,
        "skipped": skipped,
        "doc_ref": doc_ref,
    }
