"""Tests for prompt caching structure in fit_scorer."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fit_scorer import BillingError, build_cached_system_prompt, score_job, score_jobs_batch


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


class TestScoreJobErrorHandling:
    """score_job handles API errors correctly: billing aborts, transient errors return None."""

    def _billing_error_client(self):
        """Client that raises the exact error the Anthropic API returns on low credits."""
        client = MagicMock()
        client.messages.create.side_effect = Exception(
            "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
            "'message': 'Your credit balance is too low to access the Anthropic API. "
            "Please go to Plans & Billing to upgrade or purchase credits.'}}"
        )
        return client

    def _transient_error_client(self):
        """Client that raises a generic transient error on every attempt."""
        client = MagicMock()
        client.messages.create.side_effect = Exception("Connection timeout")
        return client

    def test_billing_error_raises_billing_error(self):
        client = self._billing_error_client()
        cached_system = build_cached_system_prompt(SAMPLE_PROFILE)
        with patch("fit_scorer._load_target_profile", return_value=""):
            with pytest.raises(BillingError):
                score_job(SAMPLE_JOB, cached_system, client)

    def test_billing_error_does_not_retry(self):
        """A billing error should abort on the first attempt — not retry 3 times."""
        client = self._billing_error_client()
        cached_system = build_cached_system_prompt(SAMPLE_PROFILE)
        with patch("fit_scorer._load_target_profile", return_value=""):
            with pytest.raises(BillingError):
                score_job(SAMPLE_JOB, cached_system, client)
        assert client.messages.create.call_count == 1

    def test_transient_error_returns_none_after_retries(self):
        """A non-billing API error should retry 3 times then return None (not a fake score)."""
        client = self._transient_error_client()
        cached_system = build_cached_system_prompt(SAMPLE_PROFILE)
        with patch("fit_scorer._load_target_profile", return_value=""), \
             patch("fit_scorer.time.sleep"):
            result = score_job(SAMPLE_JOB, cached_system, client)
        assert result is None

    def test_transient_error_retries_three_times(self):
        client = self._transient_error_client()
        cached_system = build_cached_system_prompt(SAMPLE_PROFILE)
        with patch("fit_scorer._load_target_profile", return_value=""), \
             patch("fit_scorer.time.sleep"):
            score_job(SAMPLE_JOB, cached_system, client)
        assert client.messages.create.call_count == 3


class TestScoreJobsBatchErrorHandling:
    """score_jobs_batch aborts on BillingError; skips jobs that return None."""

    def _good_client(self, score: int = 7) -> MagicMock:
        import json as _json
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text=_json.dumps({"score": score, "rationale": "Good."}))]
        client.messages.create.return_value = response
        return client

    def _billing_error_client(self):
        client = MagicMock()
        client.messages.create.side_effect = Exception(
            "Your credit balance is too low to access the Anthropic API."
        )
        return client

    def test_billing_error_aborts_batch_early(self):
        """When billing fails on job 1, remaining jobs are not attempted."""
        jobs = [dict(SAMPLE_JOB) for _ in range(5)]
        client = self._billing_error_client()
        with patch("fit_scorer._load_target_profile", return_value=""), \
             patch("fit_scorer.build_cached_system_prompt", return_value="cached"):
            result = score_jobs_batch(jobs, SAMPLE_PROFILE, client)
        # No jobs scored — batch aborted immediately
        assert result == []
        # Only 1 API call was made (no retries on billing, no further jobs attempted)
        assert client.messages.create.call_count == 1

    def test_none_result_skipped_not_added_to_output(self):
        """Jobs that fail scoring (None) are excluded from results rather than given a fake score."""
        jobs = [dict(SAMPLE_JOB)]
        with patch("fit_scorer._load_target_profile", return_value=""), \
             patch("fit_scorer.build_cached_system_prompt", return_value="cached"), \
             patch("fit_scorer.score_job", return_value=None):
            result = score_jobs_batch(jobs, SAMPLE_PROFILE, self._good_client())
        assert result == []

    def test_successful_jobs_still_returned_when_others_fail(self):
        """If only some jobs fail with transient errors, the successful ones are still returned."""
        jobs = [dict(SAMPLE_JOB), dict(SAMPLE_JOB)]
        return_values = [{"score": 8, "rationale": "Good."}, None]
        with patch("fit_scorer._load_target_profile", return_value=""), \
             patch("fit_scorer.build_cached_system_prompt", return_value="cached"), \
             patch("fit_scorer.score_job", side_effect=return_values):
            result = score_jobs_batch(jobs, SAMPLE_PROFILE, self._good_client())
        assert len(result) == 1
        assert result[0]["fit_score"] == 8
