"""
Raven — Regulatory Monitor

Polls public regulatory sources daily for new publications.
When a new document is found, triggers analysis pipeline.

Sources monitored:
- FINMA: supervisory notices, circulars, guidance, risk monitor
- FCA: policy statements, Dear CEO letters, consultation papers
- SEC: staff bulletins, no-action letters on digital assets
- BIS/BCBS: crypto exposure guidelines, Basel papers

No API keys required — all public RSS/listing pages.
"""

import httpx
import hashlib
from datetime import datetime, date
from typing import Optional
from xml.etree import ElementTree as ET

from app.core.database import supabase
from app.core.config import settings


# ── Source definitions ────────────────────────────────────────

SOURCES = [
    {
        "id":       "finma_guidance",
        "name":     "FINMA Guidance",
        "regulator": "FINMA",
        "doc_type": "guidance",
        "url":      "https://www.finma.ch/en/news/supervisory-notices/",
        "rss":      "https://www.finma.ch/en/rss/news/supervisory-notices/",
    },
    {
        "id":       "finma_circulars",
        "name":     "FINMA Circulars",
        "regulator": "FINMA",
        "doc_type": "circular",
        "url":      "https://www.finma.ch/en/regulation/circulars/",
        "rss":      None,
    },
    {
        "id":       "finma_risk_monitor",
        "name":     "FINMA Risk Monitor",
        "regulator": "FINMA",
        "doc_type": "notice",
        "url":      "https://www.finma.ch/en/news/finma-risk-monitor/",
        "rss":      "https://www.finma.ch/en/rss/news/finma-risk-monitor/",
    },
    {
        "id":       "fca_policy",
        "name":     "FCA Policy Statements",
        "regulator": "FCA",
        "doc_type": "guidance",
        "url":      "https://www.fca.org.uk/news/policy-statements",
        "rss":      "https://www.fca.org.uk/rss/news-and-publications.xml",
    },
    {
        "id":       "sec_statements",
        "name":     "SEC Staff Statements",
        "regulator": "SEC",
        "doc_type": "guidance",
        "url":      "https://www.sec.gov/litigation/statements.shtml",
        "rss":      None,
    },
]

HEADERS = {
    "User-Agent": "Raven Risk Intelligence / regulatory-monitor contact@raven.internal",
    "Accept":     "application/rss+xml, application/xml, text/xml, */*",
}

# Keywords that flag documents as highly relevant to crypto/digital assets
HIGH_RELEVANCE_KEYWORDS = [
    "crypto", "digital asset", "blockchain", "distributed ledger", "dlt",
    "virtual asset", "token", "stablecoin", "bitcoin", "ethereum",
    "custody", "custodian", "safekeeping", "segregat",
    "portfolio manager", "fintech licence", "defi",
]

MEDIUM_RELEVANCE_KEYWORDS = [
    "outsourcing", "operational risk", "cyber", "third party", "due diligence",
    "aml", "money laundering", "sanctions", "capital requirement",
    "liquidity", "resolution", "recovery",
]


def _is_relevant(title: str, description: str = "") -> tuple[bool, str]:
    """
    Check if a document is relevant to crypto/digital asset custody.
    Returns (is_relevant, relevance_level).
    """
    text = (title + " " + description).lower()
    if any(kw in text for kw in HIGH_RELEVANCE_KEYWORDS):
        return True, "HIGH"
    if any(kw in text for kw in MEDIUM_RELEVANCE_KEYWORDS):
        return True, "MEDIUM"
    return False, "LOW"


def _doc_exists(url: str) -> bool:
    """Check if we've already stored this document."""
    result = (
        supabase.table("regulatory_documents")
        .select("doc_id")
        .eq("url", url)
        .execute()
    )
    return bool(result.data)


def _store_document(source: dict, title: str, url: str, published: Optional[str] = None, description: str = "") -> Optional[str]:
    """Store a new regulatory document for analysis."""
    if _doc_exists(url):
        return None

    relevant, level = _is_relevant(title, description)
    if not relevant:
        return None

    result = supabase.table("regulatory_documents").insert({
        "tenant_id":    settings.DEFAULT_TENANT_ID,
        "source":       source["id"],
        "regulator":    source["regulator"],
        "doc_type":     source["doc_type"],
        "title":        title,
        "url":          url,
        "published_date": published,
        "status":       "new",
        "criticality":  None,  # set after analysis
    }).execute()

    if result.data:
        doc_id = result.data[0]["doc_id"]
        print(f"[regulatory] New document stored: {title[:60]} ({level})")
        return doc_id
    return None


