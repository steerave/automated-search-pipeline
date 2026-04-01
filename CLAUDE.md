# Job Search Automation Tool — Project Standards

## Stack

- **Language:** Python 3.11+
- **Config:** `python-dotenv` + `PyYAML` + `ruamel.yaml`
- **APIs:** Anthropic (Claude), Google Sheets (gspread), JobSpy
- **Platform:** Windows 11, scheduled via Windows Task Scheduler

## Project Structure

```
main.py                  # Daily job search pipeline entry point
analyze_feedback.py      # Daily feedback analysis entry point (6am)
setup.py                 # One-time profile setup
config.yaml              # Search config (titles, keywords, thresholds)
src/                     # All modules
profile/                 # Resume, LinkedIn export, parsed profile, target role profile
data/                    # Runtime state (seen_jobs.json, last_analysis.json)
output/                  # Generated resumes and cover letters
logs/                    # Daily logs + config change audit trail
docs/superpowers/specs/  # Design specs and architecture decisions
```

## Development Workflow

1. **Brainstorm** before building (`superpowers:brainstorming`)
2. **Write a plan** before coding (`superpowers:writing-plans`)
3. **TDD** — write tests first (`superpowers:test-driven-development`)
4. **Code review** before merging (`superpowers:requesting-code-review`)

## Testing

- Unit tests go in `tests/` mirroring `src/` structure
- Mock external services (Google Sheets, Anthropic API) in unit tests
- Use `--dry-run` flags for integration testing against real services
- Run `python -m pytest tests/` before committing

## Git Practices

- Commit directly to `main` (solo project)
- Commit and push after every meaningful working change
- Never commit broken code
- Pre-commit checklist: README + CHANGELOG + push (see global CLAUDE.md)

## Key References

- **Design specs:** `docs/superpowers/specs/` — architecture decisions and feature designs
- **Search config:** `config.yaml` — job titles, keywords, thresholds
- **Environment:** `.env.template` — all required env vars documented there
