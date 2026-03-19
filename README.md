# Job Search Automation Tool

Runs daily at 5am, scrapes new job listings, scores them with Claude AI, updates a Google Sheet tracker, and emails you a morning digest.

**Two searches per day:**
- **National Remote** — US-wide remote-only roles
- **Local QC** — Quad Cities, IA area (in-person/hybrid)

---

## One-Time Setup

### 1. Install Python 3.11+
Download from [python.org](https://python.org). During install, check **"Add Python to PATH"**.

### 2. Install dependencies
```
cd "C:\Users\steerave\Desktop\Claude Projects\Job Search Tool"
pip install -r requirements.txt
```

### 3. Get an Anthropic API Key
Go to [console.anthropic.com](https://console.anthropic.com) → API Keys → Create key.

> **Note:** This is separate from Claude.ai (the chat website). You need a pay-as-you-go API key.
> Cost: ~$0.05–$0.15 per job (resume + cover letter generation).

### 4. Set up Google Sheets API
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Enable: **Google Sheets API** + **Google Drive API**
4. Go to **IAM & Admin → Service Accounts** → Create Service Account
5. Click the service account → **Keys → Add Key → JSON** → Download
6. Save the downloaded JSON file somewhere safe (e.g., next to this project)
7. Create a new Google Sheet (or use an existing one)
8. **Share the sheet** with the service account email (looks like `name@project.iam.gserviceaccount.com`) — give it Editor access
9. Copy the Sheet ID from the URL: `docs.google.com/spreadsheets/d/SHEET_ID/edit`

### 5. Get your LinkedIn data export
1. LinkedIn → **Settings & Privacy → Data Privacy → Get a copy of your data**
2. Select **"Fast file"** — check: Profile, Positions, Skills, Education
3. Wait for the email (usually a few minutes to a few hours)
4. Download and extract the ZIP
5. Copy the CSV files into `profile/linkedin_export/`

### 6. Add your resume
Place your resume at:
- `profile/resume.pdf` ← preferred
- `profile/resume.docx` ← also works

### 7. Configure `.env`
Copy `.env.template` to `.env` and fill in your values:
```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_SHEETS_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
GOOGLE_SERVICE_ACCOUNT_JSON=C:\path\to\your\service_account.json
EMAIL_SENDER=your@gmail.com
EMAIL_PASSWORD=your_app_password_here
EMAIL_RECIPIENT=your@email.com
```

> **Gmail App Password:** Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
> You need 2-Step Verification enabled. Create an App Password for "Mail".

### 8. Customize `config.yaml`
Edit `config.yaml` to set your target job titles, required/excluded keywords, and score thresholds.

### 9. Run setup
```
python setup.py
```
This will:
- Parse your resume + LinkedIn data → `profile/parsed_profile.json`
- Initialize the Google Sheet with headers and formatting
- Validate your `.env` config

**Review `profile/parsed_profile.json`** — make sure your experience bullets are accurate. You can edit it manually if needed.

### 10. Test run
```
python main.py --dry-run
```
This scrapes and scores jobs without writing anything. Verify the output looks right.

### 11. Schedule with Windows Task Scheduler
1. Open **Task Scheduler** (search in Start Menu)
2. Click **Create Basic Task...**
3. Name: `Job Search Tool`
4. Trigger: **Daily**, start time: **5:00 AM**
5. Action: **Start a program**
   - Program: `python`
   - Arguments: `"C:\path\to\job-search-tool\main.py"`
   - Start in: `C:\path\to\job-search-tool`
6. Finish. Right-click the task → **Run** to test immediately.

> **Tip:** To verify it ran, check Windows Event Viewer (Applications and Services Logs → Task Scheduler) or look at `logs/YYYY-MM-DD.log`.

---

## Daily Usage

After setup, the tool runs automatically at 5am. Your workflow:

1. **Check email** — morning digest with top matches + fit scores
2. **Open Google Sheet** — filter/sort by score, search type, status
3. **Submit applications** — update the Status column as you go

### Status Dropdown
The "Status" column in the sheet is for your manual tracking — the tool never overwrites it:
- `New` — just found, not yet reviewed
- `Applied` — application submitted
- `Interviewing` — in the process
- `Rejected` — no longer active
- `Offer` — you got an offer!

---

## Manual Run
```bash
# Full run
python main.py

# Preview only (no writes, no email)
python main.py --dry-run

# Custom config/env paths
python main.py --config path/to/config.yaml --env path/to/.env
```

---

## Project Structure
```
Job Search Tool/
├── .env                          # API keys (never commit)
├── config.yaml                   # Search preferences
├── requirements.txt
├── main.py                       # Entry point
├── setup.py                      # One-time setup
├── src/
│   ├── job_scraper.py            # JobSpy scraping
│   ├── deduplicator.py           # Seen job tracking
│   ├── fit_scorer.py             # Claude: job fit scoring
│   ├── resume_tailor.py          # Claude: resume tailoring
│   ├── cover_letter_writer.py    # Claude: cover letter generation
│   ├── document_builder.py       # .docx file creation
│   ├── sheets_updater.py         # Google Sheets integration
│   ├── email_notifier.py         # Email digest
│   └── profile_parser.py         # Resume + LinkedIn parsing
├── profile/
│   ├── resume.pdf                # Your resume (you provide)
│   ├── linkedin_export/          # LinkedIn CSV export (you provide)
│   └── parsed_profile.json       # Auto-generated by setup.py
├── templates/
│   ├── resume_template.docx      # Auto-generated by setup.py
│   └── cover_letter_template.docx
├── output/YYYY/MM/               # Generated documents
├── data/seen_jobs.json           # Deduplication store
└── logs/YYYY-MM-DD.log           # Daily logs
```

---

## Google Sheets Columns
| Column | Description |
|---|---|
| Date Found | When the job was scraped |
| Search Type | National Remote or Local QC |
| Role Name | Job title |
| Company Name | Employer |
| Employment Type | Full-time, Contract, etc. |
| Remote | Yes / Hybrid / No |
| Compensation | Salary range if available |
| Location | Job location |
| Fit Score | 1–10 (AI scored) — color coded |
| Fit Notes | AI rationale for the score |
| Job Description | First 500 chars |
| Direct Link | Link to apply |
| Resume File | Path to tailored resume .docx |
| Cover Letter File | Path to cover letter .docx |
| Status | Your manual tracking (New / Applied / Interviewing / Rejected / Offer) |
| Notes | Free-form notes — e.g. "too junior", "wrong industry", "no salary listed" |
| My Score | Your 1–5 rating (dropdown) — feeds the feedback analyzer |

Both the **Jobs** tab and **Below Threshold** tab have the My Score column. Scoring below-threshold jobs is especially useful — it helps identify good fits the AI missed.

---

## Costs
- **Job scraping:** Free
- **Google Sheets:** Free
- **Claude API:** ~$0.05–$0.15 per job with document generation
  - At 10 docs/day × $0.10 avg = ~$1/day = ~$30/month
  - Reduce `max_docs_per_day` in config.yaml to control costs
  - Set `doc_generation_score` higher (e.g., 8) to only generate docs for top matches

---

## Troubleshooting

**No jobs found:**
- JobSpy can be blocked by job boards periodically. Try again in a few hours.
- Check `logs/YYYY-MM-DD.log` for specific error messages.

**Google Sheets auth error:**
- Make sure the sheet is shared with your service account email
- Verify both Google Sheets API and Google Drive API are enabled

**Email not sending:**
- Gmail: Use an App Password, not your regular password
- Check that 2-Step Verification is enabled on your Gmail account

**Claude API error:**
- Verify `ANTHROPIC_API_KEY` is correct
- Check your API usage at [console.anthropic.com](https://console.anthropic.com)

**Profile parsing issues:**
- Manually edit `profile/parsed_profile.json` to fix any incorrect data
- The AI uses this JSON directly, so accuracy matters
