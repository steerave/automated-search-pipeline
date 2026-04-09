# tests/test_ats_scraper.py
"""Unit tests for src/ats_scraper.py"""

def test_search_type_label_exists():
    """The 'watchlist' search_type must have a display label."""
    from src.sheets_updater import SEARCH_TYPE_LABELS
    assert "watchlist" in SEARCH_TYPE_LABELS
    assert SEARCH_TYPE_LABELS["watchlist"] == "ATS Watchlist"

def test_slug_candidates_simple():
    from src.ats_scraper import _generate_slug_candidates
    candidates = _generate_slug_candidates("Ogilvy")
    assert "ogilvy" in candidates

def test_slug_candidates_strips_suffix():
    from src.ats_scraper import _generate_slug_candidates
    candidates = _generate_slug_candidates("Huge Agency")
    assert "huge" in candidates

def test_slug_candidates_multi_word():
    from src.ats_scraper import _generate_slug_candidates
    candidates = _generate_slug_candidates("R/GA")
    assert "r-ga" in candidates or "rga" in candidates

def test_slug_candidates_inc_suffix():
    from src.ats_scraper import _generate_slug_candidates
    candidates = _generate_slug_candidates("Merkle, Inc.")
    assert "merkle" in candidates

def test_slug_candidates_empty_name():
    from src.ats_scraper import _generate_slug_candidates
    # Names that produce no valid slug return empty list
    assert _generate_slug_candidates("!!!") == []

def test_parse_date_iso():
    from src.ats_scraper import _parse_date
    from datetime import timezone
    dt = _parse_date("2026-01-15T10:30:00Z")
    assert dt is not None
    assert dt.tzinfo == timezone.utc

def test_parse_date_unix_ms():
    from src.ats_scraper import _parse_date
    # Lever uses Unix ms timestamps
    dt = _parse_date(1705312200000)
    assert dt is not None
    assert dt.year == 2024

def test_parse_date_none():
    from src.ats_scraper import _parse_date
    assert _parse_date(None) is None

def test_is_within_days_recent():
    from src.ats_scraper import _is_within_days
    from datetime import datetime, timezone, timedelta
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert _is_within_days(recent, 3) is True

def test_is_within_days_old():
    from src.ats_scraper import _is_within_days
    from datetime import datetime, timezone, timedelta
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    assert _is_within_days(old, 3) is False

def test_is_within_days_none():
    from src.ats_scraper import _is_within_days
    # Unknown date → include by default
    assert _is_within_days(None, 3) is True
