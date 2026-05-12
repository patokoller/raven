"""
Raven — FINMA Custody Compliance Module

Implements FINMA Guidance 01/2026 on the custody of crypto-based assets.

Classifies each counterparty into one of four statuses:
  compliant     — FINMA-prudentially-supervised + Swiss bankruptcy protection
                  (Sygnum Bank, SEBA Bank, Maerki Baumann, Anchorage Digital)
  scenario_b    — SRO-supervised + Art. 242a bankruptcy protection, no prudential supervision
                  (Bitcoin Suisse, Taurus under VQF/PolyReg)
  scenario_a    — Foreign custodian with equivalent prudential supervision,
                  no equivalent CH bankruptcy protection
                  (Coinbase Custody, Kraken, Fidelity Digital)
  non_compliant — Neither prudential supervision nor equivalent bankruptcy protection
                  (Binance, Fireblocks in non-equivalent jurisdiction, unregulated)

Generates disclosure language calibrated to client type:
  retail           — Full written disclosure + alternatives list + documented consent required
  qualified_investor — Disclosure + consent required
  institutional    — Disclosure recommended, lighter language

References:
  FINMA Guidance 01/2026, published 12 January 2026
  Art. 37d BA + Art. 242a SchKG (DLT Blanket Act, 2021)
  Art. 73 para. 2 CISA (collective investment schemes)
  FinSA (structured products / ETPs offered to retail clients)
"""

from datetime import datetime
from typing import Optional

# ── Custody status classification ─────────────────────────────

# FINMA-prudentially-supervised custodians confirmed compliant
FINMA_SUPERVISED_CUSTODIANS = {
    "sygnum", "sygnum-bank", "seba-bank", "seba", "maerki-baumann",
    "anchorage-digital", "julius-baer", "falcon-private-bank",
    "amina-bank", "amina",  # formerly SEBA
}

# SRO-supervised Swiss entities (Scenario B)
SRO_SUPERVISED_CUSTODIANS = {
    "bitcoin-suisse", "taurus", "copper",
}

# Foreign custodians with prudential supervision equivalent (Scenario A)
# but lacking Swiss-equivalent bankruptcy protection
SCENARIO_A_CUSTODIANS = {
    "coinbase", "coinbase-custody", "kraken", "fidelity-digital",
    "gemini", "bitstamp", "lmax-digital", "deribit",
}

# Regulators that indicate FINMA prudential supervision
FINMA_PRUDENTIAL_REGULATORS = {"finma"}

# Regulators that indicate SRO-only supervision
SRO_REGULATORS = {"vqf", "polyreg", "sro", "arif"}

# Jurisdictions where prudential supervision is equivalent (for Scenario A)
EQUIVALENT_PRUDENTIAL_JURISDICTIONS = {"US", "GB", "EU", "DE", "FR", "LU", "IE", "NL", "SG", "JP"}


