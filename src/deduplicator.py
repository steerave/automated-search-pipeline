"""
deduplicator.py

Tracks seen job IDs to avoid re-processing the same jobs across runs.
Uses a JSON file (data/seen_jobs.json) as persistent storage.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_SEEN_JOBS_PATH = "data/seen_jobs.json"


def _make_job_id(job: dict) -> str:
    """
    Generate a stable unique ID for a job based on company + title.
    Intentionally excludes URL so the same job posted on multiple boards
    (LinkedIn, Indeed, etc.) is correctly identified as a duplicate.
    """
    company = job.get("company", "").strip().lower()
    title = job.get("title", "").strip().lower()
    key = f"{company}||{title}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def load_seen_jobs(path: str = DEFAULT_SEEN_JOBS_PATH) -> dict:
    """
    Load seen jobs from JSON file.
    Returns a dict: {job_id: {"first_seen": "ISO date", "title": "...", "company": "..."}}
    """
    if not os.path.exists(path):
        logger.info(f"No seen_jobs file found at {path} — starting fresh")
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} seen job IDs from {path}")
        return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not load seen_jobs.json: {e} — starting fresh")
        return {}


def save_seen_jobs(seen: dict, path: str = DEFAULT_SEEN_JOBS_PATH) -> None:
    """Save seen jobs dict to JSON file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(seen)} seen job IDs to {path}")


def prune_old_entries(seen: dict, retention_days: int = 90) -> dict:
    """Remove entries older than retention_days to keep the file lean."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    pruned = {}
    removed = 0
    for job_id, meta in seen.items():
        try:
            first_seen = datetime.fromisoformat(meta["first_seen"].replace("Z", "+00:00"))
            if first_seen.tzinfo is None:
                first_seen = first_seen.replace(tzinfo=timezone.utc)
            if first_seen >= cutoff:
                pruned[job_id] = meta
            else:
                removed += 1
        except (KeyError, ValueError):
            pruned[job_id] = meta  # Keep entries with unparseable dates

    if removed:
        logger.info(f"Pruned {removed} old entries from seen_jobs (>{retention_days} days)")
    return pruned


def filter_new_jobs(jobs: list[dict], seen: dict) -> tuple[list[dict], list[dict]]:
    """
    Split jobs into new (unseen) and duplicate (already seen) lists.
    Deduplicates both against seen_jobs.json AND within the current batch
    (same job appearing from multiple search queries or boards).
    Adds a 'job_id' field to each job dict.
    Returns: (new_jobs, duplicate_jobs)
    """
    new_jobs = []
    duplicates = []
    seen_this_run = set()  # Track within-batch duplicates

    for job in jobs:
        job_id = _make_job_id(job)
        job["job_id"] = job_id

        if job_id in seen or job_id in seen_this_run:
            duplicates.append(job)
            logger.debug(f"Duplicate: {job.get('title')} @ {job.get('company')}")
        else:
            seen_this_run.add(job_id)
            new_jobs.append(job)

    logger.info(f"Deduplication: {len(new_jobs)} new, {len(duplicates)} duplicates")
    return new_jobs, duplicates


def mark_jobs_seen(jobs: list[dict], seen: dict) -> dict:
    """
    Add all jobs in the list to the seen dict.
    Each entry stores first_seen timestamp + title/company for debugging.
    Returns the updated seen dict.
    """
    now = datetime.now(timezone.utc).isoformat()
    for job in jobs:
        job_id = job.get("job_id") or _make_job_id(job)
        if job_id not in seen:
            seen[job_id] = {
                "first_seen": now,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
            }
    return seen
