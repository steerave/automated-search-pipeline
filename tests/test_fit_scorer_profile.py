"""Tests for fit_scorer target profile integration."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fit_scorer import _load_target_profile, FIT_SCORE_PROMPT


class TestLoadTargetProfile:
    """_load_target_profile reads the profile file if it exists."""

    def test_returns_content_when_file_exists(self, tmp_path):
        profile = tmp_path / "target_role_profile.md"
        profile.write_text("# Target Profile\nPrefers SaaS delivery roles.")
        with patch("fit_scorer.Path") as mock_path_cls:
            # Path(__file__) -> .parent -> .parent -> / "profile" -> / "target_role_profile.md"
            mock_instance = MagicMock()
            mock_path_cls.return_value = mock_instance
            mock_profile_path = MagicMock()
            mock_instance.parent.parent.__truediv__.return_value.__truediv__.return_value = mock_profile_path
            mock_profile_path.exists.return_value = True
            mock_profile_path.read_text.return_value = "# Target Profile\nPrefers SaaS delivery roles."
            result = _load_target_profile()
        assert "SaaS delivery" in result

    def test_returns_empty_when_file_missing(self):
        with patch("fit_scorer.Path") as mock_path_cls:
            mock_instance = MagicMock()
            mock_path_cls.return_value = mock_instance
            mock_profile_path = MagicMock()
            mock_instance.parent.parent.__truediv__.return_value.__truediv__.return_value = mock_profile_path
            mock_profile_path.exists.return_value = False
            result = _load_target_profile()
        assert result == ""


class TestFitScorePromptIncludesProfile:
    """FIT_SCORE_PROMPT must include target_role_profile placeholder."""

    def test_prompt_has_profile_placeholder(self):
        assert "{target_role_profile}" in FIT_SCORE_PROMPT
