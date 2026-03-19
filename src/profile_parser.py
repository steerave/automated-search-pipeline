"""
profile_parser.py

Parses the user's resume (PDF or DOCX) and LinkedIn data export
into a structured parsed_profile.json used by all AI modules.
"""

import json
import os
import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_resume_pdf(pdf_path: str) -> str:
    """Extract raw text from a PDF resume using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF is required: pip install PyMuPDF")

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Resume PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()

    raw_text = "\n".join(text_parts).strip()
    logger.info(f"Extracted {len(raw_text)} characters from PDF resume")
    return raw_text


def parse_resume_docx(docx_path: str) -> str:
    """Extract raw text from a DOCX resume using python-docx."""
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx is required: pip install python-docx")

    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"Resume DOCX not found: {docx_path}")

    doc = Document(docx_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    raw_text = "\n".join(paragraphs)
    logger.info(f"Extracted {len(raw_text)} characters from DOCX resume")
    return raw_text


def parse_linkedin_export(linkedin_dir: str) -> dict:
    """
    Parse LinkedIn data export CSVs.
    Expected files: Profile.csv, Positions.csv, Skills.csv, Education.csv
    Returns a dict with structured profile data.
    """
    linkedin_path = Path(linkedin_dir)
    result = {
        "name": "",
        "email": "",
        "headline": "",
        "summary": "",
        "positions": [],
        "skills": [],
        "education": [],
    }

    # --- Profile.csv ---
    profile_csv = linkedin_path / "Profile.csv"
    if profile_csv.exists():
        with open(profile_csv, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                result["name"] = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
                result["email"] = row.get("Email Address", "")
                result["headline"] = row.get("Headline", "")
                result["summary"] = row.get("Summary", "")
                break  # Only one row expected
        logger.info("Parsed Profile.csv")
    else:
        logger.warning(f"Profile.csv not found in {linkedin_dir}")

    # --- Positions.csv ---
    positions_csv = linkedin_path / "Positions.csv"
    if positions_csv.exists():
        with open(positions_csv, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                result["positions"].append({
                    "company": row.get("Company Name", ""),
                    "title": row.get("Title", ""),
                    "description": row.get("Description", ""),
                    "started_on": row.get("Started On", ""),
                    "finished_on": row.get("Finished On", ""),
                    "location": row.get("Location", ""),
                })
        logger.info(f"Parsed {len(result['positions'])} positions from Positions.csv")
    else:
        logger.warning(f"Positions.csv not found in {linkedin_dir}")

    # --- Skills.csv ---
    skills_csv = linkedin_path / "Skills.csv"
    if skills_csv.exists():
        with open(skills_csv, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                skill = row.get("Name", "").strip()
                if skill:
                    result["skills"].append(skill)
        logger.info(f"Parsed {len(result['skills'])} skills from Skills.csv")
    else:
        logger.warning(f"Skills.csv not found in {linkedin_dir}")

    # --- Education.csv ---
    education_csv = linkedin_path / "Education.csv"
    if education_csv.exists():
        with open(education_csv, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                result["education"].append({
                    "school": row.get("School Name", ""),
                    "degree": row.get("Degree Name", ""),
                    "field": row.get("Field Of Study", ""),
                    "start_date": row.get("Start Date", ""),
                    "end_date": row.get("End Date", ""),
                    "activities": row.get("Activities and Societies", ""),
                    "notes": row.get("Notes", ""),
                })
        logger.info(f"Parsed {len(result['education'])} education entries from Education.csv")
    else:
        logger.warning(f"Education.csv not found in {linkedin_dir}")

    return result


def extract_experience_bullets_from_resume(raw_text: str) -> list[dict]:
    """
    Heuristically extract experience bullets from raw resume text.
    Returns a list of dicts: {"company": "", "title": "", "bullets": []}

    This is best-effort — the AI will use raw_resume_text as fallback.
    """
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    experience_section = []
    in_experience = False
    current_role = None

    experience_headers = {"experience", "work experience", "professional experience", "employment"}
    stop_headers = {"education", "skills", "certifications", "projects", "volunteer", "awards", "publications"}

    for line in lines:
        lower = line.lower().strip(":-")
        if lower in experience_headers:
            in_experience = True
            continue
        if lower in stop_headers and in_experience:
            break
        if not in_experience:
            continue

        # Detect bullet points
        if line.startswith(("•", "-", "*", "–", "▪", "›")) or (len(line) > 2 and line[0].isupper() and line.endswith(".")):
            bullet = line.lstrip("•-*–▪› ").strip()
            if current_role is not None:
                current_role["bullets"].append(bullet)
        else:
            # Treat as a new role header
            if current_role is not None:
                experience_section.append(current_role)
            current_role = {"company": "", "title": line, "bullets": []}

    if current_role is not None:
        experience_section.append(current_role)

    return experience_section


def build_profile(resume_path: str, linkedin_dir: str) -> dict:
    """
    Main function: parse resume + LinkedIn export into a unified profile dict.
    """
    profile = {
        "name": "",
        "email": "",
        "headline": "",
        "summary": "",
        "skills": [],
        "experience": [],
        "education": [],
        "raw_resume_text": "",
    }

    # --- Parse resume ---
    resume_path_obj = Path(resume_path)
    if resume_path_obj.exists():
        suffix = resume_path_obj.suffix.lower()
        if suffix == ".pdf":
            raw_text = parse_resume_pdf(resume_path)
        elif suffix in (".docx", ".doc"):
            raw_text = parse_resume_docx(resume_path)
        else:
            logger.warning(f"Unsupported resume format: {suffix}. Skipping resume parse.")
            raw_text = ""

        profile["raw_resume_text"] = raw_text
        bullets = extract_experience_bullets_from_resume(raw_text)
        if bullets:
            profile["experience"] = bullets
            logger.info(f"Extracted {len(bullets)} experience entries from resume")
    else:
        logger.warning(f"Resume not found at {resume_path} — skipping resume parse")

    # --- Parse LinkedIn export ---
    linkedin_path = Path(linkedin_dir)
    if linkedin_path.exists() and any(linkedin_path.iterdir()):
        linkedin_data = parse_linkedin_export(linkedin_dir)

        # LinkedIn takes precedence for structured fields
        if linkedin_data["name"]:
            profile["name"] = linkedin_data["name"]
        if linkedin_data["email"]:
            profile["email"] = linkedin_data["email"]
        if linkedin_data["headline"]:
            profile["headline"] = linkedin_data["headline"]
        if linkedin_data["summary"]:
            profile["summary"] = linkedin_data["summary"]
        if linkedin_data["skills"]:
            profile["skills"] = linkedin_data["skills"]
        if linkedin_data["education"]:
            profile["education"] = linkedin_data["education"]

        # Merge positions: LinkedIn positions enrich the experience list
        if linkedin_data["positions"]:
            merged = []
            for pos in linkedin_data["positions"]:
                # Try to match with an extracted bullet entry
                matched = False
                for exp in profile["experience"]:
                    if pos["company"].lower() in exp.get("title", "").lower() or \
                       pos["title"].lower() in exp.get("title", "").lower():
                        exp["company"] = pos["company"]
                        exp["title"] = pos["title"]
                        exp["started_on"] = pos.get("started_on", "")
                        exp["finished_on"] = pos.get("finished_on", "")
                        exp["location"] = pos.get("location", "")
                        matched = True
                        break
                if not matched:
                    # Add LinkedIn position even if no resume bullets matched
                    merged.append({
                        "company": pos["company"],
                        "title": pos["title"],
                        "started_on": pos.get("started_on", ""),
                        "finished_on": pos.get("finished_on", ""),
                        "location": pos.get("location", ""),
                        "bullets": [pos["description"]] if pos.get("description") else [],
                    })
            # Append any unmatched LinkedIn positions
            profile["experience"] = profile["experience"] + merged
    else:
        logger.warning(f"LinkedIn export directory empty or missing: {linkedin_dir}")

    return profile


def save_profile(profile: dict, output_path: str) -> None:
    """Save parsed profile to JSON file."""
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved parsed profile to {output_path}")


def load_profile(profile_path: str) -> dict:
    """Load parsed profile from JSON file."""
    if not os.path.exists(profile_path):
        raise FileNotFoundError(
            f"Parsed profile not found at {profile_path}. "
            "Run setup.py first to generate it."
        )
    with open(profile_path, encoding="utf-8") as f:
        return json.load(f)
