"""Integration test for the analyze_feedback pipeline."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestAnalyzeFeedbackPipeline:
    """End-to-end test for the analysis pipeline with mocked externals."""

    def test_dry_run_does_not_write_files(self, tmp_path, sample_tracker_rows, sample_status_rows):
        """Dry run prints proposed changes but writes nothing."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from analyze_feedback import run_analysis

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "job_titles:\n  - \"Director Digital Delivery\"\n\n"
            "required_keywords:\n  - \"delivery\"\n\n"
            "exclude_keywords:\n  - \"supply chain\"\n"
        )
        profile_path = tmp_path / "target_role_profile.md"
        state_path = tmp_path / "last_analysis.json"
        log_path = tmp_path / "config_changes.log"

        mock_sheets_client = MagicMock()
        mock_anthropic_client = MagicMock()

        profile_response = MagicMock()
        profile_response.content = [MagicMock(text="# Target Profile\nPrefers SaaS.")]
        config_response = MagicMock()
        config_response.content = [MagicMock(text='{"add_job_titles": ["AI Director"]}')]
        mock_anthropic_client.messages.create.side_effect = [profile_response, config_response]

        result = run_analysis(
            sheets_client=mock_sheets_client,
            anthropic_client=mock_anthropic_client,
            tracker_rows=sample_tracker_rows,
            status_rows=sample_status_rows,
            config_path=str(config_file),
            profile_path=str(profile_path),
            state_path=str(state_path),
            log_path=str(log_path),
            force=True,
            dry_run=True,
        )

        assert result["skipped"] is False
        assert not profile_path.exists()
        assert not state_path.exists()
        content = config_file.read_text()
        assert "AI Director" not in content

    def test_full_run_writes_all_outputs(self, tmp_path, sample_tracker_rows, sample_status_rows):
        """Full run writes profile, updates config, saves state."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from analyze_feedback import run_analysis

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "job_titles:\n  - \"Director Digital Delivery\"\n\n"
            "required_keywords:\n  - \"delivery\"\n\n"
            "exclude_keywords:\n  - \"supply chain\"\n"
        )
        profile_path = tmp_path / "target_role_profile.md"
        state_path = tmp_path / "last_analysis.json"
        log_path = tmp_path / "config_changes.log"

        mock_sheets_client = MagicMock()
        mock_anthropic_client = MagicMock()

        profile_response = MagicMock()
        profile_response.content = [MagicMock(text="# Target Profile\nPrefers SaaS.")]
        config_response = MagicMock()
        config_response.content = [MagicMock(text='{"add_job_titles": ["AI Director"], "reasoning": {"AI Director": "trend"}}')]
        mock_anthropic_client.messages.create.side_effect = [profile_response, config_response]

        result = run_analysis(
            sheets_client=mock_sheets_client,
            anthropic_client=mock_anthropic_client,
            tracker_rows=sample_tracker_rows,
            status_rows=sample_status_rows,
            config_path=str(config_file),
            profile_path=str(profile_path),
            state_path=str(state_path),
            log_path=str(log_path),
            force=True,
            dry_run=False,
        )

        assert result["skipped"] is False
        assert profile_path.exists()
        assert "SaaS" in profile_path.read_text()
        assert state_path.exists()
        config_content = config_file.read_text()
        assert "AI Director" in config_content

    def test_skips_when_not_enough_signals(self, tmp_path, sample_tracker_rows, sample_status_rows):
        """Skips analysis when below signal threshold."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from analyze_feedback import run_analysis

        config_file = tmp_path / "config.yaml"
        config_file.write_text("job_titles:\n  - \"Director\"\n\nrequired_keywords:\n  - \"delivery\"\n\nexclude_keywords:\n  - \"supply chain\"\n")
        state_path = tmp_path / "last_analysis.json"
        state_path.write_text(json.dumps({
            "last_run": "2026-03-28T06:00:00",
            "tracker_feedback_count": 3,
            "status_row_count": 2,
        }))

        mock_sheets_client = MagicMock()
        mock_anthropic_client = MagicMock()

        result = run_analysis(
            sheets_client=mock_sheets_client,
            anthropic_client=mock_anthropic_client,
            tracker_rows=sample_tracker_rows,
            status_rows=sample_status_rows,
            config_path=str(config_file),
            profile_path=str(tmp_path / "target_role_profile.md"),
            state_path=str(state_path),
            log_path=str(tmp_path / "config_changes.log"),
            force=False,
            dry_run=False,
        )

        assert result["skipped"] is True
        mock_anthropic_client.messages.create.assert_not_called()
