"""
email_notifier.py

Sends a morning digest email with new job matches.
Uses smtplib with Gmail (or any SMTP server).
"""

import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _build_email_body(
    new_jobs: list[dict],
    skipped_count: int,
    duplicate_count: int,
    sheets_url: str,
    errors: list[str],
) -> tuple[str, str]:
    """
    Build plain-text and HTML email bodies.
    Returns (plain_text, html_text).
    """
    today = date.today().strftime("%b %d")
    total_new = len(new_jobs)

    # Sort by fit score descending for display
    sorted_jobs = sorted(new_jobs, key=lambda j: j.get("fit_score", 0), reverse=True)
    top_jobs = sorted_jobs[:10]  # Show top 10 in email

    # ---- Plain Text ----
    lines = [
        f"Job Search Update — {total_new} new job(s) found ({today})",
        "=" * 60,
        "",
    ]

    if top_jobs:
        lines.append("TOP MATCHES:")
        for job in top_jobs:
            score = job.get("fit_score", "?")
            title = job.get("title", "Unknown Role")
            company = job.get("company", "Unknown Company")
            from job_scraper import format_salary
            salary = format_salary(job)
            url = job.get("url", "")
            resume = job.get("resume_path", "")
            cover = job.get("cover_letter_path", "")
            search_type = job.get("search_type", "")
            label = "Remote" if search_type == "national_remote" else "Local"

            line = f"  [{score}/10] {title} @ {company}"
            if salary:
                line += f" — {salary}"
            line += f" [{label}]"
            lines.append(line)
            if url:
                lines.append(f"         Job: {url}")
            if resume:
                lines.append(f"         Resume: {resume}")
            if cover:
                lines.append(f"         Cover Letter: {cover}")
            lines.append("")

    lines.extend([
        "",
        f"View all jobs in Google Sheets: {sheets_url}" if sheets_url else "",
        "",
        "-" * 60,
        f"Summary: {total_new} added | {skipped_count} below threshold | {duplicate_count} duplicates skipped",
    ])

    if errors:
        lines.append("")
        lines.append("ERRORS:")
        for err in errors:
            lines.append(f"  • {err}")

    plain_text = "\n".join(l for l in lines)

    # ---- HTML ----
    html_parts = [
        "<html><body>",
        f"<h2>Job Search Update — {total_new} new job(s) found ({today})</h2>",
    ]

    if top_jobs:
        html_parts.append("<h3>Top Matches</h3>")
        html_parts.append("<table border='0' cellpadding='6' cellspacing='0' style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px;'>")
        html_parts.append("<tr style='background:#1F497D;color:white;'><th>Score</th><th>Role</th><th>Company</th><th>Salary</th><th>Type</th><th>Links</th></tr>")

        for i, job in enumerate(top_jobs):
            score = job.get("fit_score", "?")
            title = job.get("title", "Unknown Role")
            company = job.get("company", "Unknown Company")
            from job_scraper import format_salary
            salary = format_salary(job) or "—"
            url = job.get("url", "")
            resume = job.get("resume_path", "")
            cover = job.get("cover_letter_path", "")
            search_type = job.get("search_type", "")
            label = "Remote" if search_type == "national_remote" else "Local"

            # Score color
            try:
                score_int = int(score)
                if score_int >= 8:
                    score_color = "#2d7a2d"
                    score_bg = "#d4edda"
                elif score_int >= 5:
                    score_color = "#856404"
                    score_bg = "#fff3cd"
                else:
                    score_color = "#721c24"
                    score_bg = "#f8d7da"
            except (ValueError, TypeError):
                score_color = "#000"
                score_bg = "#fff"

            bg = "#f8f9fa" if i % 2 == 0 else "#ffffff"
            link_parts = []
            if url:
                link_parts.append(f"<a href='{url}'>Job</a>")
            if resume:
                link_parts.append(f"<a href='file:///{resume.replace(chr(92), '/')}'>Resume</a>")
            if cover:
                link_parts.append(f"<a href='file:///{cover.replace(chr(92), '/')}'>Cover Letter</a>")
            links_html = " &bull; ".join(link_parts) if link_parts else "—"

            html_parts.append(
                f"<tr style='background:{bg};'>"
                f"<td style='background:{score_bg};color:{score_color};font-weight:bold;text-align:center;border-radius:4px;'>{score}/10</td>"
                f"<td>{title}</td>"
                f"<td>{company}</td>"
                f"<td>{salary}</td>"
                f"<td>{label}</td>"
                f"<td>{links_html}</td>"
                f"</tr>"
            )

        html_parts.append("</table>")

    if sheets_url:
        html_parts.append(f"<p><a href='{sheets_url}' style='font-size:16px;'>📊 View All Jobs in Google Sheets</a></p>")

    html_parts.extend([
        f"<hr/>",
        f"<p style='color:#666;font-size:12px;'>Summary: <strong>{total_new}</strong> added &bull; "
        f"<strong>{skipped_count}</strong> below threshold &bull; "
        f"<strong>{duplicate_count}</strong> duplicates skipped</p>",
    ])

    if errors:
        html_parts.append("<h3 style='color:red;'>Errors</h3><ul>")
        for err in errors:
            html_parts.append(f"<li>{err}</li>")
        html_parts.append("</ul>")

    html_parts.append("</body></html>")
    html_text = "\n".join(html_parts)

    return plain_text, html_text


def send_digest(
    new_jobs: list[dict],
    skipped_count: int,
    duplicate_count: int,
    sheets_url: str,
    errors: list[str],
    smtp_host: str,
    smtp_port: int,
    sender: str,
    password: str,
    recipient: str,
) -> bool:
    """
    Send the morning digest email.

    Returns:
        True if sent successfully, False otherwise.
    """
    today = date.today().strftime("%b %d")
    total_new = len(new_jobs)
    subject = f"Job Search Update — {total_new} new job(s) found ({today})"

    plain_text, html_text = _build_email_body(
        new_jobs, skipped_count, duplicate_count, sheets_url, errors
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_text, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [recipient], msg.as_string())
        logger.info(f"Digest email sent to {recipient}: {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP authentication failed. For Gmail, make sure you're using an App Password "
            "(not your regular password). Go to myaccount.google.com/apppasswords to create one."
        )
        return False
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_digest_from_env(
    new_jobs: list[dict],
    skipped_count: int,
    duplicate_count: int,
    errors: list[str],
) -> bool:
    """
    Convenience wrapper that reads SMTP config from environment variables.
    """
    sender = os.getenv("EMAIL_SENDER", "")
    password = os.getenv("EMAIL_PASSWORD", "")
    recipient = os.getenv("EMAIL_RECIPIENT", "")
    smtp_host = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    sheets_id = os.getenv("GOOGLE_SHEETS_ID", "")

    if not all([sender, password, recipient]):
        logger.warning("Email credentials not configured — skipping email notification")
        return False

    sheets_url = f"https://docs.google.com/spreadsheets/d/{sheets_id}" if sheets_id else ""

    return send_digest(
        new_jobs=new_jobs,
        skipped_count=skipped_count,
        duplicate_count=duplicate_count,
        sheets_url=sheets_url,
        errors=errors,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        sender=sender,
        password=password,
        recipient=recipient,
    )
