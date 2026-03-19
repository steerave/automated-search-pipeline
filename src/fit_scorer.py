"""
fit_scorer.py

Uses Claude API to score how well a job matches the user's profile.
Returns a score 1-10 with a rationale string.
Supports both real-time (messages API) and batch (Batch API) modes.
"""

import json
import logging
import time

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are an expert career advisor and job fit analyst.
Your job is to evaluate how well a candidate's profile matches a job description.
Be honest, specific, and concise. Focus on skills, experience level, and domain alignment."""

FIT_SCORE_PROMPT = """Rate how well this candidate matches the job description on a scale of 1-10.

CANDIDATE PROFILE:
Name: {name}
Headline: {headline}
Summary: {summary}

Skills: {skills}

Experience:
{experience_text}

Education:
{education_text}

---

JOB POSTING:
Title: {job_title}
Company: {company}
Location: {location}
Type: {job_type}
Compensation: {salary}

Description:
{job_description}

---

Respond ONLY with a JSON object in this exact format:
{{
  "score": <integer 1-10>,
  "rationale": "<2-3 sentences: key matches, key gaps, overall verdict>"
}}

Scoring guide:
9-10: Exceptional match — candidate meets nearly all requirements, strong domain fit
7-8: Good match — candidate meets most requirements, minor gaps
5-6: Moderate match — candidate meets core requirements, notable gaps
3-4: Weak match — significant skill or experience gaps
1-2: Poor match — fundamentally different background

Be specific in the rationale. Name actual skills/technologies that match or are missing."""


def _build_profile_text(profile: dict) -> dict:
    """Format profile fields for the prompt."""
    skills_text = ", ".join(profile.get("skills", [])) or "Not specified"

    experience_parts = []
    for exp in profile.get("experience", [])[:5]:  # Top 5 roles
        title = exp.get("title", "Unknown Role")
        company = exp.get("company", "")
        role_line = f"- {title}"
        if company:
            role_line += f" @ {company}"
        started = exp.get("started_on", "")
        finished = exp.get("finished_on", "Present")
        if started:
            role_line += f" ({started} – {finished})"
        experience_parts.append(role_line)
        for bullet in exp.get("bullets", [])[:3]:  # Top 3 bullets per role
            if bullet.strip():
                experience_parts.append(f"  • {bullet.strip()}")
    experience_text = "\n".join(experience_parts) or "Not specified"

    education_parts = []
    for edu in profile.get("education", []):
        degree = edu.get("degree", "")
        field = edu.get("field", "")
        school = edu.get("school", "")
        end = edu.get("end_date", "")
        parts = [p for p in [degree, field] if p]
        edu_line = " in ".join(parts) if parts else "Degree"
        if school:
            edu_line += f" — {school}"
        if end:
            edu_line += f" ({end})"
        education_parts.append(edu_line)
    education_text = "\n".join(f"- {e}" for e in education_parts) or "Not specified"

    return {
        "skills": skills_text,
        "experience_text": experience_text,
        "education_text": education_text,
    }


def score_job(job: dict, profile: dict, client) -> dict:
    """
    Score a single job against the candidate profile using the Claude API.

    Args:
        job: Job dict from scraper
        profile: Parsed profile dict
        client: anthropic.Anthropic client instance

    Returns:
        dict with keys: score (int), rationale (str)
    """
    from job_scraper import format_salary

    profile_texts = _build_profile_text(profile)
    salary = format_salary(job) if job else ""

    # Truncate description to avoid token bloat
    description = job.get("description", "")
    if len(description) > 3000:
        description = description[:3000] + "...[truncated]"

    prompt = FIT_SCORE_PROMPT.format(
        name=profile.get("name", "Candidate"),
        headline=profile.get("headline", ""),
        summary=profile.get("summary", "")[:500] if profile.get("summary") else "",
        skills=profile_texts["skills"],
        experience_text=profile_texts["experience_text"],
        education_text=profile_texts["education_text"],
        job_title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        job_type=job.get("job_type", ""),
        salary=salary,
        job_description=description,
    )

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()

            # Extract JSON from response
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            result = json.loads(raw)
            score = int(result.get("score", 5))
            score = max(1, min(10, score))  # Clamp to 1-10
            rationale = str(result.get("rationale", "")).strip()

            logger.info(f"Scored '{job.get('title')}' @ '{job.get('company')}': {score}/10")
            return {"score": score, "rationale": rationale}

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}\nRaw: {raw[:200]}")
            if attempt < 2:
                time.sleep(2)
        except Exception as e:
            logger.error(f"Claude API error on attempt {attempt + 1}: {e}")
            if attempt < 2:
                time.sleep(5)

    logger.error(f"Failed to score job after 3 attempts: {job.get('title')} @ {job.get('company')}")
    return {"score": 5, "rationale": "Score unavailable due to API error."}


def score_jobs_batch(jobs: list[dict], profile: dict, client) -> list[dict]:
    """
    Score multiple jobs. Returns each job dict enriched with 'fit_score' and 'fit_notes'.
    Processes sequentially with small delays to respect rate limits.
    """
    scored = []
    for i, job in enumerate(jobs):
        logger.info(f"Scoring job {i+1}/{len(jobs)}: {job.get('title')} @ {job.get('company')}")
        result = score_job(job, profile, client)
        job["fit_score"] = result["score"]
        job["fit_notes"] = result["rationale"]
        scored.append(job)
        if i < len(jobs) - 1:
            time.sleep(0.5)  # Small delay between calls
    return scored
