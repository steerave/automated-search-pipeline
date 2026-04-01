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
