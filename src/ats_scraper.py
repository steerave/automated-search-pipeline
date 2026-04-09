"""
ats_scraper.py

Fetches jobs directly from company ATS (Applicant Tracking System) endpoints.
Supports: Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, BambooHR.

Companies are read from the "Watchlist" tab in Google Sheets. Unknown companies
are auto-detected (ATS type + slug probed and cached back to the sheet).
"""

import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

WATCHLIST_SHEET = "Watchlist"
WATCHLIST_HEADERS = ["Company Name", "ATS Type", "Slug", "Status", "Date Added", "Last Scanned"]

PROBE_DELAY = 0.2   # seconds between ATS probe requests
REQUEST_TIMEOUT = 10  # seconds per HTTP request

_STRIP_SUFFIXES = [
    ", inc.", ", llc", ", corp.", ", ltd.", ", co.",
    " inc", " llc", " corp", " ltd", " co",
    " agency", " digital", " group", " media", " marketing",
    " communications", " interactive", " creative", " solutions",
]


def _generate_slug_candidates(company_name: str) -> list[str]:
    """Generate likely ATS slug candidates from a company name."""
    name = company_name.lower().strip()
    for suffix in _STRIP_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
            break
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    candidates = [slug]
    no_hyphens = slug.replace("-", "")
    if no_hyphens != slug:
        candidates.append(no_hyphens)
    return list(dict.fromkeys(candidates))


def _parse_date(value) -> datetime | None:
    """Parse a date value (ISO string or Unix ms int) into a UTC datetime."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            ts = value / 1000 if value > 1e10 else value
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _is_within_days(value, days: int) -> bool:
    """Return True if value parses to a date within the last N days. Unknown dates return True."""
    dt = _parse_date(value)
    if dt is None:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return dt >= cutoff
