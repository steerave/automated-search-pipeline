# Feedback Analysis Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily feedback analysis script that reads user scoring from two Google Sheets and produces a target role profile + config.yaml updates to continuously improve job search quality.

**Architecture:** Standalone `analyze_feedback.py` entry point orchestrates three focused modules: `feedback_reader.py` (reads both sheets), `profile_generator.py` (Claude generates nuanced role profile), `config_updater.py` (Claude suggests + applies config changes with asymmetric add/remove rules). The generated `profile/target_role_profile.md` is injected into the existing `fit_scorer.py` prompt.

**Tech Stack:** Python 3.11+, gspread (Google Sheets), anthropic (Claude API), ruamel.yaml (comment-preserving YAML edits), pytest (testing)

---

## File Structure

### New Files

| File | Responsibility |
|---|---|
| `src/feedback_reader.py` | Read Job Tracker and Job Status Google Sheets, return structured dicts |
| `src/profile_generator.py` | Send feedback data to Claude, return target role profile markdown |
| `src/config_updater.py` | Send feedback data to Claude for config suggestions, apply changes to config.yaml |
| `analyze_feedback.py` | Entry point — orchestrates the full analysis pipeline |
| `tests/test_feedback_reader.py` | Unit tests for sheet reading and signal counting |
| `tests/test_config_updater.py` | Unit tests for asymmetric add/remove rules and YAML writing |
| `tests/test_profile_generator.py` | Unit tests for prompt building and profile output |
| `tests/test_analyze_feedback.py` | Integration test for the full pipeline |
| `tests/conftest.py` | Shared pytest fixtures (mock sheets data, mock Claude responses) |
| `CHANGELOG.md` | Project changelog (new file — doesn't exist yet) |

### Modified Files

| File | Change |
|---|---|
| `src/fit_scorer.py` | Add `_load_target_profile()`, inject into `FIT_SCORE_PROMPT` |
| `.env.template` | Add `GOOGLE_JOB_STATUS_SHEET_ID` |
| `.gitignore` | Add `data/last_analysis.json`, `profile/target_role_profile.md` |
| `requirements.txt` | Add `ruamel.yaml>=0.18.0`, `pytest>=8.0.0` |
| `README.md` | Document feedback analysis feature, new env var, scheduling |
| `CLAUDE.md` | Add `analyze_feedback.py` to project structure |

---

## Task 0: Project Scaffolding

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/__init__.py`
- Create: `CHANGELOG.md`
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Modify: `.env.template`

- [ ] **Step 1: Create test directory and conftest with shared fixtures**

```python
# tests/__init__.py
# (empty)
```

```python
# tests/conftest.py
"""Shared fixtures for feedback analysis tests."""

import pytest


@pytest.fixture
def sample_tracker_rows():
    """Rows from the Job Tracker sheet — simulates gspread get_all_records()."""
    return [
        {
            "Date Found": "2026-03-15",
            "Search Type": "National Remote",
            "Role Name": "Director Digital Delivery",
            "Company Name": "Acme SaaS Corp",
            "Employment Type": "Full-time",
            "Remote": "Yes",
            "Compensation": "$180,000 - $220,000",
            "Location": "Remote",
            "Fit Score": 8,
            "Fit Notes": "Strong delivery leadership match",
            "Job Description": "Lead digital delivery for SaaS platform...",
            "Direct Link": "https://example.com/job/123",
            "Resume File": "",
            "Cover Letter File": "",
            "Status": "Applied",
            "Notes": "Great culture, AI-forward company",
            "My Score": "5 — Perfect fit",
        },
        {
            "Date Found": "2026-03-15",
            "Search Type": "National Remote",
            "Role Name": "Director of Ecommerce",
            "Company Name": "RetailCo",
            "Employment Type": "Full-time",
            "Remote": "No",
            "Compensation": "$150,000 - $180,000",
            "Location": "Chicago, IL",
            "Fit Score": 6,
            "Fit Notes": "Some delivery overlap but ecommerce focused",
            "Job Description": "Manage ecommerce platform operations...",
            "Direct Link": "https://example.com/job/456",
            "Resume File": "",
            "Cover Letter File": "",
            "Status": "New",
            "Notes": "Not really my area, exclude ecommerce director roles",
            "My Score": "1 — Poor fit",
        },
        {
            "Date Found": "2026-03-16",
            "Search Type": "Local QC",
            "Role Name": "Senior TPM",
            "Company Name": "TechStartup Inc",
            "Employment Type": "Full-time",
            "Remote": "Hybrid",
            "Compensation": "",
            "Location": "Davenport, IA",
            "Fit Score": 7,
            "Fit Notes": "Good TPM match, local role",
            "Job Description": "Technical program management for AI platform...",
            "Direct Link": "https://example.com/job/789",
            "Resume File": "",
            "Cover Letter File": "",
            "Status": "New",
            "Notes": "",
            "My Score": "4 — Good fit",
        },
        {
            "Date Found": "2026-03-17",
            "Search Type": "National Remote",
            "Role Name": "VP Technology Delivery",
            "Company Name": "BigCorp",
            "Employment Type": "Full-time",
            "Remote": "Yes",
            "Compensation": "$250,000+",
            "Location": "Remote",
            "Fit Score": 9,
            "Fit Notes": "Excellent match",
            "Job Description": "Lead technology delivery org...",
            "Direct Link": "https://example.com/job/101",
            "Resume File": "",
            "Cover Letter File": "",
            "Status": "New",
            "Notes": "",
            "My Score": "",
        },
    ]


@pytest.fixture
def sample_status_rows():
    """Rows from the 2026 Job Status sheet — simulates gspread get_all_records()."""
    return [
        {
            "Role Title": "Director Digital Delivery",
            "Company": "Acme SaaS Corp",
            "Industry": "SaaS / Technology",
            "Compensation Range": "$180,000 - $220,000",
            "Remote Only": "Yes",
            "Direct Job Description Link": "https://example.com/job/123",
            "Applied": "Yes",
            "Application Link": "https://acme.com/careers/apply",
            "Notes": "AI-forward company, great mission",
            "Status": "Interviewing",
        },
        {
            "Role Title": "Senior Director Program Management",
            "Company": "CloudPlatform Co",
            "Industry": "Cloud / AI",
            "Compensation Range": "$200,000 - $240,000",
            "Remote Only": "Yes",
            "Direct Job Description Link": "https://example.com/job/200",
            "Applied": "Yes",
            "Application Link": "https://cloudplatform.com/apply",
            "Notes": "Found via recruiter, strong AI focus",
            "Status": "Applied",
        },
    ]


@pytest.fixture
def sample_last_analysis():
    """Previous analysis state."""
    return {
        "last_run": "2026-03-20T06:00:00",
        "tracker_feedback_count": 1,
        "status_row_count": 0,
    }


@pytest.fixture
def sample_config():
    """Minimal config.yaml content for testing."""
    return {
        "job_titles": [
            "Senior Director Digital Delivery",
            "Director Digital Delivery",
            "Director Technical Program Management",
        ],
        "required_keywords": [
            "delivery",
            "program management",
            "digital transformation",
        ],
        "exclude_keywords": [
            "digital marketing",
            "entry level",
            "supply chain",
        ],
        "exclude_companies": [],
        "min_fit_score": 5,
    }
```

- [ ] **Step 2: Update requirements.txt**

Add these two lines to the end of `requirements.txt`:

```
# Comment-preserving YAML editing
ruamel.yaml>=0.18.0

# Testing
pytest>=8.0.0
```

- [ ] **Step 3: Update .gitignore**

Add after the `data/seen_jobs.json` line:

```
data/last_analysis.json
```

Add after the `profile/linkedin_export/` line:

```
profile/target_role_profile.md
```

- [ ] **Step 4: Update .env.template**

Add after the `GOOGLE_SERVICE_ACCOUNT_JSON` line:

```
# Google Sheet ID for 2026 Job Status tracker (applied roles)
# The ID is in your sheet URL: docs.google.com/spreadsheets/d/SHEET_ID/edit
GOOGLE_JOB_STATUS_SHEET_ID=your_job_status_sheet_id_here
```

- [ ] **Step 5: Create CHANGELOG.md**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Feedback analysis pipeline (`analyze_feedback.py`) — reads user scoring from Job Tracker and Job Status sheets
- Target role profile generation — Claude analyzes feedback patterns to build nuanced role preferences
- Automatic config.yaml refinement — adds new job titles and keywords based on user scoring patterns
- Asymmetric change rules — aggressive on adding new search terms, conservative on removing (explicit user request only)
- Config change audit trail (`logs/config_changes.log`)
- Signal-based skip logic — only runs analysis when 5+ new feedback signals exist
- `--force` and `--dry-run` flags for manual control
- Target role profile injection into fit scoring prompt for smarter job matching
```

- [ ] **Step 6: Install new dependencies**

Run: `pip install ruamel.yaml pytest`

- [ ] **Step 7: Verify pytest runs**

Run: `python -m pytest tests/ -v`

Expected: `no tests ran` (0 collected) — confirms test infrastructure works

- [ ] **Step 8: Commit scaffolding**

```bash
git add tests/conftest.py tests/__init__.py CHANGELOG.md requirements.txt .gitignore .env.template
git commit -m "$(cat <<'EOF'
feat: add test scaffolding and dependencies for feedback analysis

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 1: Feedback Reader — Sheet Reading + Signal Counting

**Files:**
- Create: `src/feedback_reader.py`
- Test: `tests/test_feedback_reader.py`

- [ ] **Step 1: Write failing tests for feedback_reader**

```python
# tests/test_feedback_reader.py
"""Tests for feedback_reader — sheet reading and signal counting."""

from unittest.mock import MagicMock
from feedback_reader import (
    parse_tracker_feedback,
    parse_status_rows,
    count_signals,
    has_enough_signals,
)


class TestParseTrackerFeedback:
    """parse_tracker_feedback filters to rows with user feedback only."""

    def test_returns_only_rows_with_my_score(self, sample_tracker_rows):
        result = parse_tracker_feedback(sample_tracker_rows)
        # Row 0 has My Score "5 — Perfect fit", row 1 has "1 — Poor fit",
        # row 2 has "4 — Good fit", row 3 has empty My Score but no Notes either
        titles = [r["role_name"] for r in result]
        assert "Director Digital Delivery" in titles
        assert "Director of Ecommerce" in titles
        assert "Senior TPM" in titles
        assert "VP Technology Delivery" not in titles

    def test_returns_rows_with_notes_even_without_my_score(self, sample_tracker_rows):
        # Modify row 3 to have Notes but no My Score
        sample_tracker_rows[3]["Notes"] = "Interesting but too senior"
        sample_tracker_rows[3]["My Score"] = ""
        result = parse_tracker_feedback(sample_tracker_rows)
        titles = [r["role_name"] for r in result]
        assert "VP Technology Delivery" in titles

    def test_returns_empty_for_no_feedback(self):
        rows = [
            {
                "Role Name": "Some Role",
                "Company Name": "SomeCo",
                "My Score": "",
                "Notes": "",
                "Fit Score": 7,
                "Fit Notes": "Good match",
                "Date Found": "2026-03-15",
                "Search Type": "National Remote",
                "Employment Type": "Full-time",
                "Remote": "Yes",
                "Compensation": "",
                "Location": "Remote",
                "Job Description": "...",
                "Direct Link": "",
                "Resume File": "",
                "Cover Letter File": "",
                "Status": "New",
            }
        ]
        result = parse_tracker_feedback(rows)
        assert result == []

    def test_extracts_numeric_my_score(self, sample_tracker_rows):
        result = parse_tracker_feedback(sample_tracker_rows)
        scores = {r["role_name"]: r["my_score"] for r in result}
        assert scores["Director Digital Delivery"] == 5
        assert scores["Director of Ecommerce"] == 1
        assert scores["Senior TPM"] == 4

    def test_output_dict_keys(self, sample_tracker_rows):
        result = parse_tracker_feedback(sample_tracker_rows)
        expected_keys = {
            "role_name", "company", "fit_score", "fit_notes", "my_score",
            "notes", "status", "date_found", "remote", "location",
            "compensation", "search_type",
        }
        assert set(result[0].keys()) == expected_keys


class TestParseStatusRows:
    """parse_status_rows converts raw sheet rows to structured dicts."""

    def test_returns_all_rows(self, sample_status_rows):
        result = parse_status_rows(sample_status_rows)
        assert len(result) == 2

    def test_output_dict_keys(self, sample_status_rows):
        result = parse_status_rows(sample_status_rows)
        expected_keys = {
            "role_title", "company", "industry", "compensation_range",
            "remote_only", "job_link", "applied", "application_link",
            "notes", "status",
        }
        assert set(result[0].keys()) == expected_keys

    def test_handles_empty_list(self):
        result = parse_status_rows([])
        assert result == []


class TestCountSignals:
    """count_signals computes delta from last analysis state."""

    def test_counts_new_signals(self, sample_tracker_rows, sample_status_rows, sample_last_analysis):
        tracker_feedback = parse_tracker_feedback(sample_tracker_rows)
        status_data = parse_status_rows(sample_status_rows)
        delta = count_signals(tracker_feedback, status_data, sample_last_analysis)
        # 3 tracker feedback rows (was 1) + 2 status rows (was 0) = delta of 4
        assert delta == 4

    def test_first_run_counts_all(self, sample_tracker_rows, sample_status_rows):
        tracker_feedback = parse_tracker_feedback(sample_tracker_rows)
        status_data = parse_status_rows(sample_status_rows)
        delta = count_signals(tracker_feedback, status_data, None)
        # First run: all rows are new — 3 tracker + 2 status = 5
        assert delta == 5

    def test_no_new_signals(self, sample_tracker_rows, sample_status_rows):
        tracker_feedback = parse_tracker_feedback(sample_tracker_rows)
        status_data = parse_status_rows(sample_status_rows)
        last = {"last_run": "2026-03-28T06:00:00", "tracker_feedback_count": 3, "status_row_count": 2}
        delta = count_signals(tracker_feedback, status_data, last)
        assert delta == 0


class TestHasEnoughSignals:
    """has_enough_signals applies the threshold."""

    def test_below_threshold(self):
        assert has_enough_signals(4, threshold=5) is False

    def test_at_threshold(self):
        assert has_enough_signals(5, threshold=5) is True

    def test_above_threshold(self):
        assert has_enough_signals(10, threshold=5) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/test_feedback_reader.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'feedback_reader'`

- [ ] **Step 3: Implement feedback_reader.py**

```python
# src/feedback_reader.py
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


def _parse_my_score(raw: str) -> int | None:
    """Extract numeric score from 'N — Label' format. Returns None if empty."""
    raw = _clean(raw)
    if not raw:
        return None
    match = re.match(r"(\d+)", raw)
    return int(match.group(1)) if match else None


def parse_tracker_feedback(rows: list[dict]) -> list[dict]:
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


def parse_status_rows(rows: list[dict]) -> list[dict]:
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
    tracker_feedback: list[dict],
    status_data: list[dict],
    last_analysis: dict | None,
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


def load_last_analysis(path: str) -> dict | None:
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


def read_job_tracker(client, sheet_id: str) -> list[dict]:
    """Read all rows from the Job Tracker 'Jobs' tab via gspread."""
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet("Jobs")
    return worksheet.get_all_records()


def read_job_status(client, sheet_id: str) -> list[dict]:
    """Read all rows from the 2026 Job Status sheet (first tab)."""
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.sheet1
    return worksheet.get_all_records()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/test_feedback_reader.py -v`

Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/feedback_reader.py tests/test_feedback_reader.py
git commit -m "$(cat <<'EOF'
feat: add feedback_reader — sheet reading and signal counting

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 2: Profile Generator — Claude Analysis to Target Profile

**Files:**
- Create: `src/profile_generator.py`
- Test: `tests/test_profile_generator.py`

- [ ] **Step 1: Write failing tests for profile_generator**

```python
# tests/test_profile_generator.py
"""Tests for profile_generator — prompt building and profile output."""

import json
from unittest.mock import MagicMock, patch
from feedback_reader import parse_tracker_feedback, parse_status_rows
from profile_generator import (
    format_tracker_for_prompt,
    format_status_for_prompt,
    build_profile_prompt,
    generate_target_profile,
)


class TestFormatTrackerForPrompt:
    """format_tracker_for_prompt creates readable text from tracker data."""

    def test_includes_role_and_scores(self, sample_tracker_rows):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        text = format_tracker_for_prompt(tracker)
        assert "Director Digital Delivery" in text
        assert "Acme SaaS Corp" in text
        assert "My Score: 5" in text

    def test_includes_notes(self, sample_tracker_rows):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        text = format_tracker_for_prompt(tracker)
        assert "Great culture, AI-forward company" in text

    def test_empty_list_returns_none_message(self):
        text = format_tracker_for_prompt([])
        assert "No feedback" in text


class TestFormatStatusForPrompt:
    """format_status_for_prompt creates readable text from status data."""

    def test_includes_applied_roles(self, sample_status_rows):
        status = parse_status_rows(sample_status_rows)
        text = format_status_for_prompt(status)
        assert "Acme SaaS Corp" in text
        assert "Director Digital Delivery" in text

    def test_includes_industry(self, sample_status_rows):
        status = parse_status_rows(sample_status_rows)
        text = format_status_for_prompt(status)
        assert "SaaS / Technology" in text

    def test_empty_list_returns_none_message(self):
        text = format_status_for_prompt([])
        assert "No application" in text


class TestBuildProfilePrompt:
    """build_profile_prompt assembles the full prompt for Claude."""

    def test_includes_all_sections(self, sample_tracker_rows, sample_status_rows):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        status = parse_status_rows(sample_status_rows)
        prompt = build_profile_prompt(tracker, status, current_profile="")
        assert "JOB TRACKER FEEDBACK" in prompt
        assert "APPLICATION HISTORY" in prompt
        assert "target role profile" in prompt.lower()

    def test_includes_current_profile_when_provided(self, sample_tracker_rows, sample_status_rows):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        status = parse_status_rows(sample_status_rows)
        prompt = build_profile_prompt(tracker, status, current_profile="# My current profile")
        assert "CURRENT TARGET PROFILE" in prompt
        assert "# My current profile" in prompt


class TestGenerateTargetProfile:
    """generate_target_profile calls Claude and returns markdown."""

    def test_returns_claude_response(self, sample_tracker_rows, sample_status_rows):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        status = parse_status_rows(sample_status_rows)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="# Target Role Profile\n\nPrefers SaaS delivery roles.")]
        mock_client.messages.create.return_value = mock_response

        result = generate_target_profile(tracker, status, "", mock_client)
        assert "Target Role Profile" in result
        assert "SaaS" in result
        mock_client.messages.create.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/test_profile_generator.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'profile_generator'`

- [ ] **Step 3: Implement profile_generator.py**

```python
# src/profile_generator.py
"""
profile_generator.py

Sends user feedback data to Claude to generate a nuanced target role profile.
The profile is written to profile/target_role_profile.md and used by fit_scorer.py.
"""

