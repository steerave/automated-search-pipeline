"""
sheets_updater.py

Appends job rows to a Google Sheet.
- "Jobs" tab: qualifying jobs (score >= min_fit_score)
- "Below Threshold" tab: jobs that were scored but fell below min_fit_score
Both tabs get full formatting: frozen header, auto-filter, text wrap, column widths,
conditional formatting on Fit Score and My Score.
"""

import logging
import os
import re
from datetime import date

logger = logging.getLogger(__name__)

JOBS_SHEET = "Jobs"
BELOW_SHEET = "Below Threshold"

HEADERS = [
    "Date Found",
    "Search Type",
    "Role Name",
    "Company Name",
    "Employment Type",
    "Remote",
    "Compensation",
    "Location",
    "Fit Score",
    "Fit Notes",
    "Job Description",
    "Direct Link",
    "Resume File",
    "Cover Letter File",
    "Status",
    "Notes",
    "My Score",
]

# Column widths in pixels (approximate)
COLUMN_WIDTHS = {
    0: 100,   # Date Found
    1: 120,   # Search Type
    2: 220,   # Role Name
    3: 180,   # Company Name
    4: 110,   # Employment Type
    5: 70,    # Remote
    6: 130,   # Compensation
    7: 150,   # Location
    8: 80,    # Fit Score
    9: 300,   # Fit Notes
    10: 350,  # Job Description
    11: 200,  # Direct Link
    12: 200,  # Resume File
    13: 200,  # Cover Letter File
    14: 100,  # Status
    15: 200,  # Notes
    16: 90,   # My Score
}

SEARCH_TYPE_LABELS = {
    "national_remote": "National Remote",
    "local_qc": "Local QC",
}

STATUS_NEW = "New"

MY_SCORE_COL_INDEX = 16  # Column Q (0-indexed)


def _get_client(service_account_path: str):
    """Authenticate and return a gspread client."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise ImportError("gspread and google-auth are required: pip install gspread google-auth")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(service_account_path, scopes=scopes)
    return gspread.authorize(creds)


def _get_or_create_worksheet(spreadsheet, sheet_name: str):
    """Get a worksheet by name, creating it with headers if it doesn't exist."""
    try:
        ws = spreadsheet.worksheet(sheet_name)
        existing_headers = ws.row_values(1)
        if not existing_headers or existing_headers[0] != HEADERS[0]:
            ws.insert_row(HEADERS, index=1)
        return ws, False
    except Exception:
        ws = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(HEADERS))
        ws.insert_row(HEADERS, index=1)
        logger.info(f"Created new worksheet '{sheet_name}' with headers")
        return ws, True