def classify_custody_status(
    slug: str,
    entity_type: str,
    jurisdiction: str,
    regulator: str,
    enrichment_data: dict,
) -> dict:
    """
    Classify a counterparty's FINMA 01/2026 custody compliance status.
    Returns status + rationale + required actions.
    """
    slug_lower       = (slug or "").lower()
    regulator_lower  = (regulator or "").lower()
    jurisdiction_up  = (jurisdiction or "").upper()
    enrich_finma     = enrichment_data.get("_finma", {}) or {}

    # --- Check hardcoded known entities first ---
    if slug_lower in FINMA_SUPERVISED_CUSTODIANS:
        return {
            "status":   "compliant",
            "rationale": f"{slug} holds a full FINMA banking or securities licence. "
                         "Client assets benefit from prudential supervision and Swiss bankruptcy "
                         "protection under Art. 37d BA + Art. 242a SchKG. No disclosure obligation "
                         "under FINMA Guidance 01/2026.",
            "disclosure_required":   False,
            "consent_required":      False,
            "alternatives_required": False,
        }

    if slug_lower in SRO_SUPERVISED_CUSTODIANS:
        return {
            "status":   "scenario_b",
            "rationale": f"{slug} operates under SRO supervision (Art. 242a SchKG bankruptcy "
                         "protection exists) but lacks FINMA prudential supervision. "
                         "This is Scenario B under FINMA Guidance 01/2026 transitional provisions. "
                         "Portfolio managers must provide comprehensive client disclosure, "
                         "present alternative custodians, and obtain written client consent.",
            "disclosure_required":   True,
            "consent_required":      True,
            "alternatives_required": True,
        }

    if slug_lower in SCENARIO_A_CUSTODIANS:
        return {
            "status":   "scenario_a",
            "rationale": f"{slug} is subject to equivalent prudential supervision in its home "
                         "jurisdiction but Swiss-equivalent bankruptcy protection under Art. 242a "
                         "SchKG does not apply. This is Scenario A under FINMA Guidance 01/2026. "
                         "Comprehensive client disclosure and documented consent required.",
            "disclosure_required":   True,
            "consent_required":      True,
            "alternatives_required": True,
        }

    # --- Derive from regulatory data ---
    if "finma" in regulator_lower:
        # Check if it's prudential FINMA or just registered
        if enrich_finma.get("licence_type") or enrich_finma.get("finma_licence_type"):
            return {
                "status":   "compliant",
                "rationale": f"{slug} is FINMA-prudentially-supervised. Full compliance with "
                             "FINMA Guidance 01/2026 custody requirements.",
                "disclosure_required":   False,
                "consent_required":      False,
                "alternatives_required": False,
            }

    if any(sro in regulator_lower for sro in SRO_REGULATORS):
        return {
            "status":   "scenario_b",
            "rationale": f"{slug} operates under SRO supervision without full FINMA prudential "
                         "supervision. Scenario B transitional provisions apply.",
            "disclosure_required":   True,
            "consent_required":      True,
            "alternatives_required": True,
        }

    if jurisdiction_up == "CH" and "finma" not in regulator_lower:
        # Swiss entity without FINMA prudential supervision
        return {
            "status":   "scenario_b",
            "rationale": f"{slug} is a Swiss entity without confirmed FINMA prudential supervision. "
                         "Scenario B transitional provisions likely apply pending verification.",
            "disclosure_required":   True,
            "consent_required":      True,
            "alternatives_required": True,
        }

    if jurisdiction_up in EQUIVALENT_PRUDENTIAL_JURISDICTIONS:
        return {
            "status":   "scenario_a",
            "rationale": f"{slug} is supervised in {jurisdiction_up}, a jurisdiction with "
                         "equivalent prudential standards, but Swiss bankruptcy protection "
                         "does not apply. Scenario A disclosure required.",
            "disclosure_required":   True,
            "consent_required":      True,
            "alternatives_required": True,
        }

    # Default for unregulated / unclear
    return {
        "status":   "non_compliant",
        "rationale": f"{slug} does not appear to meet FINMA Guidance 01/2026 requirements: "
                     "no equivalent prudential supervision or bankruptcy protection identified. "
                     "Use of this custodian should be reviewed urgently.",
        "disclosure_required":   True,
        "consent_required":      True,
        "alternatives_required": True,
        "urgent_review":         True,
    }


# ── Compliant alternatives (used in disclosures) ───────────────

COMPLIANT_ALTERNATIVES = [
    "Sygnum Bank AG (FINMA banking licence, Zurich)",
    "SEBA Bank AG / AMINA Bank AG (FINMA banking licence, Zug)",
    "Maerki Baumann & Co. AG (FINMA banking licence, Zurich)",
    "Anchorage Digital Bank (OCC-chartered, equivalent prudential supervision)",
]


# ── Disclosure language generation ────────────────────────────

