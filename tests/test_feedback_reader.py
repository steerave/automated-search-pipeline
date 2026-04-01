"""Tests for feedback_reader — sheet reading and signal counting."""

from unittest.mock import MagicMock
from feedback_reader import (
    parse_tracker_feedback,
    parse_status_rows,
    count_signals,
    has_enough_signals,
)


class TestParseTrackerFeedback:
    """parse_tracker_feedback filters to rows with user feedback only."""

    def test_returns_only_rows_with_my_score(self, sample_tracker_rows):
        result = parse_tracker_feedback(sample_tracker_rows)
        titles = [r["role_name"] for r in result]
        assert "Director Digital Delivery" in titles
        assert "Director of Ecommerce" in titles
        assert "Senior TPM" in titles
        assert "VP Technology Delivery" not in titles

    def test_returns_rows_with_notes_even_without_my_score(self, sample_tracker_rows):
        sample_tracker_rows[3]["Notes"] = "Interesting but too senior"
        sample_tracker_rows[3]["My Score"] = ""
        result = parse_tracker_feedback(sample_tracker_rows)
        titles = [r["role_name"] for r in result]
        assert "VP Technology Delivery" in titles

    def test_returns_empty_for_no_feedback(self):
        rows = [
            {
                "Role Name": "Some Role",
                "Company Name": "SomeCo",
                "My Score": "",
                "Notes": "",
                "Fit Score": 7,
                "Fit Notes": "Good match",
                "Date Found": "2026-03-15",
                "Search Type": "National Remote",
                "Employment Type": "Full-time",
                "Remote": "Yes",
                "Compensation": "",
                "Location": "Remote",
                "Job Description": "...",
                "Direct Link": "",
                "Resume File": "",
                "Cover Letter File": "",
                "Status": "New",
            }
        ]
        result = parse_tracker_feedback(rows)
        assert result == []

    def test_extracts_numeric_my_score(self, sample_tracker_rows):
        result = parse_tracker_feedback(sample_tracker_rows)
        scores = {r["role_name"]: r["my_score"] for r in result}
        assert scores["Director Digital Delivery"] == 5
        assert scores["Director of Ecommerce"] == 1
        assert scores["Senior TPM"] == 4

    def test_output_dict_keys(self, sample_tracker_rows):
        result = parse_tracker_feedback(sample_tracker_rows)
        expected_keys = {
            "role_name", "company", "fit_score", "fit_notes", "my_score",
            "notes", "status", "date_found", "remote", "location",
            "compensation", "search_type",
        }
        assert set(result[0].keys()) == expected_keys


class TestParseStatusRows:
    """parse_status_rows converts raw sheet rows to structured dicts."""

    def test_returns_all_rows(self, sample_status_rows):
        result = parse_status_rows(sample_status_rows)
        assert len(result) == 2

    def test_output_dict_keys(self, sample_status_rows):
        result = parse_status_rows(sample_status_rows)
        expected_keys = {
            "role_title", "company", "industry", "compensation_range",
            "remote_only", "job_link", "applied", "application_link",
            "notes", "status",
        }
        assert set(result[0].keys()) == expected_keys

    def test_handles_empty_list(self):
        result = parse_status_rows([])
        assert result == []


class TestCountSignals:
    """count_signals computes delta from last analysis state."""

    def test_counts_new_signals(self, sample_tracker_rows, sample_status_rows, sample_last_analysis):
        tracker_feedback = parse_tracker_feedback(sample_tracker_rows)
        status_data = parse_status_rows(sample_status_rows)
        delta = count_signals(tracker_feedback, status_data, sample_last_analysis)
        assert delta == 4

    def test_first_run_counts_all(self, sample_tracker_rows, sample_status_rows):
        tracker_feedback = parse_tracker_feedback(sample_tracker_rows)
        status_data = parse_status_rows(sample_status_rows)
        delta = count_signals(tracker_feedback, status_data, None)
        assert delta == 5

    def test_no_new_signals(self, sample_tracker_rows, sample_status_rows):
        tracker_feedback = parse_tracker_feedback(sample_tracker_rows)
        status_data = parse_status_rows(sample_status_rows)
        last = {"last_run": "2026-03-28T06:00:00", "tracker_feedback_count": 3, "status_row_count": 2}
        delta = count_signals(tracker_feedback, status_data, last)
        assert delta == 0


class TestHasEnoughSignals:
    """has_enough_signals applies the threshold."""

    def test_below_threshold(self):
        assert has_enough_signals(4, threshold=5) is False

    def test_at_threshold(self):
        assert has_enough_signals(5, threshold=5) is True

    def test_above_threshold(self):
        assert has_enough_signals(10, threshold=5) is True
