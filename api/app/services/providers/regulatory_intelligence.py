"""
Raven — Regulatory Intelligence Provider

Uses Claude with web search to fetch regulatory and financial data
from sources that block direct API access:
- SECO Swiss sanctions (seco.admin.ch)
- SNB banking statistics (data.snb.ch)
- GLEIF LEI register (search.gleif.org)
- EBA register (registers.eba.europa.eu)
- FINMA supervised institutions (finma.ch)

One combined Claude call per entity type → fast, accurate, no API keys.
Results cached in counterparty enrichment_data to avoid repeat calls.
"""

import json
import re
from datetime import datetime
from anthropic import Anthropic
from app.core.config import settings

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _parse_json(text: str) -> dict:
    """Extract JSON from Claude response."""
    # Try direct parse first
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    # Try finding any JSON object
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}


def enrich_swiss_entity(slug: str, display_name: str, entity_type: str = "") -> dict:
    """
    Fetch regulatory and financial data for a Swiss entity using Claude web search.
    Searches: FINMA, SECO, SNB, GLEIF, Zefix (as backup), Swiss news.

    Returns structured dict with all available fields.
    """
    prompt = f"""Search for comprehensive regulatory and financial information about this Swiss financial entity:

Entity: {display_name}
Type: {entity_type or 'financial institution'}
Jurisdiction: Switzerland (CH)

Please search and find the following specific information:

1. FINMA supervision (finma.ch/en/authorisation/supervised-institutions/):
   - Is it FINMA-supervised? What licence type?
   - Is the licence currently active?
   - Any enforcement actions in last 12 months?

2. SECO Swiss sanctions (seco.admin.ch):
   - Does this entity appear on any Swiss sanctions list?

3. LEI (Legal Entity Identifier) from GLEIF (search.gleif.org):
   - What is the LEI code?
   - What is the LEI status?

4. Financial data from SNB or public sources:
   - Total assets (if available)
   - Capital ratio or equity ratio (if available)
   - Any credit ratings?

5. General regulatory standing:
   - Any recent regulatory fines, warnings, or enforcement actions?
   - Any pending regulatory investigations?

Respond ONLY with a valid JSON object (no markdown, no preamble):
{{
  "finma_supervised": true,
  "finma_licence_type": "Banking Licence",
  "finma_licence_active": true,
  "finma_enforcement_12m": 0,
  "finma_url": "https://www.finma.ch/...",
  "seco_sanctioned": false,
  "lei_code": "string or null",
  "lei_status": "ISSUED or null",
  "total_assets_chf_bn": null,
  "capital_ratio_pct": null,
  "credit_rating": null,
  "enforcement_actions_12m": 0,
  "recent_regulatory_issues": "none or description",
  "data_notes": "any important caveats"
}}"""

    try:
        response = _get_client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )

        raw = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw += block.text

        data = _parse_json(raw)
        if not data:
            return {"source": "regulatory_intelligence", "available": False, "reason": "parse_error"}

        result = {
            "source":     "regulatory_intelligence",
            "available":  True,
            "fetched_at": datetime.utcnow().isoformat(),
        }

        # FINMA
        if data.get("finma_supervised"):
            result["finma_supervised"]        = True
            result["license_active"]          = data.get("finma_licence_active", True)
            result["finma_licence_type"]      = data.get("finma_licence_type", "")
            result["finma_enforcement_12m"]   = data.get("finma_enforcement_12m", 0)
            result["finma_url"]               = data.get("finma_url")
            result["_finma"] = {
                "licence_type": data.get("finma_licence_type"),
                "status":       "authorised" if data.get("finma_licence_active") else "not_authorised",
                "url":          data.get("finma_url"),
            }
        else:
            result["finma_supervised"] = False

        # SECO
        result["seco_sanctioned"] = data.get("seco_sanctioned", False)
        result["_seco"] = {
            "available": True,
            "match":     data.get("seco_sanctioned", False),
            "screened_at": datetime.utcnow().isoformat(),
        }
        if data.get("seco_sanctioned"):
            result["license_active"]          = False
            result["enforcement_actions_12m"] = max(
                result.get("enforcement_actions_12m", 0), 3
            )

        # GLEIF / LEI
        if data.get("lei_code"):
            result["lei"]        = data["lei_code"]
            result["lei_status"] = data.get("lei_status", "ISSUED")
            result["_gleif"] = {
                "available": True,
                "lei":       data["lei_code"],
                "status":    data.get("lei_status"),
                "url":       f"https://search.gleif.org/#/record/{data['lei_code']}",
            }

        # Financial data
        if data.get("total_assets_chf_bn") is not None:
            result["total_assets_chf_bn"] = data["total_assets_chf_bn"]
            result["_snb"] = {
                "available":        True,
                "total_assets_bn":  data["total_assets_chf_bn"],
                "data_type":        "web_search",
            }
        if data.get("capital_ratio_pct") is not None:
            result["capital_ratio_pct"] = data["capital_ratio_pct"]
        if data.get("credit_rating"):
            result["credit_rating"] = data["credit_rating"]

        # Enforcement
        if data.get("enforcement_actions_12m", 0) > 0:
            result["enforcement_actions_12m"] = data["enforcement_actions_12m"]
        if data.get("recent_regulatory_issues") and data["recent_regulatory_issues"] != "none":
            result["regulatory_notes"] = data["recent_regulatory_issues"]

        result["data_notes"] = data.get("data_notes", "")
        return result

    except Exception as e:
        print(f"[reg_intel] Swiss entity enrichment error for {display_name}: {e}")
        return {"source": "regulatory_intelligence", "available": False, "reason": str(e)}