def generate_disclosure(
    counterparty_name: str,
    custody_info: dict,
    client_type: str,          # retail | qualified_investor | institutional
    aum_at_custodian_chf: Optional[float] = None,
) -> dict:
    """
    Generate FINMA 01/2026-compliant disclosure language for a specific
    counterparty + client type combination.
    Returns structured disclosure with narrative and required actions.
    """
    status    = custody_info.get("status", "non_compliant")
    aum_str   = f"CHF {aum_at_custodian_chf:,.0f}" if aum_at_custodian_chf else "assets"

    if status == "compliant":
        return {
            "counterparty":      counterparty_name,
            "status":            "compliant",
            "disclosure_required": False,
            "narrative": (
                f"{counterparty_name} holds a full FINMA banking licence and is subject to FINMA "
                f"prudential supervision. Your digital assets ({aum_str}) benefit from Swiss "
                f"bankruptcy protection under Art. 37d of the Banking Act and Art. 242a SchKG "
                f"(DLT Blanket Act 2021). In the event of {counterparty_name}'s insolvency, "
                f"your crypto-based assets would be segregated from the bankruptcy estate and "
                f"returned to you. No enhanced disclosure is required under FINMA Guidance 01/2026."
            ),
            "client_actions": [],
        }

    # Build disclosure for scenario_a, scenario_b, non_compliant
    base_risk = {
        "scenario_b": (
            f"{counterparty_name} is supervised by a Swiss self-regulatory organisation (SRO) "
            f"under the Anti-Money Laundering Act and benefits from bankruptcy protection under "
            f"Art. 242a SchKG. However, {counterparty_name} is not subject to FINMA prudential "
            f"supervision, which means it does not meet the full requirements under FINMA Guidance "
            f"01/2026 for the custody of crypto-based assets."
        ),
        "scenario_a": (
            f"{counterparty_name} is subject to prudential supervision in its home jurisdiction, "
            f"which FINMA considers broadly equivalent. However, Swiss bankruptcy protection under "
            f"Art. 242a SchKG does not apply to assets held abroad. In the event of "
            f"{counterparty_name}'s insolvency, the treatment of your assets would be governed "
            f"by the laws of {counterparty_name}'s jurisdiction, which may differ from Swiss law."
        ),
        "non_compliant": (
            f"{counterparty_name} does not currently meet FINMA Guidance 01/2026 requirements "
            f"for crypto-based asset custody. Neither equivalent prudential supervision nor "
            f"Swiss-equivalent bankruptcy protection has been confirmed. Your digital assets "
            f"({aum_str}) are at elevated risk in an insolvency scenario."
        ),
    }.get(status, "")

    # Client type modulates urgency and required actions
    if client_type == "retail":
        urgency = (
            f"As a retail client, you are entitled to the highest level of protection under "
            f"Swiss financial law. FINMA Guidance 01/2026 requires that your portfolio manager "
            f"obtain your written consent before maintaining this custody arrangement, having "
            f"fully informed you of the risks and presented suitable alternatives."
        )
        actions = [
            f"Provide written consent to continue using {counterparty_name} as custodian, "
            f"having been informed of the above risks",
            "Or instruct migration to a fully compliant FINMA-supervised custodian",
            f"Alternatives that fully comply with FINMA Guidance 01/2026: {', '.join(COMPLIANT_ALTERNATIVES[:3])}",
        ]
    elif client_type == "qualified_investor":
        urgency = (
            f"As a qualified investor under FinSA, you are presumed to have the expertise to "
            f"assess these risks independently. Your written consent to maintain this custody "
            f"arrangement is required under FINMA Guidance 01/2026, having been informed of the "
            f"applicable risks."
        )
        actions = [
            f"Confirm written consent to continue using {counterparty_name} as custodian",
            "This consent should be documented and retained by your portfolio manager",
            f"Compliant alternatives include: {', '.join(COMPLIANT_ALTERNATIVES[:2])}",
        ]
    else:  # institutional
        urgency = (
            f"As an institutional client, your risk assessment capabilities are well-established. "
            f"We note the following custody risk for your awareness and internal risk documentation."
        )
        actions = [
            f"Note this disclosure in your internal risk register regarding {counterparty_name}",
            "Consider whether your investment policy statement requires migration to a compliant custodian",
        ]

    return {
        "counterparty":        counterparty_name,
        "status":              status,
        "aum_chf":             aum_at_custodian_chf,
        "disclosure_required": True,
        "narrative": f"{base_risk}\n\n{urgency}",
        "client_actions":      actions,
        "regulatory_basis": (
            "FINMA Guidance 01/2026 on the Custody of Crypto-Based Assets, "
            "published 12 January 2026. Art. 37d BA, Art. 242a SchKG, FinSA."
        ),
        "generated_at": datetime.utcnow().isoformat(),
    }


