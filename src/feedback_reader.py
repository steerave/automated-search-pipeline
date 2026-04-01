"""
feedback_reader.py

Reads user feedback from the Job Search Tracker and 2026 Job Status
Google Sheets. Computes signal deltas for skip logic.
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _clean(val) -> str:
    """Strip and normalize empty-ish values."""
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "null"):
        return ""
    return s


def _parse_my_score(raw: str):
    """Extract numeric score from 'N — Label' format. Returns None if empty."""
    raw = _clean(raw)
    if not raw:
        return None
    match = re.match(r"(\d+)", raw)
    return int(match.group(1)) if match else None


def parse_tracker_feedback(rows: list) -> list:
    """
    Filter Job Tracker rows to only those with user feedback (My Score or Notes).
    Returns normalized dicts.
    """
    result = []
    for row in rows:
        my_score_raw = _clean(row.get("My Score", ""))
        notes = _clean(row.get("Notes", ""))
        if not my_score_raw and not notes:
            continue
        result.append({
            "role_name": _clean(row.get("Role Name", "")),
            "company": _clean(row.get("Company Name", "")),
            "fit_score": row.get("Fit Score", ""),
            "fit_notes": _clean(row.get("Fit Notes", "")),
            "my_score": _parse_my_score(my_score_raw),
            "notes": notes,
            "status": _clean(row.get("Status", "")),
            "date_found": _clean(row.get("Date Found", "")),
            "remote": _clean(row.get("Remote", "")),
            "location": _clean(row.get("Location", "")),
            "compensation": _clean(row.get("Compensation", "")),
            "search_type": _clean(row.get("Search Type", "")),
        })
    return result


def parse_status_rows(rows: list) -> list:
    """Convert raw Job Status sheet rows to normalized dicts."""
    result = []
    for row in rows:
        result.append({
            "role_title": _clean(row.get("Role Title", "")),
            "company": _clean(row.get("Company", "")),
            "industry": _clean(row.get("Industry", "")),
            "compensation_range": _clean(row.get("Compensation Range", "")),
            "remote_only": _clean(row.get("Remote Only", "")),
            "job_link": _clean(row.get("Direct Job Description Link", "")),
            "applied": _clean(row.get("Applied", "")),
            "application_link": _clean(row.get("Application Link", "")),
            "notes": _clean(row.get("Notes", "")),
            "status": _clean(row.get("Status", "")),
        })
    return result


def count_signals(
    tracker_feedback: list,
    status_data: list,
    last_analysis,
) -> int:
    """
    Compute number of new signals since last analysis run.
    Returns total delta across both sheets.
    """
    current_tracker = len(tracker_feedback)
    current_status = len(status_data)

    if last_analysis is None:
        return current_tracker + current_status

    prev_tracker = last_analysis.get("tracker_feedback_count", 0)
    prev_status = last_analysis.get("status_row_count", 0)

    delta = max(0, current_tracker - prev_tracker) + max(0, current_status - prev_status)
    return delta


def has_enough_signals(delta: int, threshold: int = 5) -> bool:
    """Check if enough new signals exist to justify running analysis."""
    return delta >= threshold


def load_last_analysis(path: str):
    """Load last analysis state from JSON. Returns None if file doesn't exist."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load last_analysis.json: {e}")
        return None


def save_last_analysis(path: str, tracker_count: int, status_count: int) -> None:
    """Save current analysis state to JSON."""
    from datetime import datetime
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "last_run": datetime.now().isoformat(timespec="seconds"),
        "tracker_feedback_count": tracker_count,
        "status_row_count": status_count,
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved analysis state: {tracker_count} tracker, {status_count} status")


def read_job_tracker(client, sheet_id: str) -> list:
    """Read all rows from the Job Tracker 'Jobs' tab via gspread."""
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet("Jobs")
    return worksheet.get_all_records()


def read_job_status(client, sheet_id: str) -> list:
    """Read all rows from the 2026 Job Status sheet (first tab)."""
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.sheet1
    return worksheet.get_all_records()