def enrich_eu_entity(slug: str, display_name: str, jurisdiction: str, entity_type: str = "") -> dict:
    """
    Fetch regulatory data for an EU/EEA entity using Claude web search.
    Searches: EBA register, national regulator, GLEIF, news.
    """
    REGULATORS = {
        "DE": "BaFin (Bundesanstalt für Finanzdienstleistungsaufsicht)",
        "FR": "AMF (Autorité des marchés financiers) and ACPR",
        "LU": "CSSF (Commission de Surveillance du Secteur Financier)",
        "IE": "Central Bank of Ireland",
        "NL": "AFM and DNB (De Nederlandsche Bank)",
        "IT": "Consob and Banca d'Italia",
        "ES": "CNMV and Banco de España",
        "AT": "FMA (Finanzmarktaufsicht)",
        "BE": "FSMA and National Bank of Belgium",
        "SE": "Finansinspektionen",
        "DK": "Finanstilsynet",
    }
    regulator = REGULATORS.get(jurisdiction, f"national financial regulator ({jurisdiction})")

    prompt = f"""Search for comprehensive regulatory information about this European financial entity:

Entity: {display_name}
Jurisdiction: {jurisdiction}
Type: {entity_type or 'financial institution'}
National Regulator: {regulator}

Please search and find:

1. EBA Register (registers.eba.europa.eu):
   - Is it EBA-registered? What institution type (credit institution, investment firm, etc.)?
   - Is the authorisation currently active?

2. National regulator register ({regulator}):
   - Regulatory status and licence type
   - Any enforcement actions in last 12 months?

3. LEI from GLEIF (search.gleif.org):
   - LEI code and status?

4. Financial standing:
   - Credit rating (Moody's, S&P, Fitch)?
   - Any recent capital/liquidity concerns?

Respond ONLY with valid JSON:
{{
  "eba_registered": true,
  "eba_institution_type": "Credit Institution",
  "eba_licence_active": true,
  "national_licence_active": true,
  "enforcement_actions_12m": 0,
  "lei_code": "string or null",
  "credit_rating": null,
  "regulatory_notes": "none or description",
  "data_notes": "any caveats"
}}"""

    try:
        response = _get_client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )

        raw = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw += block.text

        data = _parse_json(raw)
        if not data:
            return {"source": "regulatory_intelligence", "available": False}

        result = {
            "source":     "regulatory_intelligence",
            "available":  True,
            "fetched_at": datetime.utcnow().isoformat(),
        }

        if data.get("eba_registered"):
            result["eba_registered"]      = True
            result["license_active"]      = (
                data.get("eba_licence_active", True) and
                data.get("national_licence_active", True)
            )
            result["eba_institution_type"] = data.get("eba_institution_type", "")
            result["_eba"] = {
                "available":        True,
                "institution_type": data.get("eba_institution_type"),
                "status":           "authorised" if data.get("eba_licence_active") else "not_authorised",
            }

        if data.get("enforcement_actions_12m", 0) > 0:
            result["enforcement_actions_12m"] = data["enforcement_actions_12m"]

        if data.get("lei_code"):
            result["lei"] = data["lei_code"]
            result["_gleif"] = {
                "available": True,
                "lei":       data["lei_code"],
                "url":       f"https://search.gleif.org/#/record/{data['lei_code']}",
            }

        if data.get("credit_rating"):
            result["credit_rating"] = data["credit_rating"]

        if data.get("regulatory_notes") and data["regulatory_notes"] != "none":
            result["regulatory_notes"] = data["regulatory_notes"]

        result["data_notes"] = data.get("data_notes", "")
        return result

    except Exception as e:
        print(f"[reg_intel] EU entity error for {display_name}: {e}")
        return {"source": "regulatory_intelligence", "available": False, "reason": str(e)}
