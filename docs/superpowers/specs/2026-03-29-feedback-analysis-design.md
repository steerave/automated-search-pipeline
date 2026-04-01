# Feedback Analysis Feature — Design Spec

**Date:** 2026-03-29
**Status:** Approved
**Author:** Sarun (Joe) Teeravechyan + Claude

---

## Summary

A standalone daily analysis script that reads user feedback from two Google Sheets — the Job Search Tracker and the 2026 Job Status sheet — to continuously improve the job search tool. It produces two outputs: a nuanced target role profile that makes fit scoring smarter, and conservative updates to `config.yaml` that make the search itself return better results over time.

## Goals

1. Close the feedback loop — user scoring and application decisions should make the tool smarter
2. Capture nuance that keywords alone cannot (e.g., "digital delivery at a SaaS company with AI exposure")
3. Be aggressive on discovery (add new titles/keywords easily) but conservative on removal (never auto-remove unless user explicitly says so)
4. Keep the user in control — all changes are logged, the profile doc is human-readable and editable

## Non-Goals

- Replacing the user's judgment — the tool suggests, the user decides
- Real-time analysis — this runs once daily, not on every sheet edit
- Multi-profile search (AI contract roles, etc.) — future workstream

---

## Architecture

### Data Flow

```
Job Tracker Sheet ──┐
(My Score, Notes,   │
 Fit Score, Status) │                                    ┌──▶ profile/target_role_profile.md
                    ├──▶ analyze_feedback.py ──▶ Claude ─┤     (nuanced preferences → fit scoring)
Job Status Sheet ───┘                                    │
(Applied roles,                                          └──▶ config.yaml updates
 Industry, Notes)                                              (new titles/keywords → search)
                                                               + logs/config_changes.log
```

### New Files

| File | Purpose |
|---|---|
| `analyze_feedback.py` | Entry point — standalone script, runs daily at 6am |
| `src/feedback_reader.py` | Reads both Google Sheets, extracts feedback data |
| `src/profile_generator.py` | Sends feedback to Claude, generates target role profile |
| `src/config_updater.py` | Parses Claude's config suggestions and applies to config.yaml |
| `profile/target_role_profile.md` | Generated output — nuanced role preferences for fit scoring |
| `data/last_analysis.json` | State — tracks last run timestamp and row counts |
| `logs/config_changes.log` | Audit trail — every config.yaml change with reason |

### Modified Files

| File | Change |
|---|---|
| `src/fit_scorer.py` | Load `target_role_profile.md` and inject into scoring prompt |
| `.env.template` | Add `GOOGLE_JOB_STATUS_SHEET_ID` |
| `.gitignore` | Add `data/last_analysis.json` |
| `requirements.txt` | Add `ruamel.yaml` (preserves comments when editing config.yaml) |
| `README.md` | Document the new feature, env var, and scheduling |

---

## Component Details

### 1. `src/feedback_reader.py`

**`read_job_tracker(sheets_client, sheet_id) -> list[dict]`**
- Connects to the Job Search Tracker spreadsheet
- Reads the "Jobs" tab
- Returns only rows where `My Score` is not empty OR `Notes` is not empty
- Each row returned as a dict with keys: `role_name`, `company`, `fit_score`, `fit_notes`, `my_score`, `notes`, `status`, `date_found`, `remote`, `location`, `compensation`

**`read_job_status(sheets_client, status_sheet_id) -> list[dict]`**
- Connects to the "2026 Job Status" spreadsheet
- Reads all rows
- Each row returned as a dict with keys: `role_title`, `company`, `industry`, `compensation_range`, `remote_only`, `job_link`, `applied`, `application_link`, `notes`, `status`

### 2. Signal Counting and Skip Logic

**State file: `data/last_analysis.json`**
```json
{
  "last_run": "2026-03-29T06:00:00",
  "tracker_feedback_count": 42,
  "status_row_count": 15
}
```

**Logic:**
1. Load current counts: tracker rows with feedback + status sheet total rows
2. Load `last_analysis.json` (if missing, treat as first run — always proceed)
3. Compute delta: `(current_tracker_feedback - last_tracker_feedback) + (current_status_rows - last_status_rows)`
4. If delta < 5, log "Not enough new signals ({delta}/5), skipping analysis" and exit
5. If delta >= 5, proceed with analysis

**What counts as a signal:**
- Job Tracker: a row where `My Score` or `Notes` has a value (only user-provided feedback counts, not AI-scored-only rows)
- Job Status: any row (each applied role is a signal)

### 3. `src/profile_generator.py`

**`generate_target_profile(tracker_data, status_data, current_profile, client) -> str`**

Sends all feedback data to Claude with a structured prompt:

**Prompt structure:**
```
You are an expert career advisor analyzing a job seeker's feedback to build their ideal role profile.

CURRENT TARGET PROFILE (if exists):
{current_profile_text}

JOB TRACKER FEEDBACK (roles the user has scored and commented on):
{formatted_tracker_data}

APPLICATION HISTORY (roles the user has actually applied for):
{formatted_status_data}

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
Format as a clean markdown document with sections.
```

**Output:** Writes the returned markdown to `profile/target_role_profile.md`

### 4. `src/config_updater.py`

**`generate_config_suggestions(tracker_data, status_data, current_config, client) -> dict`**

A separate Claude call that analyzes the same data but outputs structured config changes.