def poll_rss(source: dict) -> list:
    """Poll an RSS feed for new documents."""
    if not source.get("rss"):
        return []

    found = []
    try:
        r = httpx.get(source["rss"], headers=HEADERS, timeout=15, follow_redirects=True)
        if r.status_code != 200:
            return []

        root = ET.fromstring(r.content)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}

        # Handle both RSS 2.0 and Atom formats
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)

        for item in items[:20]:  # last 20 items
            # RSS 2.0
            title = (item.findtext("title") or item.findtext("atom:title", namespaces=ns) or "").strip()
            url   = (item.findtext("link")  or item.findtext("atom:link", namespaces=ns) or "").strip()
            desc  = (item.findtext("description") or item.findtext("atom:summary", namespaces=ns) or "").strip()
            pub   = item.findtext("pubDate") or item.findtext("atom:published", namespaces=ns)

            if not title or not url:
                continue

            # Normalise date
            pub_date = None
            if pub:
                for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
                    try:
                        pub_date = datetime.strptime(pub.strip()[:25], fmt).strftime("%Y-%m-%d")
                        break
                    except Exception:
                        continue

            doc_id = _store_document(source, title, url, pub_date, desc)
            if doc_id:
                found.append({"doc_id": doc_id, "title": title, "url": url})

    except Exception as e:
        print(f"[regulatory] RSS poll error for {source['id']}: {e}")

    return found


def check_finma_listing() -> list:
    """
    Scrape FINMA supervisory notices listing page.
    Fallback when RSS isn't available or sufficient.
    """
    found = []
    source = next(s for s in SOURCES if s["id"] == "finma_guidance")

    try:
        r = httpx.get(
            "https://www.finma.ch/en/news/supervisory-notices/",
            headers={**HEADERS, "Accept": "text/html"},
            timeout=15,
            follow_redirects=True,
        )
        if r.status_code != 200:
            return []

        # Simple extraction — find PDF links and titles
        import re
        text = r.text

        # Find document links (FINMA PDFs are predictably structured)
        pdf_pattern = re.findall(
            r'href="([^"]*finma-aufsichtsmitteilung[^"]*\.pdf[^"]*)"[^>]*>([^<]+)',
            text, re.IGNORECASE
        )
        for href, title in pdf_pattern[:10]:
            url = href if href.startswith("http") else f"https://www.finma.ch{href}"
            title = title.strip()
            doc_id = _store_document(source, title, url)
            if doc_id:
                found.append({"doc_id": doc_id, "title": title, "url": url})

    except Exception as e:
        print(f"[regulatory] FINMA listing error: {e}")

    return found


def run_monitor() -> dict:
    """
    Main monitoring run. Polls all sources, stores new documents.
    Triggers analysis for newly found documents.
    Returns summary of what was found.
    """
    from app.services.regulatory_analysis import analyse_document
    from app.workers.tasks import run_in_thread

    found_all = []

    for source in SOURCES:
        # Try RSS first
        found = poll_rss(source)
        found_all.extend(found)

    # FINMA fallback scrape
    finma_found = check_finma_listing()
    found_all.extend(finma_found)

    # Deduplicate by doc_id
    seen = set()
    unique = []
    for doc in found_all:
        if doc["doc_id"] not in seen:
            seen.add(doc["doc_id"])
            unique.append(doc)

    # Trigger analysis for each new document
    for doc in unique:
        run_in_thread(analyse_document, doc["doc_id"])

    return {
        "new_documents": len(unique),
        "documents":     unique,
        "checked_at":    datetime.utcnow().isoformat(),
    }


def add_manual_document(url: str, title: Optional[str] = None) -> dict:
    """
    Manually add a document URL for analysis.
    Used when analyst pastes a PDF link directly.
    """
    from app.services.regulatory_analysis import analyse_document
    from app.workers.tasks import run_in_thread

    if _doc_exists(url):
        existing = (
            supabase.table("regulatory_documents")
            .select("*")
            .eq("url", url)
            .single()
            .execute()
            .data
        )
        return {"status": "already_exists", "doc": existing}

    # Try to fetch title from URL if not provided
    if not title:
        try:
            r = httpx.head(url, timeout=10, follow_redirects=True)
            # Extract from URL path as fallback
            title = url.split("/")[-1].replace("-", " ").replace(".pdf", "").title()
        except Exception:
            title = url.split("/")[-1]

    doc = supabase.table("regulatory_documents").insert({
        "tenant_id":  settings.DEFAULT_TENANT_ID,
        "source":     "manual",
        "regulator":  "Manual",
        "doc_type":   "guidance",
        "title":      title or "Untitled Document",
        "url":        url,
        "status":     "new",
    }).execute()

    doc_id = doc.data[0]["doc_id"]
    run_in_thread(analyse_document, doc_id)

    return {"status": "queued", "doc_id": doc_id, "title": title}
