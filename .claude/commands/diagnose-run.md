Diagnose a job search pipeline run for Sarun's Job Search Tool.

## Project context
- Logs: `C:\Users\steerave\Desktop\Claude Projects\Job Search Tool\logs\YYYY-MM-DD.log`
- Summary script: `scripts/log_summary.py` (accepts optional date arg, exits 1 if log missing)
- Config: `config.yaml` (job titles, filters, thresholds)
- Config change log: `logs/config_changes.log`

## Step 1 — Get the date
If the user specified a date (e.g. "diagnose yesterday" or "diagnose 2026-04-15"), parse it.
Otherwise default to today's date in YYYY-MM-DD format.

## Step 2 — Run the summary script
```bash
cd "C:\Users\steerave\Desktop\Claude Projects\Job Search Tool" && python scripts/log_summary.py <date>
```
Show the output verbatim. Then evaluate against these thresholds:

| Metric | Flag if |
|---|---|
| Local QC raw count | > 100 (location filter may have a gap) |
| Scored | = 0 (something failed upstream) |
| Cap hit | True (title list likely needs pruning) |
| Errors | > 0 (always investigate) |
| Added to sheet | > 30 (possible filter regression) |
| Est. cost | > $1.00 (check if cap is working) |

## Step 3 — Deep diagnosis (when anomalies found or user asks "why")
Read the actual log file. Extract:

**Local QC over-scraping** — find all lines matching `[Local QC] Scraping:` and their result counts (the line immediately after each). Which titles produced > 20 results? Those are candidates for removal.

**Domain filter catches** — find all lines matching `Pre-filter: off-domain title skipped`. List the distinct skipped titles. If a title appears across multiple runs, it should be removed from `job_titles` in config.yaml.

**Watchlist hits** — find lines matching `new remote jobs` where the count > 0. List companies and counts.

**Scrape failures** — find lines matching `JobSpy scrape failed`. Note which titles and boards. Persistent failures on the same title suggest removing it from `job_titles`.

## Step 4 — Check recent config changes
Read the last 30 lines of `logs/config_changes.log`. If the feedback analyzer added titles or keywords recently, flag them in context of any anomalies.

## Step 5 — Deliver findings
Format the response as:

**Quick Summary** — the script output verbatim

**Health Status** — one of: HEALTHY / WARNING / CRITICAL, with a one-line reason

**Anomalies** (if any) — bullet list, each with: metric → observed value → threshold → likely cause

**Root cause** — 2–3 sentences on what drove the anomaly

**Recommendations** — specific and actionable. Examples:
- "Remove 'Contractor Digital Delivery' from job_titles — it returned 80 results with 0 passing the domain filter"
- "Add 'Boston' to local_qc.location_include exclusions — Boston jobs are passing the location filter"
- "Raise max_jobs_to_score to 175 — cap is consistently hit but most capped jobs are relevant"

Keep the tone direct and diagnostic, not reassuring. Surface problems clearly.
