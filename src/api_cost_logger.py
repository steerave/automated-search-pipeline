"""
api_cost_logger.py

Appends one line to logs/api_costs.log after every Anthropic API call.
No external dependencies — reads response.usage which the SDK always returns.

Log format (pipe-separated):
  2026-04-17T05:29:58 | fit_scorer        | claude-sonnet-4-6 | in=1523 cw=0    cr=1201 out=142 | $0.00234
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Pricing per token (USD) — add new models here as needed
PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input":       3.00 / 1_000_000,
        "cache_write": 3.75 / 1_000_000,
        "cache_read":  0.30 / 1_000_000,
        "output":     15.00 / 1_000_000,
    },
    "claude-opus-4-6": {
        "input":       15.00 / 1_000_000,
        "cache_write": 18.75 / 1_000_000,
        "cache_read":   1.50 / 1_000_000,
        "output":      75.00 / 1_000_000,
    },
    "claude-haiku-4-5-20251001": {
        "input":        0.80 / 1_000_000,
        "cache_write":  1.00 / 1_000_000,
        "cache_read":   0.08 / 1_000_000,
        "output":       4.00 / 1_000_000,
    },
}


def _log_path() -> Path:
    """Return path to logs/api_costs.log, relative to project root."""
    return Path(__file__).parent.parent / "logs" / "api_costs.log"


def calculate_cost(model: str, usage) -> float:
    """
    Calculate USD cost from a response.usage object.
    Returns 0.0 if model is not in PRICING or usage is None.
    """
    if usage is None:
        return 0.0
    pricing = PRICING.get(model)
    if pricing is None:
        return 0.0

    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0

    return (
        input_tokens  * pricing["input"]
        + cache_write * pricing["cache_write"]
        + cache_read  * pricing["cache_read"]
        + output_tokens * pricing["output"]
    )


def log_api_cost(caller: str, model: str, usage) -> None:
    """
    Append one cost line to logs/api_costs.log.

    Args:
        caller: short name identifying which module made the call
                (e.g. "fit_scorer", "config_updater", "profile_generator")
        model:  model ID string (e.g. "claude-sonnet-4-6")
        usage:  response.usage object from the Anthropic SDK, or None
    """
    try:
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cost = calculate_cost(model, usage)

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        line = (
            f"{ts} | {caller:<18} | {model} | "
            f"in={input_tokens:<6} cw={cache_write:<6} cr={cache_read:<6} out={output_tokens:<6} | "
            f"${cost:.5f}\n"
        )

        log_file = _log_path()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line)

    except Exception as e:
        # Never let cost logging crash the pipeline
        logger.warning(f"api_cost_logger: failed to write cost log: {e}")