**Prompt structure:**
```
You are analyzing a job seeker's feedback to suggest search configuration improvements.

CURRENT CONFIG:
{current_config_yaml}

JOB TRACKER FEEDBACK:
{formatted_tracker_data}

APPLICATION HISTORY:
{formatted_status_data}

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

Respond with a JSON object:
{
  "add_job_titles": ["title1", "title2"],
  "remove_job_titles": [],
  "add_required_keywords": ["keyword1"],
  "add_exclude_keywords": [],
  "remove_exclude_keywords": [],
  "reasoning": {
    "title1": "why this title is being added",
    "keyword1": "why this keyword is being added"
  }
}

Only include non-empty arrays. If no changes are warranted, return an empty object {}.
```

**`apply_config_updates(config_path, suggestions) -> list[str]`**
- Reads current `config.yaml`
- Applies additions/removals from the suggestions dict
- Writes updated `config.yaml` preserving comments and structure (using ruamel.yaml or careful string manipulation)
- Returns a list of human-readable change descriptions for the log

**Change logging:**
Every change is appended to `logs/config_changes.log`:
```
[2026-03-29 06:02:15] ADDED job_title: "Director of AI Implementation"
  Reason: User applied to 3 AI implementation roles and rated them 4-5
[2026-03-29 06:02:15] ADDED required_keyword: "platform modernization"
  Reason: Recurring theme in high-scored roles (5 of 8 top-rated roles mention this)
```

### 5. Changes to `src/fit_scorer.py`

**Loading the profile:**
At module level or in `score_job()`, load `profile/target_role_profile.md` if it exists:

```python
def _load_target_profile() -> str:
    profile_path = Path(__file__).parent.parent / "profile" / "target_role_profile.md"
    if profile_path.exists():
        return profile_path.read_text(encoding="utf-8")
    return ""
```

**Prompt modification:**
Add a new section to `FIT_SCORE_PROMPT` between the candidate profile and the job posting:

```
TARGET ROLE PREFERENCES (learned from candidate's own feedback and application history):
{target_role_profile}

Use these preferences to inform your scoring. If the target profile indicates the candidate
prefers certain industries, company types, or role characteristics, weight those in your score.
A role that matches the candidate's stated preferences should score higher than one that
only matches on paper qualifications.
```

If `target_role_profile` is empty (no analysis has run yet), this section is omitted entirely — scoring works exactly as it does today.

### 6. `analyze_feedback.py` — Entry Point

**Pipeline:**
1. Load `.env` and `config.yaml`
2. Set up logging
3. Authenticate with Google Sheets (reuse existing service account)
4. Read Job Tracker feedback via `feedback_reader.read_job_tracker()`
5. Read Job Status data via `feedback_reader.read_job_status()`
6. Check signal count against `data/last_analysis.json` — exit if < 5 new signals
7. Initialize Anthropic client
8. Generate target role profile via `profile_generator.generate_target_profile()`
9. Generate config suggestions via `config_updater.generate_config_suggestions()`
10. Apply config updates via `config_updater.apply_config_updates()`
11. Log all changes to `logs/config_changes.log`
12. Update `data/last_analysis.json` with current counts and timestamp
13. Log summary and exit

**CLI args:**
- `--force` — skip the 5-signal threshold check (useful for first run or manual trigger)
- `--dry-run` — show what would change without writing anything
- `--config` — path to config.yaml (default: project root)
- `--env` — path to .env file (default: project root)

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `GOOGLE_JOB_STATUS_SHEET_ID` | Sheet ID for the "2026 Job Status" spreadsheet |
| `GOOGLE_SHEETS_ID` | (existing) Sheet ID for the Job Search Tracker |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | (existing) Path to service account credentials |
| `ANTHROPIC_API_KEY` | (existing) Claude API key |

---

## Scheduling

**Windows Task Scheduler entry:**
- Name: `Job Search — Feedback Analysis`
- Trigger: Daily at 6:00 AM
- Action: `python analyze_feedback.py`
- Start in: `C:\Users\steerave\Desktop\Claude Projects\Job Search Tool`
- Runs after the existing 5:00 AM job scraper

---

## Cost Estimate

| Component | Tokens per run | Est. cost per run |
|---|---|---|
| Profile generation (read sheets + Claude analysis) | ~8,000–15,000 | ~$0.02–0.06 |
| Config suggestion (separate Claude call) | ~5,000–10,000 | ~$0.01–0.04 |
| **Total per daily run** | ~13,000–25,000 | **~$0.03–0.10** |
| **Monthly (30 runs, many skipped)** | — | **~$0.50–1.50** |

Most days will skip due to the 5-signal threshold, so actual monthly cost is likely under $1.

---

## Asymmetric Change Rules — Summary

| Action | Auto threshold | Explicit-only |
|---|---|---|
| Add job title | 2+ high-scored or applied roles with shared pattern | — |
| Add required keyword | Recurring positive signal | — |
| Add exclude keyword | — | User must write "exclude"/"remove" in Notes |
| Remove job title | — | User must write "stop searching" in Notes |
| Remove required keyword | Never | Manual config.yaml edit only |
| Lower fit score for poor matches | Automatic via target profile | — |

---

## Testing Plan

1. **Unit tests** for `feedback_reader.py` — mock gspread responses, verify dict structure
2. **Unit tests** for `config_updater.py` — verify asymmetric rules (additions happen, removals don't without explicit signals)
3. **Integration test** — dry-run with real sheets to verify end-to-end flow
4. **Manual verification** — run `--force --dry-run`, inspect proposed profile and config changes
5. **Regression** — run existing `main.py --dry-run` to confirm fit scoring still works with and without the target profile