import logging

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are an expert career advisor analyzing a job seeker's feedback patterns.
Your job is to synthesize their scoring, notes, and application history into a clear,
actionable target role profile. Be specific and evidence-based."""

PROFILE_PROMPT_TEMPLATE = """You are an expert career advisor analyzing a job seeker's feedback to build their ideal role profile.

{current_profile_section}

JOB TRACKER FEEDBACK (roles the user has scored and commented on):
{tracker_text}

APPLICATION HISTORY (roles the user has actually applied for):
{status_text}

Based on this data, generate an updated target role profile in markdown format.

The profile should capture:
- Ideal role titles and seniority level
- Preferred industries and company types
- Domain preferences (e.g., SaaS, AI/ML, digital transformation)
- Key skills and responsibilities the user gravitates toward
- Work arrangement preferences (remote, hybrid, location)
- Compensation expectations
- Patterns in what the user rates highly vs. poorly
- Patterns in what the user actually applies for vs. skips
- Nuanced preferences that keywords alone cannot capture

Be specific and evidence-based. Reference actual roles and scores from the data.
Format as a clean markdown document with sections."""


def format_tracker_for_prompt(tracker_data: list[dict]) -> str:
    """Format tracker feedback data into readable text for the prompt."""
    if not tracker_data:
        return "No feedback data available yet."

    lines = []
    for row in tracker_data:
        line = f"- {row['role_name']} @ {row['company']}"
        line += f" | AI Score: {row['fit_score']}/10"
        if row['my_score'] is not None:
            line += f" | My Score: {row['my_score']}/5"
        if row['remote']:
            line += f" | Remote: {row['remote']}"
        if row['compensation']:
            line += f" | Comp: {row['compensation']}"
        if row['location']:
            line += f" | Location: {row['location']}"
        if row['status']:
            line += f" | Status: {row['status']}"
        if row['notes']:
            line += f"\n  Notes: {row['notes']}"
        if row['fit_notes']:
            line += f"\n  AI Notes: {row['fit_notes']}"
        lines.append(line)
    return "\n".join(lines)


def format_status_for_prompt(status_data: list[dict]) -> str:
    """Format application history into readable text for the prompt."""
    if not status_data:
        return "No application history available yet."

    lines = []
    for row in status_data:
        line = f"- {row['role_title']} @ {row['company']}"
        if row['industry']:
            line += f" | Industry: {row['industry']}"
        if row['compensation_range']:
            line += f" | Comp: {row['compensation_range']}"
        if row['remote_only']:
            line += f" | Remote: {row['remote_only']}"
        if row['applied']:
            line += f" | Applied: {row['applied']}"
        if row['status']:
            line += f" | Status: {row['status']}"
        if row['notes']:
            line += f"\n  Notes: {row['notes']}"
        lines.append(line)
    return "\n".join(lines)


def build_profile_prompt(
    tracker_data: list[dict],
    status_data: list[dict],
    current_profile: str,
) -> str:
    """Assemble the full prompt for Claude."""
    if current_profile:
        current_section = f"CURRENT TARGET PROFILE (update and refine this):\n{current_profile}"
    else:
        current_section = "CURRENT TARGET PROFILE:\nNo existing profile — this is the first generation."

    return PROFILE_PROMPT_TEMPLATE.format(
        current_profile_section=current_section,
        tracker_text=format_tracker_for_prompt(tracker_data),
        status_text=format_status_for_prompt(status_data),
    )


def generate_target_profile(
    tracker_data: list[dict],
    status_data: list[dict],
    current_profile: str,
    client,
) -> str:
    """
    Call Claude to generate an updated target role profile.

    Args:
        tracker_data: Parsed tracker feedback rows
        status_data: Parsed job status rows
        current_profile: Current profile markdown (empty string if none)
        client: anthropic.Anthropic client instance

    Returns:
        Markdown string with the updated target role profile
    """
    prompt = build_profile_prompt(tracker_data, status_data, current_profile)

    logger.info("Generating target role profile via Claude...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    profile_text = response.content[0].text.strip()
    logger.info(f"Generated profile: {len(profile_text)} chars")
    return profile_text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/test_profile_generator.py -v`

Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/profile_generator.py tests/test_profile_generator.py
git commit -m "$(cat <<'EOF'
feat: add profile_generator — Claude-powered target role profiling

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 3: Config Updater — Asymmetric Add/Remove Rules

**Files:**
- Create: `src/config_updater.py`
- Test: `tests/test_config_updater.py`

- [ ] **Step 1: Write failing tests for config_updater**

```python
# tests/test_config_updater.py
"""Tests for config_updater — asymmetric add/remove rules and YAML writing."""

import json
import os
import tempfile
from unittest.mock import MagicMock
from feedback_reader import parse_tracker_feedback, parse_status_rows
from config_updater import (
    build_config_prompt,
    parse_config_suggestions,
    apply_config_updates,
    log_config_changes,
    generate_config_suggestions,
)


class TestBuildConfigPrompt:
    """build_config_prompt assembles the prompt with asymmetric rules."""

    def test_includes_current_config(self, sample_tracker_rows, sample_status_rows, sample_config):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        status = parse_status_rows(sample_status_rows)
        prompt = build_config_prompt(tracker, status, sample_config)
        assert "Senior Director Digital Delivery" in prompt
        assert "ADDING" in prompt
        assert "REMOVING" in prompt

    def test_includes_asymmetric_rules(self, sample_tracker_rows, sample_status_rows, sample_config):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        status = parse_status_rows(sample_status_rows)
        prompt = build_config_prompt(tracker, status, sample_config)
        assert "NEVER suggest removing required_keywords" in prompt
        assert "explicitly requests exclusion" in prompt


class TestParseConfigSuggestions:
    """parse_config_suggestions handles Claude's JSON response."""

    def test_parses_valid_json(self):
        raw = json.dumps({
            "add_job_titles": ["Director of AI Implementation"],
            "add_required_keywords": ["AI platform"],
            "reasoning": {
                "Director of AI Implementation": "User applied to 2 AI roles"
            }
        })
        result = parse_config_suggestions(raw)
        assert result["add_job_titles"] == ["Director of AI Implementation"]
        assert result["add_required_keywords"] == ["AI platform"]

    def test_handles_empty_response(self):
        result = parse_config_suggestions("{}")
        assert result.get("add_job_titles", []) == []
        assert result.get("remove_job_titles", []) == []

    def test_handles_json_in_code_block(self):
        raw = '```json\n{"add_job_titles": ["New Title"]}\n```'
        result = parse_config_suggestions(raw)
        assert result["add_job_titles"] == ["New Title"]

    def test_returns_empty_on_invalid_json(self):
        result = parse_config_suggestions("not json at all")
        assert result == {}