def _apply_all_conditional_formatting(spreadsheet, worksheet) -> None:
    """
    Apply conditional formatting for Fit Score (col I) and My Score (col Q).
    Clears existing rules and rewrites them so this is safe to call repeatedly.
    """
    try:
        from gspread_formatting import (
            CellFormat, Color, BooleanCondition, BooleanRule,
            ConditionalFormatRule, get_conditional_format_rules,
        )
    except ImportError:
        logger.warning("gspread-formatting not installed — skipping conditional formatting")
        return

    sheet_id = worksheet.id

    try:
        rules = get_conditional_format_rules(worksheet)
        rules.clear()

        # Fit Score (col index 8) — 1-10 scale
        fit_range = [{"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": 8, "endColumnIndex": 9}]
        rules.append(ConditionalFormatRule(
            ranges=fit_range,
            booleanRule=BooleanRule(
                condition=BooleanCondition("NUMBER_GREATER_THAN_EQ", ["8"]),
                format=CellFormat(backgroundColor=Color(0.72, 0.88, 0.72)),
            )
        ))
        rules.append(ConditionalFormatRule(
            ranges=fit_range,
            booleanRule=BooleanRule(
                condition=BooleanCondition("NUMBER_BETWEEN", ["5", "7"]),
                format=CellFormat(backgroundColor=Color(1.0, 0.94, 0.6)),
            )
        ))
        rules.append(ConditionalFormatRule(
            ranges=fit_range,
            booleanRule=BooleanRule(
                condition=BooleanCondition("NUMBER_LESS_THAN_EQ", ["4"]),
                format=CellFormat(backgroundColor=Color(0.96, 0.73, 0.73)),
            )
        ))

        # My Score (col index 16) — 1-5 scale
        my_range = [{"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": MY_SCORE_COL_INDEX, "endColumnIndex": MY_SCORE_COL_INDEX + 1}]
        rules.append(ConditionalFormatRule(
            ranges=my_range,
            booleanRule=BooleanRule(
                condition=BooleanCondition("NUMBER_GREATER_THAN_EQ", ["4"]),
                format=CellFormat(backgroundColor=Color(0.72, 0.88, 0.72)),   # Green
            )
        ))
        rules.append(ConditionalFormatRule(
            ranges=my_range,
            booleanRule=BooleanRule(
                condition=BooleanCondition("NUMBER_EQ", ["3"]),
                format=CellFormat(backgroundColor=Color(1.0, 0.94, 0.6)),     # Yellow
            )
        ))
        rules.append(ConditionalFormatRule(
            ranges=my_range,
            booleanRule=BooleanRule(
                condition=BooleanCondition("NUMBER_LESS_THAN_EQ", ["2"]),
                format=CellFormat(backgroundColor=Color(0.96, 0.73, 0.73)),   # Red
            )
        ))

        rules.save()
    except Exception as e:
        logger.warning(f"Conditional formatting failed: {e}")


def _apply_my_score_dropdown(spreadsheet, worksheet) -> None:
    """Apply 1–5 dropdown validation to the My Score column."""
    sheet_id = worksheet.id
    requests = [{
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "startColumnIndex": MY_SCORE_COL_INDEX,
                "endColumnIndex": MY_SCORE_COL_INDEX + 1,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [
                        {"userEnteredValue": "1 — Poor fit"},
                        {"userEnteredValue": "2 — Weak fit"},
                        {"userEnteredValue": "3 — Moderate fit"},
                        {"userEnteredValue": "4 — Good fit"},
                        {"userEnteredValue": "5 — Perfect fit"},
                    ],
                },
                "showCustomUi": True,
                "strict": False,  # Allow blank (unreviewed rows)
            },
        }
    }]
    try:
        spreadsheet.batch_update({"requests": requests})
    except Exception as e:
        logger.warning(f"My Score dropdown validation failed: {e}")


def _ensure_my_score_column(spreadsheet, worksheet) -> None:
    """
    Add 'My Score' header + dropdown if not already present.
    Safe to call on every connect() — no-ops if column already exists.
    """
    headers = worksheet.row_values(1)

    if "My Score" not in headers:
        # Expand the sheet if it doesn't have enough columns
        col_num = len(headers) + 1
        sheet_id = worksheet.id
        current_cols = worksheet.col_count
        if col_num > current_cols:
            spreadsheet.batch_update({"requests": [{
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"columnCount": col_num},
                    },
                    "fields": "gridProperties.columnCount",
                }
            }]})
        worksheet.update_cell(1, col_num, "My Score")
        logger.info(f"Added 'My Score' column to '{worksheet.title}'")

    _apply_my_score_dropdown(spreadsheet, worksheet)
    _apply_all_conditional_formatting(spreadsheet, worksheet)


