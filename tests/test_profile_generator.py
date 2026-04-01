"""Tests for profile_generator — prompt building and profile output."""

from unittest.mock import MagicMock
from feedback_reader import parse_tracker_feedback, parse_status_rows
from profile_generator import (
    format_tracker_for_prompt,
    format_status_for_prompt,
    build_profile_prompt,
    generate_target_profile,
)


class TestFormatTrackerForPrompt:
    """format_tracker_for_prompt creates readable text from tracker data."""

    def test_includes_role_and_scores(self, sample_tracker_rows):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        text = format_tracker_for_prompt(tracker)
        assert "Director Digital Delivery" in text
        assert "Acme SaaS Corp" in text
        assert "My Score: 5" in text

    def test_includes_notes(self, sample_tracker_rows):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        text = format_tracker_for_prompt(tracker)
        assert "Great culture, AI-forward company" in text

    def test_empty_list_returns_none_message(self):
        text = format_tracker_for_prompt([])
        assert "No feedback" in text


class TestFormatStatusForPrompt:
    """format_status_for_prompt creates readable text from status data."""

    def test_includes_applied_roles(self, sample_status_rows):
        status = parse_status_rows(sample_status_rows)
        text = format_status_for_prompt(status)
        assert "Acme SaaS Corp" in text
        assert "Director Digital Delivery" in text

    def test_includes_industry(self, sample_status_rows):
        status = parse_status_rows(sample_status_rows)
        text = format_status_for_prompt(status)
        assert "SaaS / Technology" in text

    def test_empty_list_returns_none_message(self):
        text = format_status_for_prompt([])
        assert "No application" in text


class TestBuildProfilePrompt:
    """build_profile_prompt assembles the full prompt for Claude."""

    def test_includes_all_sections(self, sample_tracker_rows, sample_status_rows):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        status = parse_status_rows(sample_status_rows)
        prompt = build_profile_prompt(tracker, status, current_profile="")
        assert "JOB TRACKER FEEDBACK" in prompt
        assert "APPLICATION HISTORY" in prompt
        assert "target role profile" in prompt.lower()

    def test_includes_current_profile_when_provided(self, sample_tracker_rows, sample_status_rows):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        status = parse_status_rows(sample_status_rows)
        prompt = build_profile_prompt(tracker, status, current_profile="# My current profile")
        assert "CURRENT TARGET PROFILE" in prompt
        assert "# My current profile" in prompt


class TestGenerateTargetProfile:
    """generate_target_profile calls Claude and returns markdown."""

    def test_returns_claude_response(self, sample_tracker_rows, sample_status_rows):
        tracker = parse_tracker_feedback(sample_tracker_rows)
        status = parse_status_rows(sample_status_rows)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="# Target Role Profile\n\nPrefers SaaS delivery roles.")]
        mock_client.messages.create.return_value = mock_response

        result = generate_target_profile(tracker, status, "", mock_client)
        assert "Target Role Profile" in result
        assert "SaaS" in result
        mock_client.messages.create.assert_called_once()
