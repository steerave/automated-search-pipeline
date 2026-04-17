"""Tests for src/api_cost_logger.py — cost calculation and log line format."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api_cost_logger import calculate_cost, log_api_cost, PRICING


def _make_usage(input_tokens=0, output_tokens=0, cache_creation=0, cache_read=0):
    """Build a mock usage object matching the Anthropic SDK structure."""
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_creation_input_tokens = cache_creation
    usage.cache_read_input_tokens = cache_read
    return usage


MODEL = "claude-sonnet-4-6"


class TestCalculateCost:
    """calculate_cost returns correct USD amount for each token type."""

    def test_zero_tokens_costs_nothing(self):
        usage = _make_usage()
        assert calculate_cost(MODEL, usage) == 0.0

    def test_input_tokens_only(self):
        usage = _make_usage(input_tokens=1_000_000)
        assert abs(calculate_cost(MODEL, usage) - 3.00) < 0.0001

    def test_output_tokens_only(self):
        usage = _make_usage(output_tokens=1_000_000)
        assert abs(calculate_cost(MODEL, usage) - 15.00) < 0.0001

    def test_cache_read_tokens_only(self):
        usage = _make_usage(cache_read=1_000_000)
        assert abs(calculate_cost(MODEL, usage) - 0.30) < 0.0001

    def test_cache_write_tokens_only(self):
        usage = _make_usage(cache_creation=1_000_000)
        assert abs(calculate_cost(MODEL, usage) - 3.75) < 0.0001

    def test_typical_scored_job_with_caching(self):
        # First job: cache write (1200 tokens) + job input (500) + output (150)
        usage = _make_usage(input_tokens=500, output_tokens=150, cache_creation=1200)
        cost = calculate_cost(MODEL, usage)
        expected = (500 * 3.00 + 1200 * 3.75 + 150 * 15.00) / 1_000_000
        assert abs(cost - expected) < 0.000001

    def test_typical_scored_job_cache_hit(self):
        # Subsequent jobs: cache read (1200 tokens) + job input (500) + output (150)
        usage = _make_usage(input_tokens=500, output_tokens=150, cache_read=1200)
        cost = calculate_cost(MODEL, usage)
        expected = (500 * 3.00 + 1200 * 0.30 + 150 * 15.00) / 1_000_000
        assert abs(cost - expected) < 0.000001

    def test_unknown_model_returns_zero(self):
        usage = _make_usage(input_tokens=1000, output_tokens=100)
        assert calculate_cost("claude-unknown-model", usage) == 0.0

    def test_returns_float(self):
        usage = _make_usage(input_tokens=100, output_tokens=50)
        assert isinstance(calculate_cost(MODEL, usage), float)

    def test_pricing_dict_has_sonnet(self):
        assert MODEL in PRICING
        assert "input" in PRICING[MODEL]
        assert "cache_write" in PRICING[MODEL]
        assert "cache_read" in PRICING[MODEL]
        assert "output" in PRICING[MODEL]


class TestLogApiCost:
    """log_api_cost writes a correctly formatted line to logs/api_costs.log."""

    def _call_log(self, tmp_path):
        """Call log_api_cost with a predictable usage and a temp log directory."""
        usage = _make_usage(input_tokens=1523, output_tokens=142, cache_read=1201)
        log_file = tmp_path / "api_costs.log"
        with patch("api_cost_logger._log_path", return_value=log_file):
            log_api_cost("fit_scorer", MODEL, usage)
        return log_file

    def test_log_file_created(self, tmp_path):
        log_file = self._call_log(tmp_path)
        assert log_file.exists()

    def test_log_line_contains_caller(self, tmp_path):
        log_file = self._call_log(tmp_path)
        assert "fit_scorer" in log_file.read_text()

    def test_log_line_contains_model(self, tmp_path):
        log_file = self._call_log(tmp_path)
        assert MODEL in log_file.read_text()

    def test_log_line_contains_input_token_count(self, tmp_path):
        log_file = self._call_log(tmp_path)
        assert "in=1523" in log_file.read_text()

    def test_log_line_contains_cache_read_count(self, tmp_path):
        log_file = self._call_log(tmp_path)
        assert "cr=1201" in log_file.read_text()

    def test_log_line_contains_output_token_count(self, tmp_path):
        log_file = self._call_log(tmp_path)
        assert "out=142" in log_file.read_text()

    def test_log_line_contains_dollar_amount(self, tmp_path):
        # in=1523, cr=1201, out=142 on claude-sonnet-4-6:
        # (1523*3.00 + 1201*0.30 + 142*15.00) / 1_000_000 = $0.00706
        log_file = self._call_log(tmp_path)
        assert "$0.00706" in log_file.read_text()

    def test_log_line_contains_datetime(self, tmp_path):
        import re
        log_file = self._call_log(tmp_path)
        content = log_file.read_text()
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", content), \
            "Log line should contain ISO datetime like 2026-04-17T05:29:58"

    def test_multiple_calls_append_multiple_lines(self, tmp_path):
        usage = _make_usage(input_tokens=100, output_tokens=50)
        log_file = tmp_path / "api_costs.log"
        with patch("api_cost_logger._log_path", return_value=log_file):
            log_api_cost("fit_scorer", MODEL, usage)
            log_api_cost("fit_scorer", MODEL, usage)
        lines = [l for l in log_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 2

    def test_log_does_not_raise_on_unknown_model(self, tmp_path):
        usage = _make_usage(input_tokens=100, output_tokens=50)
        log_file = tmp_path / "api_costs.log"
        with patch("api_cost_logger._log_path", return_value=log_file):
            log_api_cost("fit_scorer", "claude-unknown-99", usage)  # should not raise

    def test_log_does_not_raise_if_usage_is_none(self, tmp_path):
        log_file = tmp_path / "api_costs.log"
        with patch("api_cost_logger._log_path", return_value=log_file):
            log_api_cost("fit_scorer", MODEL, None)  # should not raise