class TestApplyConfigUpdates:
    """apply_config_updates modifies config.yaml correctly."""

    def test_adds_new_job_title(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "job_titles:\n  - \"Director Digital Delivery\"\n\n"
            "required_keywords:\n  - \"delivery\"\n\n"
            "exclude_keywords:\n  - \"supply chain\"\n"
        )
        suggestions = {"add_job_titles": ["Director of AI Implementation"]}
        changes = apply_config_updates(str(config_file), suggestions)
        assert len(changes) == 1
        assert "Director of AI Implementation" in changes[0]

        content = config_file.read_text()
        assert "Director of AI Implementation" in content
        assert "Director Digital Delivery" in content  # original preserved

    def test_adds_required_keyword(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "job_titles:\n  - \"Director\"\n\n"
            "required_keywords:\n  - \"delivery\"\n\n"
            "exclude_keywords:\n  - \"supply chain\"\n"
        )
        suggestions = {"add_required_keywords": ["AI platform"]}
        changes = apply_config_updates(str(config_file), suggestions)
        assert len(changes) == 1
        content = config_file.read_text()
        assert "AI platform" in content

    def test_does_not_add_duplicate_title(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "job_titles:\n  - \"Director Digital Delivery\"\n\n"
            "required_keywords:\n  - \"delivery\"\n\n"
            "exclude_keywords:\n  - \"supply chain\"\n"
        )
        suggestions = {"add_job_titles": ["Director Digital Delivery"]}
        changes = apply_config_updates(str(config_file), suggestions)
        assert len(changes) == 0

    def test_removes_title_only_when_in_suggestions(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "job_titles:\n  - \"Director Digital Delivery\"\n  - \"Bad Title\"\n\n"
            "required_keywords:\n  - \"delivery\"\n\n"
            "exclude_keywords:\n  - \"supply chain\"\n"
        )
        suggestions = {"remove_job_titles": ["Bad Title"]}
        changes = apply_config_updates(str(config_file), suggestions)
        assert len(changes) == 1
        content = config_file.read_text()
        assert "Bad Title" not in content
        assert "Director Digital Delivery" in content

    def test_empty_suggestions_no_changes(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        original = "job_titles:\n  - \"Director\"\n\nrequired_keywords:\n  - \"delivery\"\n\nexclude_keywords:\n  - \"supply chain\"\n"
        config_file.write_text(original)
        changes = apply_config_updates(str(config_file), {})
        assert len(changes) == 0


class TestLogConfigChanges:
    """log_config_changes writes to the audit log."""

    def test_appends_to_log_file(self, tmp_path):
        log_file = tmp_path / "config_changes.log"
        changes = [
            'ADDED job_title: "Director of AI Implementation"',
            'ADDED required_keyword: "AI platform"',
        ]
        reasoning = {
            "Director of AI Implementation": "User applied to 2 AI roles",
            "AI platform": "Recurring theme in high-scored roles",
        }
        log_config_changes(str(log_file), changes, reasoning)
        content = log_file.read_text()
        assert "Director of AI Implementation" in content
        assert "User applied to 2 AI roles" in content


class TestGenerateConfigSuggestions:
    """generate_config_suggestions calls Claude and returns parsed suggestions."""

    def test_calls_claude_and_parses(self, sample_tracker_rows, sample_status_rows, sample_config):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        status = parse_status_rows(sample_status_rows)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "add_job_titles": ["Director of AI Delivery"],
            "reasoning": {"Director of AI Delivery": "AI trend in applied roles"},
        }))]
        mock_client.messages.create.return_value = mock_response

        result = generate_config_suggestions(tracker, status, sample_config, mock_client)
        assert "add_job_titles" in result
        assert "Director of AI Delivery" in result["add_job_titles"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/test_config_updater.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'config_updater'`

- [ ] **Step 3: Implement config_updater.py**

```python
# src/config_updater.py
"""
config_updater.py

Uses Claude to suggest config.yaml changes based on user feedback.
Applies asymmetric rules: aggressive on adding, conservative on removing.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are an expert career advisor analyzing a job seeker's feedback
to suggest search configuration improvements. Be conservative on removals
and aggressive on discovering new search terms."""

CONFIG_PROMPT_TEMPLATE = """You are analyzing a job seeker's feedback to suggest search configuration improvements.

CURRENT CONFIG:
Job Titles: {job_titles}
Required Keywords: {required_keywords}
Exclude Keywords: {exclude_keywords}

JOB TRACKER FEEDBACK:
{tracker_text}

APPLICATION HISTORY:
{status_text}

Suggest changes to the job search configuration. You MUST follow these rules:

ADDING (low threshold — be aggressive):
- Suggest new job_titles if 2+ applied roles or 2+ high-scored roles (My Score 4-5) share a title pattern not already in the search
- Suggest new required_keywords if a positive theme recurs in high-scored roles or applied roles
- Suggest new exclude_keywords ONLY if the user explicitly requests exclusion in their Notes (look for phrases like "exclude", "stop showing", "remove", "don't search for", "irrelevant")

REMOVING (high threshold — almost never):
- Suggest removing a job_title ONLY if the user explicitly says to stop searching for it in their Notes
- NEVER suggest removing required_keywords automatically
- NEVER suggest removing exclude_keywords

For roles that match poorly but aren't explicitly excluded by the user:
- Do NOT suggest removing them from the search
- Instead, note them so the target role profile can lower their fit score

Respond ONLY with a JSON object:
{{
  "add_job_titles": ["title1", "title2"],
  "remove_job_titles": [],
  "add_required_keywords": ["keyword1"],
  "add_exclude_keywords": [],
  "reasoning": {{
    "title1": "why this title is being added",
    "keyword1": "why this keyword is being added"
  }}
}}

Only include non-empty arrays. If no changes are warranted, return an empty object {{}}.
Do NOT include keys with empty arrays."""


def build_config_prompt(
    tracker_data: list[dict],
    status_data: list[dict],
    current_config: dict,
) -> str:
    """Assemble the config suggestion prompt."""
    from profile_generator import format_tracker_for_prompt, format_status_for_prompt

    return CONFIG_PROMPT_TEMPLATE.format(
        job_titles="\n".join(f"  - {t}" for t in current_config.get("job_titles", [])),
        required_keywords="\n".join(f"  - {k}" for k in current_config.get("required_keywords", [])),
        exclude_keywords="\n".join(f"  - {k}" for k in current_config.get("exclude_keywords", [])),
        tracker_text=format_tracker_for_prompt(tracker_data),
        status_text=format_status_for_prompt(status_data),
    )


def parse_config_suggestions(raw: str) -> dict:
    """Parse Claude's JSON response into a suggestions dict."""
    raw = raw.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse config suggestions: {raw[:200]}")
        return {}


def generate_config_suggestions(
    tracker_data: list[dict],
    status_data: list[dict],
    current_config: dict,
    client,
) -> dict:
    """Call Claude to get config change suggestions."""
    prompt = build_config_prompt(tracker_data, status_data, current_config)

    logger.info("Generating config suggestions via Claude...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    suggestions = parse_config_suggestions(raw)
    logger.info(f"Config suggestions: {json.dumps(suggestions, indent=2)}")
    return suggestions


def apply_config_updates(config_path: str, suggestions: dict) -> list[str]:
    """
    Apply additions/removals to config.yaml using ruamel.yaml to preserve comments.
    Returns a list of human-readable change descriptions.
    """
    yaml = YAML()
    yaml.preserve_quotes = True

    with open(config_path, encoding="utf-8") as f:
        config = yaml.load(f)

    changes = []

    # Add job titles
    for title in suggestions.get("add_job_titles", []):
        existing = [str(t).lower() for t in config.get("job_titles", [])]
        if title.lower() not in existing:
            config["job_titles"].append(title)
            changes.append(f'ADDED job_title: "{title}"')

    # Remove job titles (only from explicit user request)
    for title in suggestions.get("remove_job_titles", []):
        titles = config.get("job_titles", [])
        for i, existing in enumerate(titles):
            if str(existing).lower() == title.lower():
                titles.pop(i)
                changes.append(f'REMOVED job_title: "{title}"')
                break

    # Add required keywords
    for kw in suggestions.get("add_required_keywords", []):
        existing = [str(k).lower() for k in config.get("required_keywords", [])]
        if kw.lower() not in existing:
            config["required_keywords"].append(kw)
            changes.append(f'ADDED required_keyword: "{kw}"')

    # Add exclude keywords (only from explicit user request)
    for kw in suggestions.get("add_exclude_keywords", []):
        existing = [str(k).lower() for k in config.get("exclude_keywords", [])]
        if kw.lower() not in existing:
            config["exclude_keywords"].append(kw)
            changes.append(f'ADDED exclude_keyword: "{kw}"')

    if changes:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f)
        logger.info(f"Applied {len(changes)} config changes")

    return changes


def log_config_changes(log_path: str, changes: list[str], reasoning: dict) -> None:
    """Append config changes to the audit log."""
    if not changes:
        return

    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    for change in changes:
        lines.append(f"[{timestamp}] {change}")
        # Try to find a matching reasoning entry
        for key, reason in reasoning.items():
            if key.lower() in change.lower():
                lines.append(f"  Reason: {reason}")
                break

    with open(p, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n")

    logger.info(f"Logged {len(changes)} config changes to {log_path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/test_config_updater.py -v`

Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/config_updater.py tests/test_config_updater.py
git commit -m "$(cat <<'EOF'
feat: add config_updater — asymmetric config.yaml updates from feedback

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 4: Fit Scorer Integration — Load Target Profile into Scoring Prompt

**Files:**
- Modify: `src/fit_scorer.py:1-63`
- Test: `tests/test_fit_scorer_profile.py`

- [ ] **Step 1: Write failing tests for target profile loading**

```python
# tests/test_fit_scorer_profile.py
"""Tests for fit_scorer target profile integration."""

import tempfile
from pathlib import Path
from unittest.mock import patch

# We need to set up the path before importing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fit_scorer import _load_target_profile, FIT_SCORE_PROMPT


class TestLoadTargetProfile:
    """_load_target_profile reads the profile file if it exists."""

    def test_returns_content_when_file_exists(self, tmp_path):
        profile = tmp_path / "target_role_profile.md"
        profile.write_text("# Target Profile\nPrefers SaaS delivery roles.")
        with patch("fit_scorer.Path") as mock_path_cls:
            # Make the function use our tmp_path
            mock_path = mock_path_cls.return_value.__truediv__.return_value.__truediv__.return_value
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = "# Target Profile\nPrefers SaaS delivery roles."
            result = _load_target_profile()
        assert "SaaS delivery" in result

    def test_returns_empty_when_file_missing(self):
        with patch("fit_scorer.Path") as mock_path_cls:
            mock_path = mock_path_cls.return_value.__truediv__.return_value.__truediv__.return_value
            mock_path.exists.return_value = False
            result = _load_target_profile()
        assert result == ""


class TestFitScorePromptIncludesProfile:
    """FIT_SCORE_PROMPT must include target_role_profile placeholder."""

    def test_prompt_has_profile_placeholder(self):
        assert "{target_role_profile}" in FIT_SCORE_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/test_fit_scorer_profile.py -v`

Expected: FAIL — `ImportError` (no `_load_target_profile` or `{target_role_profile}` in prompt)

- [ ] **Step 3: Modify fit_scorer.py — add profile loading and prompt injection**

Add this import at the top of `src/fit_scorer.py` (after line 3):

```python
from pathlib import Path
```

Add this function after the `logger` definition (after line 13):

```python
def _load_target_profile() -> str:
    """Load target role profile if it exists. Returns empty string if not found."""
    profile_path = Path(__file__).parent.parent / "profile" / "target_role_profile.md"
    if profile_path.exists():
        return profile_path.read_text(encoding="utf-8")
    return ""
```

Modify `FIT_SCORE_PROMPT` — insert this section between the Education block and the `JOB POSTING:` line (between the current lines `---` after education and `JOB POSTING:`):

```
{target_role_section}
JOB POSTING:
```

Where `{target_role_section}` is built dynamically. To achieve this, modify the `score_job` function. After the `prompt = FIT_SCORE_PROMPT.format(...)` call (around line 144), add logic to inject the profile:

Replace the existing `FIT_SCORE_PROMPT` string — change the section between `Education:` and `JOB POSTING:` from:

```
Education:
{education_text}

---

JOB POSTING:
```

to:

```
Education:
{education_text}

{target_role_profile}
---

JOB POSTING:
```

Then in the `score_job` function, build the `target_role_profile` format value. Modify the `prompt = FIT_SCORE_PROMPT.format(...)` call to include:

```python
    # Build target role profile section
    target_profile = _load_target_profile()
    if target_profile:
        target_section = (
            "TARGET ROLE PREFERENCES (learned from candidate's own feedback and application history):\n"
            f"{target_profile}\n\n"
            "Use these preferences to inform your scoring. If the target profile indicates the candidate\n"
            "prefers certain industries, company types, or role characteristics, weight those in your score.\n"
            "A role that matches the candidate's stated preferences should score higher than one that\n"
            "only matches on paper qualifications.\n"
        )
    else:
        target_section = ""

    prompt = FIT_SCORE_PROMPT.format(
        name=profile.get("name", "Candidate"),
        headline=profile.get("headline", ""),
        summary=profile.get("summary", "")[:500] if profile.get("summary") else "",
        skills=profile_texts["skills"],
        experience_text=profile_texts["experience_text"],
        education_text=profile_texts["education_text"],
        target_role_profile=target_section,
        job_title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        job_type=job.get("job_type", ""),
        salary=salary,
        job_description=description,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/test_fit_scorer_profile.py -v`

Expected: All 3 tests PASS

- [ ] **Step 5: Run existing fit_scorer tests (regression)**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/ -v`

Expected: All tests PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add src/fit_scorer.py tests/test_fit_scorer_profile.py
git commit -m "$(cat <<'EOF'
feat: inject target role profile into fit scoring prompt

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 5: Entry Point — analyze_feedback.py

**Files:**
- Create: `analyze_feedback.py`
- Test: `tests/test_analyze_feedback.py`

- [ ] **Step 1: Write failing test for the pipeline**

```python
# tests/test_analyze_feedback.py
"""Integration test for the analyze_feedback pipeline."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestAnalyzeFeedbackPipeline:
    """End-to-end test for the analysis pipeline with mocked externals."""

    def test_dry_run_does_not_write_files(self, tmp_path, sample_tracker_rows, sample_status_rows):
        """Dry run prints proposed changes but writes nothing."""
        from analyze_feedback import run_analysis

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "job_titles:\n  - \"Director Digital Delivery\"\n\n"
            "required_keywords:\n  - \"delivery\"\n\n"
            "exclude_keywords:\n  - \"supply chain\"\n"
        )
        profile_path = tmp_path / "target_role_profile.md"
        state_path = tmp_path / "last_analysis.json"
        log_path = tmp_path / "config_changes.log"

        mock_sheets_client = MagicMock()
        mock_anthropic_client = MagicMock()

        # Mock Claude responses
        profile_response = MagicMock()
        profile_response.content = [MagicMock(text="# Target Profile\nPrefers SaaS.")]
        config_response = MagicMock()
        config_response.content = [MagicMock(text='{"add_job_titles": ["AI Director"]}')]
        mock_anthropic_client.messages.create.side_effect = [profile_response, config_response]

        result = run_analysis(
            sheets_client=mock_sheets_client,
            anthropic_client=mock_anthropic_client,
            tracker_rows=sample_tracker_rows,
            status_rows=sample_status_rows,
            config_path=str(config_file),
            profile_path=str(profile_path),
            state_path=str(state_path),
            log_path=str(log_path),
            force=True,
            dry_run=True,
        )

        assert result["skipped"] is False
        assert not profile_path.exists()
        assert not state_path.exists()
        content = config_file.read_text()
        assert "AI Director" not in content

    def test_full_run_writes_all_outputs(self, tmp_path, sample_tracker_rows, sample_status_rows):
        """Full run writes profile, updates config, saves state."""
        from analyze_feedback import run_analysis

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "job_titles:\n  - \"Director Digital Delivery\"\n\n"
            "required_keywords:\n  - \"delivery\"\n\n"
            "exclude_keywords:\n  - \"supply chain\"\n"
        )
        profile_path = tmp_path / "target_role_profile.md"
        state_path = tmp_path / "last_analysis.json"
        log_path = tmp_path / "config_changes.log"

        mock_sheets_client = MagicMock()
        mock_anthropic_client = MagicMock()

        profile_response = MagicMock()
        profile_response.content = [MagicMock(text="# Target Profile\nPrefers SaaS.")]
        config_response = MagicMock()
        config_response.content = [MagicMock(text='{"add_job_titles": ["AI Director"], "reasoning": {"AI Director": "trend"}}')]
        mock_anthropic_client.messages.create.side_effect = [profile_response, config_response]

        result = run_analysis(
            sheets_client=mock_sheets_client,
            anthropic_client=mock_anthropic_client,
            tracker_rows=sample_tracker_rows,
            status_rows=sample_status_rows,
            config_path=str(config_file),
            profile_path=str(profile_path),
            state_path=str(state_path),
            log_path=str(log_path),
            force=True,
            dry_run=False,
        )

        assert result["skipped"] is False
        assert profile_path.exists()
        assert "SaaS" in profile_path.read_text()
        assert state_path.exists()
        config_content = config_file.read_text()
        assert "AI Director" in config_content

    def test_skips_when_not_enough_signals(self, tmp_path, sample_tracker_rows, sample_status_rows):
        """Skips analysis when below signal threshold."""
        from analyze_feedback import run_analysis

        config_file = tmp_path / "config.yaml"
        config_file.write_text("job_titles:\n  - \"Director\"\n\nrequired_keywords:\n  - \"delivery\"\n\nexclude_keywords:\n  - \"supply chain\"\n")
        state_path = tmp_path / "last_analysis.json"
        # Set counts to match current data — no new signals
        state_path.write_text(json.dumps({
            "last_run": "2026-03-28T06:00:00",
            "tracker_feedback_count": 3,
            "status_row_count": 2,
        }))

        mock_sheets_client = MagicMock()
        mock_anthropic_client = MagicMock()

        result = run_analysis(
            sheets_client=mock_sheets_client,
            anthropic_client=mock_anthropic_client,
            tracker_rows=sample_tracker_rows,
            status_rows=sample_status_rows,
            config_path=str(config_file),
            profile_path=str(tmp_path / "target_role_profile.md"),
            state_path=str(state_path),
            log_path=str(tmp_path / "config_changes.log"),
            force=False,
            dry_run=False,
        )

        assert result["skipped"] is True
        mock_anthropic_client.messages.create.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/test_analyze_feedback.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'analyze_feedback'`

- [ ] **Step 3: Implement analyze_feedback.py**

```python
# analyze_feedback.py
"""
analyze_feedback.py

Entry point for the daily feedback analysis pipeline.
Reads user feedback from two Google Sheets, generates a target role profile,
and suggests config.yaml updates.

Usage:
    python analyze_feedback.py              # Normal run (skips if < 5 signals)
    python analyze_feedback.py --force      # Force run regardless of signal count
    python analyze_feedback.py --dry-run    # Preview changes without writing
"""

import argparse
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logger = logging.getLogger(__name__)


def setup_logging(log_dir: str, log_level: str = "INFO") -> None:
    from datetime import date
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / f"{date.today().isoformat()}.log"
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def load_config(config_path: str) -> dict:
    import yaml
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env(env_path: str = ".env") -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        logger.warning("python-dotenv not installed — reading from system env only")


def run_analysis(
    sheets_client,
    anthropic_client,
    tracker_rows: list[dict],
    status_rows: list[dict],
    config_path: str,
    profile_path: str,
    state_path: str,
    log_path: str,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Core analysis pipeline. Accepts pre-fetched sheet data for testability.

    Returns dict with keys: skipped, signal_delta, profile_generated, config_changes
    """
    from feedback_reader import (
        parse_tracker_feedback, parse_status_rows,
        count_signals, has_enough_signals,
        load_last_analysis, save_last_analysis,
    )
    from profile_generator import generate_target_profile
    from config_updater import (
        generate_config_suggestions, apply_config_updates, log_config_changes,
    )

    result = {
        "skipped": False,
        "signal_delta": 0,
        "profile_generated": False,
        "config_changes": [],
    }

    # Parse sheet data
    tracker_data = parse_tracker_feedback(tracker_rows)
    status_data = parse_status_rows(status_rows)

    logger.info(f"Tracker feedback rows: {len(tracker_data)}")
    logger.info(f"Status rows: {len(status_data)}")

    # Signal check
    last_analysis = load_last_analysis(state_path)
    delta = count_signals(tracker_data, status_data, last_analysis)
    result["signal_delta"] = delta

    if not force and not has_enough_signals(delta):
        logger.info(f"Not enough new signals ({delta}/5), skipping analysis")
        result["skipped"] = True
        return result

    logger.info(f"New signals: {delta} — proceeding with analysis")

    # Load current profile if it exists
    profile_file = Path(profile_path)
    current_profile = ""
    if profile_file.exists():
        current_profile = profile_file.read_text(encoding="utf-8")

    # Generate target role profile
    logger.info("=" * 60)
    logger.info("STEP 1: Generating target role profile...")
    logger.info("=" * 60)
    new_profile = generate_target_profile(
        tracker_data, status_data, current_profile, anthropic_client
    )

    if dry_run:
        logger.info("DRY RUN — Profile that would be written:")
        logger.info(new_profile[:500])
    else:
        profile_file.parent.mkdir(parents=True, exist_ok=True)
        profile_file.write_text(new_profile, encoding="utf-8")
        logger.info(f"Wrote target role profile to {profile_path}")
    result["profile_generated"] = True

    # Generate and apply config suggestions
    logger.info("=" * 60)
    logger.info("STEP 2: Generating config suggestions...")
    logger.info("=" * 60)
    config = load_config(config_path)
    suggestions = generate_config_suggestions(
        tracker_data, status_data, config, anthropic_client
    )

    if not suggestions or suggestions == {}:
        logger.info("No config changes suggested")
    elif dry_run:
        logger.info("DRY RUN — Config changes that would be applied:")
        for key, vals in suggestions.items():
            if key != "reasoning" and vals:
                logger.info(f"  {key}: {vals}")
    else:
        changes = apply_config_updates(config_path, suggestions)
        result["config_changes"] = changes
        reasoning = suggestions.get("reasoning", {})
        log_config_changes(log_path, changes, reasoning)

    # Save state
    if not dry_run:
        save_last_analysis(state_path, len(tracker_data), len(status_data))

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Feedback Analysis — improve job search from your scoring data",
    )
    parser.add_argument("--force", action="store_true", help="Skip signal threshold check")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    parser.add_argument("--env", default=str(PROJECT_ROOT / ".env"))
    args = parser.parse_args()

    load_env(args.env)
    config = load_config(args.config)
    setup_logging(
        str(PROJECT_ROOT / config.get("log_dir", "logs")),
        config.get("log_level", "INFO"),
    )

    logger.info("=" * 60)
    logger.info("Feedback Analysis — Starting")
    if args.force:
        logger.info("*** FORCE MODE — skipping signal threshold ***")
    if args.dry_run:
        logger.info("*** DRY RUN — no writes ***")
    logger.info("=" * 60)

    # Authenticate
    from feedback_reader import read_job_tracker, read_job_status
    from sheets_updater import _get_client
    import anthropic

    sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheets_id = os.getenv("GOOGLE_SHEETS_ID")
    status_sheet_id = os.getenv("GOOGLE_JOB_STATUS_SHEET_ID")
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not all([sa_path, sheets_id, status_sheet_id, api_key]):
        logger.error("Missing required env vars. Check .env file.")
        sys.exit(1)

    sheets_client = _get_client(sa_path)
    anthropic_client = anthropic.Anthropic(api_key=api_key)

    # Read sheets
    logger.info("Reading Google Sheets...")
    tracker_rows = read_job_tracker(sheets_client, sheets_id)
    status_rows = read_job_status(sheets_client, status_sheet_id)

    # Run analysis
    result = run_analysis(
        sheets_client=sheets_client,
        anthropic_client=anthropic_client,
        tracker_rows=tracker_rows,
        status_rows=status_rows,
        config_path=args.config,
        profile_path=str(PROJECT_ROOT / "profile" / "target_role_profile.md"),
        state_path=str(PROJECT_ROOT / "data" / "last_analysis.json"),
        log_path=str(PROJECT_ROOT / "logs" / "config_changes.log"),
        force=args.force,
        dry_run=args.dry_run,
    )

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("ANALYSIS COMPLETE")
    if result["skipped"]:
        logger.info(f"  Skipped (signals: {result['signal_delta']}/5)")
    else:
        logger.info(f"  Signals: {result['signal_delta']}")
        logger.info(f"  Profile generated: {result['profile_generated']}")
        logger.info(f"  Config changes: {len(result['config_changes'])}")
        for change in result["config_changes"]:
            logger.info(f"    - {change}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/ -v`

Expected: All tests PASS (feedback_reader, profile_generator, config_updater, fit_scorer_profile, analyze_feedback)

- [ ] **Step 5: Commit**

```bash
git add analyze_feedback.py tests/test_analyze_feedback.py
git commit -m "$(cat <<'EOF'
feat: add analyze_feedback.py — daily feedback analysis entry point

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 6: Documentation and Final Commit

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `CHANGELOG.md` (verify up to date)

- [ ] **Step 1: Update README.md — add Feedback Analysis section**

Add after the "Daily Usage" section (after line 107), before "Manual Run":

```markdown
---

## Feedback Analysis

The tool learns from your feedback. Score jobs in the tracker (`My Score` column) and log your applications in the "2026 Job Status" sheet — the feedback analyzer uses both to:

1. **Generate a target role profile** (`profile/target_role_profile.md`) — a nuanced description of your ideal role that makes AI scoring smarter
2. **Refine search config** (`config.yaml`) — adds new job titles and keywords when patterns emerge in your scoring

### How It Works

- Runs daily at 6am (after the 5am scrape) via Windows Task Scheduler
- Only runs when **5+ new signals** exist (scored jobs or applied roles)
- **Aggressive on discovery** — quickly adds new titles/keywords based on your preferences
- **Conservative on removal** — never auto-removes search terms unless you explicitly say so in your Notes (e.g., "exclude ecommerce director roles")
- All config changes are logged to `logs/config_changes.log`

### Manual Run
```bash
# Normal run (skips if < 5 new signals)
python analyze_feedback.py

# Force run regardless of signal count
python analyze_feedback.py --force

# Preview changes without writing
python analyze_feedback.py --dry-run

# Both
python analyze_feedback.py --force --dry-run
```

### Setup

1. Share your "2026 Job Status" Google Sheet with the same service account email
2. Add the sheet ID to `.env`:
   ```
   GOOGLE_JOB_STATUS_SHEET_ID=your_sheet_id_here
   ```
3. Schedule in Task Scheduler: daily at 6:00 AM, same setup as the main tool

### Scoring Guide (My Score column)

| Score | Meaning | Effect |
|---|---|---|
| 5 — Perfect fit | Exactly what I'm looking for | Strongly influences profile toward similar roles |
| 4 — Good fit | Very relevant, would apply | Moderate positive signal |
| 3 — Moderate fit | Some relevance, on the fence | Neutral |
| 2 — Weak fit | Mostly irrelevant | Lowers priority of similar roles |
| 1 — Poor fit | Completely wrong | Strong negative signal in profile |
```

- [ ] **Step 2: Update README.md — update Project Structure**

In the Project Structure section, add after the `data/seen_jobs.json` line:

```
│   └── last_analysis.json        # Feedback analysis state
```

Add after the `├── profile/` section:

```
│   └── target_role_profile.md    # Auto-generated by feedback analyzer
```

Add `analyze_feedback.py` to the top-level listing:

```
├── analyze_feedback.py           # Feedback analysis (daily at 6am)
```

- [ ] **Step 3: Update README.md — update Costs section**

Add after the Claude API cost line:

```
- **Feedback analysis:** ~$0.03–$0.10 per run (most days skipped)
```

- [ ] **Step 4: Update README.md — add .env variable**

In the `.env` example block, add:

```
GOOGLE_JOB_STATUS_SHEET_ID=your_job_status_sheet_id
```

- [ ] **Step 5: Update CLAUDE.md — add analyze_feedback.py to project structure**

Add `analyze_feedback.py` to the project structure section.

- [ ] **Step 6: Verify CHANGELOG.md is up to date**

The CHANGELOG.md created in Task 0 should already list all features. Read it and confirm nothing is missing.

- [ ] **Step 7: Run full test suite one final time**

Run: `cd "C:/Users/steerave/Desktop/Claude Projects/Job Search Tool" && python -m pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 8: Commit everything together**

```bash
git add README.md CLAUDE.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
docs: add feedback analysis to README, CLAUDE.md, and CHANGELOG

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 7: Manual Integration Test

This task is NOT automated — it requires the user's real Google Sheets.

- [ ] **Step 1: Verify .env has the new variable**

Confirm `GOOGLE_JOB_STATUS_SHEET_ID` is set in `.env` with the real sheet ID.

- [ ] **Step 2: Share the Job Status sheet with the service account**

In Google Sheets, share the "2026 Job Status" sheet with the service account email (same one used for the Job Tracker).

- [ ] **Step 3: Run dry-run with force**

Run: `python analyze_feedback.py --force --dry-run`

Expected:
- Reads both sheets successfully
- Prints proposed target role profile
- Prints proposed config changes (if any)
- Writes nothing

- [ ] **Step 4: Run full analysis**

Run: `python analyze_feedback.py --force`

Expected:
- Writes `profile/target_role_profile.md`
- Updates `config.yaml` (if changes suggested)
- Creates `data/last_analysis.json`
- Logs changes to `logs/config_changes.log`

- [ ] **Step 5: Verify fit scoring uses the profile**

Run: `python main.py --dry-run`

Expected: Jobs are scored. Check logs for any errors related to profile loading.

- [ ] **Step 6: Review generated profile**

Open `profile/target_role_profile.md` and verify it makes sense — reflects your actual preferences.

- [ ] **Step 7: Review config changes**

Open `logs/config_changes.log` and `config.yaml` — verify any additions are reasonable.
