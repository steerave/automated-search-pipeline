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
    # Force UTF-8 on console to handle emojis from Claude responses on Windows
    stream_handler = logging.StreamHandler(sys.stdout)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    handlers = [
        stream_handler,
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
    tracker_rows: list,
    status_rows: list,
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
