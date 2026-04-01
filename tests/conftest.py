"""Shared fixtures for feedback analysis tests."""

import sys
from pathlib import Path

# Ensure src/ is importable in tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


@pytest.fixture
def sample_tracker_rows():
    """Rows from the Job Tracker sheet — simulates gspread get_all_records()."""
    return [
        {
            "Date Found": "2026-03-15",
            "Search Type": "National Remote",
            "Role Name": "Director Digital Delivery",
            "Company Name": "Acme SaaS Corp",
            "Employment Type": "Full-time",
            "Remote": "Yes",
            "Compensation": "$180,000 - $220,000",
            "Location": "Remote",
            "Fit Score": 8,
            "Fit Notes": "Strong delivery leadership match",
            "Job Description": "Lead digital delivery for SaaS platform...",
            "Direct Link": "https://example.com/job/123",
            "Resume File": "",
            "Cover Letter File": "",
            "Status": "Applied",
            "Notes": "Great culture, AI-forward company",
            "My Score": "5 — Perfect fit",
        },
        {
            "Date Found": "2026-03-15",
            "Search Type": "National Remote",
            "Role Name": "Director of Ecommerce",
            "Company Name": "RetailCo",
            "Employment Type": "Full-time",
            "Remote": "No",
            "Compensation": "$150,000 - $180,000",
            "Location": "Chicago, IL",
            "Fit Score": 6,
            "Fit Notes": "Some delivery overlap but ecommerce focused",
            "Job Description": "Manage ecommerce platform operations...",
            "Direct Link": "https://example.com/job/456",
            "Resume File": "",
            "Cover Letter File": "",
            "Status": "New",
            "Notes": "Not really my area, exclude ecommerce director roles",
            "My Score": "1 — Poor fit",
        },
        {
            "Date Found": "2026-03-16",
            "Search Type": "Local QC",
            "Role Name": "Senior TPM",
            "Company Name": "TechStartup Inc",
            "Employment Type": "Full-time",
            "Remote": "Hybrid",
            "Compensation": "",
            "Location": "Davenport, IA",
            "Fit Score": 7,
            "Fit Notes": "Good TPM match, local role",
            "Job Description": "Technical program management for AI platform...",
            "Direct Link": "https://example.com/job/789",
            "Resume File": "",
            "Cover Letter File": "",
            "Status": "New",
            "Notes": "",
            "My Score": "4 — Good fit",
        },
        {
            "Date Found": "2026-03-17",
            "Search Type": "National Remote",
            "Role Name": "VP Technology Delivery",
            "Company Name": "BigCorp",
            "Employment Type": "Full-time",
            "Remote": "Yes",
            "Compensation": "$250,000+",
            "Location": "Remote",
            "Fit Score": 9,
            "Fit Notes": "Excellent match",
            "Job Description": "Lead technology delivery org...",
            "Direct Link": "https://example.com/job/101",
            "Resume File": "",
            "Cover Letter File": "",
            "Status": "New",
            "Notes": "",
            "My Score": "",
        },
    ]


@pytest.fixture
def sample_status_rows():
    """Rows from the 2026 Job Status sheet — simulates gspread get_all_records()."""
    return [
        {
            "Role Title": "Director Digital Delivery",
            "Company": "Acme SaaS Corp",
            "Industry": "SaaS / Technology",
            "Compensation Range": "$180,000 - $220,000",
            "Remote Only": "Yes",
            "Direct Job Description Link": "https://example.com/job/123",
            "Applied": "Yes",
            "Application Link": "https://acme.com/careers/apply",
            "Notes": "AI-forward company, great mission",
            "Status": "Interviewing",
        },
        {
            "Role Title": "Senior Director Program Management",
            "Company": "CloudPlatform Co",
            "Industry": "Cloud / AI",
            "Compensation Range": "$200,000 - $240,000",
            "Remote Only": "Yes",
            "Direct Job Description Link": "https://example.com/job/200",
            "Applied": "Yes",
            "Application Link": "https://cloudplatform.com/apply",
            "Notes": "Found via recruiter, strong AI focus",
            "Status": "Applied",
        },
    ]


@pytest.fixture
def sample_last_analysis():
    """Previous analysis state."""
    return {
        "last_run": "2026-03-20T06:00:00",
        "tracker_feedback_count": 1,
        "status_row_count": 0,
    }


@pytest.fixture
def sample_config():
    """Minimal config.yaml content for testing."""
    return {
        "job_titles": [
            "Senior Director Digital Delivery",
            "Director Digital Delivery",
            "Director Technical Program Management",
        ],
        "required_keywords": [
            "delivery",
            "program management",
            "digital transformation",
        ],
        "exclude_keywords": [
            "digital marketing",
            "entry level",
            "supply chain",
        ],
        "exclude_companies": [],
        "min_fit_score": 5,
    }