def _apply_formatting(spreadsheet, worksheet, header_color: tuple) -> None:
    """
    Apply full formatting to a worksheet:
    - Frozen header row
    - Colored bold header
    - Auto-filter on all columns
    - Text wrap on wide columns
    - Column widths
    - Conditional formatting on Fit Score + My Score
    """
    try:
        from gspread_formatting import (
            CellFormat, Color, TextFormat, format_cell_range,
        )
    except ImportError:
        logger.warning("gspread-formatting not installed — skipping formatting")
        return

    sheet_id = worksheet.id
    r, g, b = header_color
    num_cols = len(HEADERS)
    last_col_letter = chr(ord("A") + num_cols - 1)  # "Q" for 17 columns

    requests = []

    # 1. Freeze header row
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    })

    # 2. Auto-filter across all columns
    requests.append({
        "setBasicFilter": {
            "filter": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "startColumnIndex": 0,
                    "endColumnIndex": num_cols,
                }
            }
        }
    })

    # 3. Column widths
    for col_idx, width in COLUMN_WIDTHS.items():
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": col_idx,
                    "endIndex": col_idx + 1,
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })

    # 4. Text wrap on wide columns
    wrap_cols = [2, 3, 7, 9, 10, 11, 12, 13, 15]
    for col_idx in wrap_cols:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": col_idx,
                    "endColumnIndex": col_idx + 1,
                },
                "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                "fields": "userEnteredFormat.wrapStrategy",
            }
        })

    # 5. Row height for data rows
    requests.append({
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "startIndex": 1,
                "endIndex": 1000,
            },
            "properties": {"pixelSize": 80},
            "fields": "pixelSize",
        }
    })

    # 6. Header row height
    requests.append({
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "startIndex": 0,
                "endIndex": 1,
            },
            "properties": {"pixelSize": 40},
            "fields": "pixelSize",
        }
    })

    # 7. Vertical align all cells to top
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1},
            "cell": {"userEnteredFormat": {"verticalAlignment": "TOP"}},
            "fields": "userEnteredFormat.verticalAlignment",
        }
    })

    try:
        spreadsheet.batch_update({"requests": requests})
    except Exception as e:
        logger.warning(f"Batch formatting failed: {e}")

    # 8. Header cell formatting (color + bold + white text)
    try:
        header_fmt = CellFormat(
            backgroundColor=Color(r, g, b),
            textFormat=TextFormat(
                bold=True,
                foregroundColor=Color(1, 1, 1),
                fontSize=11,
            ),
            verticalAlignment="MIDDLE",
            wrapStrategy="WRAP",
        )
        format_cell_range(worksheet, f"A1:{last_col_letter}1", header_fmt)
    except Exception as e:
        logger.warning(f"Header formatting failed: {e}")

    # 9. Conditional formatting (Fit Score + My Score)
    _apply_all_conditional_formatting(spreadsheet, worksheet)

    # 10. My Score dropdown
    _apply_my_score_dropdown(spreadsheet, worksheet)

    logger.info(f"Applied formatting to '{worksheet.title}'")


def _clean(val) -> str:
    """Clean null/nan values from scraper output."""
    if val is None or str(val).lower() in ("nan", "none", "null"):
        return ""
    return str(val).strip()


def _job_to_row(job: dict) -> list:
    """Convert a job dict to a spreadsheet row."""
    from job_scraper import format_salary

    today = date.today().strftime("%Y-%m-%d")
    search_type = SEARCH_TYPE_LABELS.get(job.get("search_type", ""), job.get("search_type", ""))

    # Remote field
    if job.get("is_remote"):
        remote = "Yes"
    elif "hybrid" in (job.get("location", "") + job.get("description", ""))[:200].lower():
        remote = "Hybrid"
    else:
        remote = "No"

    # Employment type
    job_type = job.get("job_type", "")
    if job_type:
        job_type = (job_type
                    .replace("fulltime", "Full-time")
                    .replace("parttime", "Part-time")
                    .replace("contract", "Contract"))
    else:
        job_type = "Full-time"

    # Truncate description to 500 chars
    description = job.get("description", "")
    if len(description) > 500:
        description = description[:497] + "..."

    salary = format_salary(job)

    return [
        today,                                   # Date Found
        search_type,                             # Search Type
        _clean(job.get("title", "")),            # Role Name
        _clean(job.get("company", "")),          # Company Name
        job_type,                                # Employment Type
        remote,                                  # Remote
        salary,                                  # Compensation
        _clean(job.get("location", "")),         # Location
        job.get("fit_score", ""),                # Fit Score
        job.get("fit_notes", ""),                # Fit Notes
        description,                             # Job Description
        _clean(job.get("url", "")),              # Direct Link
        job.get("resume_path", ""),              # Resume File
        job.get("cover_letter_path", ""),        # Cover Letter File
        STATUS_NEW,                              # Status
        "",                                      # Notes (user editable)
        "",                                      # My Score (user editable)
    ]


