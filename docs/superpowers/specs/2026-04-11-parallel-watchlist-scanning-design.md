# Parallel Watchlist Scanning — Design Spec

**Date:** 2026-04-11
**Status:** Approved

---

## Problem

The watchlist ATS scan runs serially: one company at a time, ~1 second per company. With 650+ companies in the list, the scan alone takes 10+ minutes. The full morning pipeline (JobSpy scraping + watchlist scan + Claude scoring + Sheets write + email) now runs 30+ minutes, causing the scheduled 5am run to not deliver email until well after the user wakes up. The problem compounds as more companies are added to the watchlist.

---

## Goal

Reduce the watchlist scan from 10+ minutes to under 2 minutes without losing same-day job coverage, by scanning companies in parallel.

---

## Decision: Why Parallelism Over Rotation

Two approaches were considered:

- **Rotation (scan 1/3 of companies per day):** Simpler, but misses jobs on the day they post 2/3 of the time. In a job search context, early applications have better conversion — day-3 discovery is a real cost.
- **Parallelism (scan all companies daily, concurrently):** Catches every job the same morning. Slightly more complex, but the ATS APIs are all unauthenticated public JSON endpoints designed for this usage pattern.

**Decision: parallelism.** Same-day coverage is worth the added code complexity.

---

## Architecture

### What Changes

`fetch_watchlist_jobs` in `src/ats_scraper.py` — the serial `for` loop is replaced with a `ThreadPoolExecutor`.

**New flow:**

1. Read all companies from the Watchlist sheet (unchanged)
2. Call `_get_watchlist_worksheet` once in the main thread to populate `_worksheet_cache` before workers start (the cache is lazy-initialized on first call; pre-warming ensures workers find it already populated and never race to initialize it)
3. Extract per-company logic into `_scan_company(row, row_index, config)` — a self-contained worker that returns `(jobs: list[dict], sheet_update: dict | None)`
4. Submit all companies to `ThreadPoolExecutor(max_workers=scan_workers)`, collect via `as_completed()`
5. Main thread merges all returned jobs and sheet updates
6. Single batch Google Sheets write (unchanged)

### Thread Safety

No locks needed:
- Each worker owns its own local state and returns results — no shared mutation
- `_worksheet_cache` is populated before workers start, then read-only during scan
- `requests` is thread-safe for concurrent calls
- Google Sheets batch write still happens in the main thread after all workers finish

### ATS Auto-Detection

Unknown companies (blank/unknown ATS Type) are detected inline by their worker thread (not in a separate serial phase). Acceptable because new companies are added a handful at a time, not hundreds at once.

### Config

One new field added to `config.yaml` under `watchlist:`:

```yaml
watchlist:
  scan_workers: 10   # parallel workers for ATS scanning
```

Default: `10` if not set. At 10 workers with 650 companies (~1 sec/company): ~65 seconds total vs 10+ minutes today. Configurable to tune up or down.

### Logging

A log line at scan start: `[Watchlist] Scanning N companies with X workers` confirms parallelism is active.

---

## Error Handling

Each `_scan_company` call is wrapped in try/except. On failure: logs the error, returns `([], None)`. A failed company does not affect any other worker. Behavior is identical to today's serial error handling.

---

## What Does Not Change

- All ATS fetch functions (`fetch_greenhouse`, `fetch_lever`, `fetch_ashby`, `fetch_smartrecruiters`, `fetch_recruitee`, `fetch_bamboohr`)
- ATS auto-detection logic (`detect_ats`)
- Remote detection, date filtering, job normalizers
- Google Sheets batch write (still one call, still from main thread)
- Deduplication, scoring, Sheets row insertion, email — all downstream, untouched

---

## Testing

All tests added to `tests/test_ats_scraper.py` (existing file).

1. **Worker isolation** — `_scan_company` with a valid row returns `(jobs, update)`; with a bad slug returns `([], None)` without raising
2. **Parallel assembly** — `fetch_watchlist_jobs` with 3 mocked companies returns correct combined job list and correct sheet updates (verifies futures merge logic)
3. **Worker count respected** — executor is initialized with the configured `scan_workers` value (mock executor, assert `max_workers` matches config)

---

## Expected Outcome

| Metric | Before | After |
|---|---|---|
| Watchlist scan time (650 companies) | ~10 min | ~65 sec |
| Full pipeline runtime | ~30+ min | ~20 min |
| Same-day job coverage | Yes | Yes (unchanged) |
| Code files changed | — | `src/ats_scraper.py`, `config.yaml` |
| New test cases | — | 3 in `tests/test_ats_scraper.py` |