def build_portfolio_disclosure(
    counterparty_exposures: list,
    client_type: str,
    all_counterparties: list,
) -> dict:
    """
    Build the full FINMA 01/2026 custody disclosure section for a portfolio report.
    counterparty_exposures: list of {counterparty_id, name, value_chf, pct}
    client_type: retail | qualified_investor | institutional
    all_counterparties: full counterparty records with enrichment_data, slug, etc.
    """
    cp_by_id = {cp["counterparty_id"]: cp for cp in all_counterparties}

    disclosures        = []
    compliant_items    = []
    disclosure_items   = []
    non_compliant_items = []
    total_aum_at_risk  = 0.0
    consent_required   = False

    for exposure in counterparty_exposures:
        cp_id   = exposure.get("counterparty_id")
        cp_name = exposure.get("name", "Unknown")
        aum     = exposure.get("value_chf")

        # Merge DB record with exposure data (exposure may have enriched fields)
        cp = cp_by_id.get(cp_id, {})

        # Use exposure fields as fallback when DB record is missing
        eff_slug     = cp.get("slug") or exposure.get("slug") or cp_name.lower().replace(" ", "-")
        eff_type     = cp.get("entity_type") or exposure.get("entity_type", "")
        eff_juris    = cp.get("jurisdiction") or exposure.get("jurisdiction", "")
        eff_reg      = cp.get("regulator") or exposure.get("regulator", "")
        eff_enrich   = cp.get("enrichment_data") or exposure.get("enrichment") or {}

        # Get or compute custody status
        existing_status = cp.get("finma_custody_status")
        if existing_status:
            status_info = {
                "status":                existing_status,
                "rationale":             "",
                "disclosure_required":   existing_status != "compliant",
                "consent_required":      existing_status != "compliant",
                "alternatives_required": existing_status != "compliant",
            }
        else:
            status_info = classify_custody_status(
                slug=eff_slug,
                entity_type=eff_type,
                jurisdiction=eff_juris,
                regulator=eff_reg,
                enrichment_data=eff_enrich,
            )

        disclosure = generate_disclosure(
            counterparty_name=cp_name,
            custody_info=status_info,
            client_type=client_type,
            aum_at_custodian_chf=aum,
        )
        disclosures.append(disclosure)

        if status_info["status"] == "compliant":
            compliant_items.append(cp_name)
        elif status_info["status"] == "non_compliant":
            non_compliant_items.append(cp_name)
            if aum:
                total_aum_at_risk += aum
        else:
            disclosure_items.append(cp_name)
            if aum:
                total_aum_at_risk += aum

        if status_info.get("consent_required"):
            consent_required = True

    # Overall assessment
    if non_compliant_items:
        overall = "ACTION REQUIRED"
        summary = (
            f"The portfolio includes custodians that do not meet FINMA Guidance 01/2026 "
            f"requirements: {', '.join(non_compliant_items)}. Urgent review is required."
        )
    elif disclosure_items:
        overall = "DISCLOSURE REQUIRED"
        if client_type == "institutional":
            summary = (
                f"The portfolio includes custodians operating under FINMA Guidance 01/2026 "
                f"transitional provisions: {', '.join(disclosure_items)}. "
                f"As an institutional client, these custody arrangements should be noted in your "
                f"internal risk register and reviewed against your investment policy statement."
            )
        elif client_type == "qualified_investor":
            summary = (
                f"The portfolio includes custodians operating under FINMA Guidance 01/2026 "
                f"transitional provisions: {', '.join(disclosure_items)}. "
                f"Client disclosure and documented written consent are required under Swiss regulatory obligations."
            )
        else:
            summary = (
                f"The portfolio includes custodians operating under FINMA Guidance 01/2026 "
                f"transitional provisions: {', '.join(disclosure_items)}. "
                f"As a retail client, comprehensive risk disclosure, presentation of alternative "
                f"custodians, and written consent are mandatory under Swiss regulatory obligations."
            )
    else:
        overall = "COMPLIANT"
        summary = (
            f"All counterparties in this portfolio ({', '.join(compliant_items)}) are subject to "
            f"full FINMA prudential supervision with Swiss bankruptcy protection. "
            f"No enhanced disclosure obligations arise under FINMA Guidance 01/2026."
        )

    return {
        "overall_status":         overall,
        "summary":                summary,
        "client_type":            client_type,
        "consent_required":       consent_required,
        "total_aum_at_risk_chf":  total_aum_at_risk,
        "compliant_custodians":   compliant_items,
        "disclosure_custodians":  disclosure_items,
        "non_compliant_custodians": non_compliant_items,
        "disclosures":            disclosures,
        "regulatory_basis": (
            "FINMA Guidance 01/2026 on the Custody of Crypto-Based Assets (12 January 2026). "
            "Art. 37d Banking Act, Art. 242a SchKG (DLT Blanket Act 2021), FinSA."
        ),
        "generated_at": datetime.utcnow().isoformat(),
    }
