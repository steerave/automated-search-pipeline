"""Tests for pipeline-level job filtering helpers in main.py."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import _filter_scoreable_jobs


class TestFilterScoreableJobs:
    """_filter_scoreable_jobs splits jobs into scoreable vs. skipped by title domain words."""

    def _job(self, title: str) -> dict:
        return {"title": title, "company": "Co", "search_type": "national_remote"}

    def _config(self, words: list[str]) -> dict:
        return {"title_domain_words": words}

    def test_passes_delivery_title(self):
        jobs = [self._job("Director of Delivery")]
        scoreable, skipped = _filter_scoreable_jobs(jobs, self._config(["delivery"]))
        assert len(scoreable) == 1
        assert len(skipped) == 0

    def test_blocks_art_director(self):
        jobs = [self._job("Senior Art Director")]
        scoreable, skipped = _filter_scoreable_jobs(
            jobs, self._config(["delivery", "digital", "program", "technical", "operations"])
        )
        assert len(scoreable) == 0
        assert len(skipped) == 1

    def test_blocks_software_engineer(self):
        jobs = [self._job("Senior iOS Software Engineer")]
        scoreable, skipped = _filter_scoreable_jobs(
            jobs, self._config(["delivery", "digital", "program"])
        )
        assert len(scoreable) == 0
        assert len(skipped) == 1

    def test_passes_marketing_operations(self):
        jobs = [self._job("Marketing Operations Manager")]
        scoreable, skipped = _filter_scoreable_jobs(
            jobs, self._config(["operations", "marketing", "delivery"])
        )
        assert len(scoreable) == 1
        assert len(skipped) == 0

    def test_empty_domain_words_passes_all(self):
        jobs = [self._job("Anything At All")]
        scoreable, skipped = _filter_scoreable_jobs(jobs, self._config([]))
        assert len(scoreable) == 1
        assert len(skipped) == 0

    def test_case_insensitive(self):
        jobs = [self._job("DIRECTOR OF DIGITAL DELIVERY")]
        scoreable, skipped = _filter_scoreable_jobs(
            jobs, self._config(["delivery", "digital"])
        )
        assert len(scoreable) == 1

    def test_mixed_batch(self):
        jobs = [
            self._job("Director Digital Delivery"),   # passes
            self._job("Senior Art Director"),          # blocked
            self._job("Software Engineer II"),         # blocked
            self._job("Campaign Operations Manager"),  # passes
        ]
        domain_words = ["delivery", "digital", "operations", "program", "technical",
                        "marketing", "campaign", "producer", "implementation",
                        "transformation", "platform", "product", "solutions"]
        scoreable, skipped = _filter_scoreable_jobs(jobs, self._config(domain_words))
        assert len(scoreable) == 2
        assert len(skipped) == 2
        assert scoreable[0]["title"] == "Director Digital Delivery"
        assert scoreable[1]["title"] == "Campaign Operations Manager"