def _append_job_to_worksheet(worksheet, job: dict) -> int:
    """Append a job row and return the row number."""
    row = _job_to_row(job)
    result = worksheet.append_row(row, value_input_option="USER_ENTERED")
    logger.info(f"Appended: {job.get('title')} @ {job.get('company')}")
    try:
        updated_range = result.get("updates", {}).get("updatedRange", "")
        if updated_range:
            match = re.search(r"(\d+):", updated_range)
            return int(match.group(1)) if match else -1
    except Exception:
        pass
    return -1


class SheetsUpdater:
    """Manages the Google Sheets connection and job appending for both tabs."""

    def __init__(self, sheets_id: str, service_account_path: str):
        self.sheets_id = sheets_id
        self.service_account_path = service_account_path
        self._client = None
        self._spreadsheet = None
        self._jobs_ws = None
        self._below_ws = None

    def connect(self) -> None:
        """Authenticate, open the spreadsheet, and ensure both tabs exist."""
        self._client = _get_client(self.service_account_path)
        self._spreadsheet = self._client.open_by_key(self.sheets_id)

        # Jobs tab — dark blue header
        self._jobs_ws, jobs_created = _get_or_create_worksheet(self._spreadsheet, JOBS_SHEET)
        if jobs_created:
            _apply_formatting(
                self._spreadsheet, self._jobs_ws,
                header_color=(0.122, 0.29, 0.49),
            )
        else:
            _ensure_my_score_column(self._spreadsheet, self._jobs_ws)

        # Below Threshold tab — dark gray header
        self._below_ws, below_created = _get_or_create_worksheet(self._spreadsheet, BELOW_SHEET)
        if below_created:
            _apply_formatting(
                self._spreadsheet, self._below_ws,
                header_color=(0.35, 0.35, 0.35),
            )
        else:
            _ensure_my_score_column(self._spreadsheet, self._below_ws)

        logger.info(f"Connected to Google Sheet: {self._spreadsheet.title}")

    def reformat(self) -> None:
        """Re-apply formatting to both tabs (useful after schema changes)."""
        if self._jobs_ws:
            _apply_formatting(self._spreadsheet, self._jobs_ws, header_color=(0.122, 0.29, 0.49))
        if self._below_ws:
            _apply_formatting(self._spreadsheet, self._below_ws, header_color=(0.35, 0.35, 0.35))

    def add_job(self, job: dict) -> int:
        """Add a qualifying job to the Jobs tab. Returns row number."""
        if self._jobs_ws is None:
            raise RuntimeError("Not connected — call connect() first")
        return _append_job_to_worksheet(self._jobs_ws, job)

    def add_job_below_threshold(self, job: dict) -> None:
        """Add a below-threshold job to the Below Threshold tab."""
        if self._below_ws is None:
            raise RuntimeError("Not connected — call connect() first")
        _append_job_to_worksheet(self._below_ws, job)

    def add_jobs_below_threshold_batch(self, jobs: list) -> None:
        """Add multiple below-threshold jobs in a single API call to avoid rate limits."""
        if self._below_ws is None:
            raise RuntimeError("Not connected — call connect() first")
        if not jobs:
            return
        rows = [_job_to_row(job) for job in jobs]
        self._below_ws.append_rows(rows, value_input_option="USER_ENTERED")
        logger.info(f"Batch-appended {len(rows)} below-threshold jobs")

    def update_file_paths(self, row_num: int, resume_path: str, cover_letter_path: str) -> None:
        """Update Resume File and Cover Letter File columns for a row in the Jobs tab."""
        if self._jobs_ws is None or row_num <= 0:
            return
        try:
            self._jobs_ws.update_cell(row_num, 13, resume_path)
            self._jobs_ws.update_cell(row_num, 14, cover_letter_path)
        except Exception as e:
            logger.error(f"Failed to update file paths for row {row_num}: {e}")
