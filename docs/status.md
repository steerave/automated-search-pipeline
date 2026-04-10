# Project Status Log

## 2026-04-09

**Done:**
- Built `src/ats_scraper.py` — full ATS watchlist scanner with 6 adapters (Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, BambooHR)
- ATS auto-detection: probes endpoints using slug candidates generated from company names, caches result back to Google Sheet
- Per-ATS remote detection (uses platform-native fields: `isRemote`, `workplaceType`, location text), date extraction, and job normalization to standard 14-field dict via shared `_make_job()` helper
- Google Sheets "Watchlist" tab read/write: `read_watchlist()`, `update_watchlist_detection()`, `update_watchlist_last_scanned()`
- `fetch_watchlist_jobs()` orchestrator: reads watchlist, detects unknowns, fetches remote jobs within `lookback_days`, returns normalized dicts
- Integrated into `job_scraper.py` via `scrape_watchlist()` + updated `scrape_all_jobs()` — watchlist is now a third job source alongside national_remote and local_qc
- 43 unit tests in `tests/test_ats_scraper.py` covering all adapters, remote detectors, normalizers, auto-detection, and orchestrator
- End-to-end dry run confirmed: Apple/Microsoft/Amazon → smartrecruiters, Ogilvy → greenhouse — all detected and written back to sheet

**In Progress:**
- Nothing — feature is complete and pushed

**Next:**
- Populate Watchlist tab with full 600+ company list (user generating this separately)
- Address two tech debt items flagged in final review: (1) duplicated GSheets auth logic between ats_scraper.py and sheets_updater.py, (2) orphaned YAML entries in config.yaml
- Start career strategy expansion: multi-profile AI search, career-advisor skill, networking tracker

**Notes:**
- `lookback_days: 3` is the right default — 0 watchlist jobs in dry run is expected behavior (large companies don't post matching remote roles every 3 days)
- ATS coverage estimate: ~55-65% of a digital marketing company list; Workday/iCIMS companies are covered by the existing daily JobSpy scrape via LinkedIn/Indeed syndication
- Plan saved at `docs/superpowers/plans/2026-04-09-ats-watchlist-scanner.md`

## 2026-04-03

**Done:**
- Fixed config_updater truncated JSON parsing — increased max_tokens from 2000 to 4096 and added fallback parser to recover suggestions from partial responses
- Ran first real feedback analysis: 17 new signals processed, 34 config changes applied (12 job titles, 10 required keywords, 12 exclude keywords)
- Target role profile regenerated from tracker feedback and application history
- Created Windows Task Scheduler task "Job Search Feedback Analysis" for daily 6am runs
- Added 2 new tests for truncated JSON recovery in config_updater

**In Progress:**
- config.yaml, profile/target_role_profile.md, and data/last_analysis.json updated by feedback analysis but not yet committed

**Next:**
- Commit feedback analysis results and bug fix
- Start career strategy expansion: multi-profile AI search, career-advisor skill, networking tracker

**Notes:**
- The 6am feedback task was never scheduled before today — only the 5am main search was in Task Scheduler
- Feedback analysis confirmed working end-to-end with real sheet data (70 tracker rows, 56 status rows)

## 2026-04-01

**Done:**
- Added feedback_reader module — reads Google Sheets feedback and counts signals
- Added profile_generator — Claude-powered target role profiling from resume + feedback
- Injected target role profile into fit scoring prompt for better job matching
- Added config_updater — asymmetric config.yaml updates driven by feedback analysis
- Added analyze_feedback.py entry point for daily feedback analysis pipeline
- Fixed Windows UTF-8 logging and increased config suggestion max_tokens
- Fixed config updater YAML indentation; added run_feedback.bat launcher
- Updated README, CLAUDE.md, and CHANGELOG for feedback analysis feature
- Created `/status` skill and added Daily Status Log standard to global CLAUDE.md

**In Progress:**
- config.yaml has uncommitted local changes (likely from config_updater testing)

**Next:**
- Wire feedback analysis into daily pipeline schedule (Windows Task Scheduler)
- Start career strategy expansion: multi-profile AI search, career-advisor skill, networking tracker
- Test full feedback analysis loop end-to-end with real data
