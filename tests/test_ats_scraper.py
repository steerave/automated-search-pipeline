# tests/test_ats_scraper.py
"""Unit tests for src/ats_scraper.py"""

def test_search_type_label_exists():
    """The 'watchlist' search_type must have a display label."""
    from src.sheets_updater import SEARCH_TYPE_LABELS
    assert "watchlist" in SEARCH_TYPE_LABELS
    assert SEARCH_TYPE_LABELS["watchlist"] == "ATS Watchlist"
