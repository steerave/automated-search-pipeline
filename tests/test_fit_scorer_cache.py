"""Tests for prompt caching structure in fit_scorer."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fit_scorer import build_cached_system_prompt, score_job


SAMPLE_PROFILE = {
    "name": "Joe Test",
    "headline": "Director of Digital Delivery",
    "summary": "10 years leading delivery organizations.",
    "skills": ["Agile", "SDLC", "Stakeholder Management"],
    "experience": [
        {
            "title": "Director, Digital Delivery",
            "company": "Acme Corp",
            "started_on": "2020-01",
            "finished_on": "Present",
            "bullets": ["Led 50-person delivery org", "Reduced cycle time 30%"],
        }
    ],
    "education": [
        {"degree": "BS", "field": "Computer Science", "school": "State U", "end_date": "2005"}
    ],
}

SAMPLE_JOB = {
    "title": "Director Digital Delivery",
    "company": "SaaS Co",
    "location": "Remote",
    "job_type": "fulltime",
    "salary_min": 180000,
    "salary_max": 220000,
    "salary_currency": "USD",
    "salary_interval": "",
    "description": "Lead digital delivery for our SaaS platform. Agile, SDLC, stakeholder mgmt required.",
}


class TestBuildCachedSystemPrompt:
    """build_cached_system_prompt returns a string containing all profile fields."""

    def test_contains_candidate_name(self):
        result = build_cached_system_prompt(SAMPLE_PROFILE)
        assert "Joe Test" in result

    def test_contains_headline(self):
        result = build_cached_system_prompt(SAMPLE_PROFILE)
        assert "Director of Digital Delivery" in result

    def test_contains_skills(self):
        result = build_cached_system_prompt(SAMPLE_PROFILE)
        assert "Agile" in result

    def test_contains_experience(self):
        result = build_cached_system_prompt(SAMPLE_PROFILE)
        assert "Acme Corp" in result

    def test_contains_scoring_instructions(self):
        result = build_cached_system_prompt(SAMPLE_PROFILE)
        assert "1-10" in result

    def test_contains_json_response_format(self):
        result = build_cached_system_prompt(SAMPLE_PROFILE)
        assert '"score"' in result
        assert '"rationale"' in result


class TestScoreJobUsesCachedSystem:
    """score_job passes system as a list with cache_control, not as a plain string."""

    def _make_client(self, score: int = 7) -> MagicMock:
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text=json.dumps({"score": score, "rationale": "Good match."}))]
        client.messages.create.return_value = response
        return client

    def test_system_is_list(self):
        client = self._make_client()
        cached_system = build_cached_system_prompt(SAMPLE_PROFILE)
        with patch("fit_scorer._load_target_profile", return_value=""):
            score_job(SAMPLE_JOB, cached_system, client)
        call_kwargs = client.messages.create.call_args.kwargs
        assert isinstance(call_kwargs["system"], list)

    def test_system_has_cache_control(self):
        client = self._make_client()
        cached_system = build_cached_system_prompt(SAMPLE_PROFILE)
        with patch("fit_scorer._load_target_profile", return_value=""):
            score_job(SAMPLE_JOB, cached_system, client)
        call_kwargs = client.messages.create.call_args.kwargs
        system_block = call_kwargs["system"][0]
        assert system_block.get("cache_control") == {"type": "ephemeral"}

    def test_system_block_contains_profile_text(self):
        client = self._make_client()
        cached_system = build_cached_system_prompt(SAMPLE_PROFILE)
        with patch("fit_scorer._load_target_profile", return_value=""):
            score_job(SAMPLE_JOB, cached_system, client)
        call_kwargs = client.messages.create.call_args.kwargs
        system_text = call_kwargs["system"][0]["text"]
        assert "Joe Test" in system_text

    def test_user_message_contains_job_description(self):
        client = self._make_client()
        cached_system = build_cached_system_prompt(SAMPLE_PROFILE)
        with patch("fit_scorer._load_target_profile", return_value=""):
            score_job(SAMPLE_JOB, cached_system, client)
        call_kwargs = client.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        assert "SaaS Co" in user_content
        assert "Director Digital Delivery" in user_content

    def test_returns_score_and_rationale(self):
        client = self._make_client(score=8)
        cached_system = build_cached_system_prompt(SAMPLE_PROFILE)
        with patch("fit_scorer._load_target_profile", return_value=""):
            result = score_job(SAMPLE_JOB, cached_system, client)
        assert result["score"] == 8
        assert result["rationale"] == "Good match."
