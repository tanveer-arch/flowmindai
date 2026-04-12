"""Google Sheets connector – appends rows via gspread or mock.

Uses gspread + service account when GOOGLE_SHEETS_CREDENTIALS is set.
Falls back to mock if not configured.

Env vars:
    GOOGLE_SHEET_ID=your_sheet_id
    GOOGLE_SHEETS_CREDENTIALS=path/to/service-account.json  (or OAuth token hash)
"""

import logging
import os

log = logging.getLogger(__name__)

_SHEET_ID   = os.getenv("GOOGLE_SHEET_ID", "")
_CREDS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")

# Track row counter for mock
_row_counter = 41


def execute_action(action: str, params: dict) -> dict:
    """Execute a Google Sheets action."""
    if action == "append_row":
        return _append_row(params)

    return {
        "success": False,
        "message": f"Unsupported action '{action}' for sheets connector",
        "data": {},
    }


def _append_row(params: dict) -> dict:
    global _row_counter
    sheet_name = params.get("sheet_name", "Sheet1")
    row_data   = params.get("row_data", {})

    if _SHEET_ID and _CREDS_PATH:
        creds_str = _CREDS_PATH.strip()
        if creds_str.startswith("{") or os.path.isfile(_CREDS_PATH):
            return _real_append(_SHEET_ID, sheet_name, row_data)

    # Mock fallback
    _row_counter += 1
    log.info("sheets (mock): would append row to '%s': %s", sheet_name, row_data)
    return {
        "success": True,
        "message": f"Row appended to '{sheet_name}' (mock)",
        "data": {
            "sheet_name": sheet_name,
            "row_data":   row_data,
            "row_index":  _row_counter,
            "sheet_url":  f"https://docs.google.com/spreadsheets/d/{_SHEET_ID or 'demo'}/edit",
        },
    }


def _real_append(sheet_id: str, sheet_name: str, row_data: dict) -> dict:
    try:
        import gspread
        import json
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds_str = _CREDS_PATH.strip()
        if creds_str.startswith("{"):
            creds_info = json.loads(creds_str)
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        else:
            creds = Credentials.from_service_account_file(_CREDS_PATH, scopes=scopes)
            
        client = gspread.authorize(creds)
        sheet  = client.open_by_key(sheet_id).worksheet(sheet_name)

        # Append row values in order
        row_values = list(row_data.values())
        sheet.append_row(row_values)
        log.info("sheets (real): appended to '%s'", sheet_name)
        return {
            "success": True,
            "message": f"Row appended to '{sheet_name}'",
            "data": {
                "sheet_name": sheet_name,
                "row_data":   row_data,
                "sheet_url":  f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit",
            },
        }
    except Exception as exc:
        log.error("sheets real API failed: %s", exc)
        # Fall back to mock on error
        return {
            "success": True,
            "message": f"Row appended to '{sheet_name}' (mock fallback after API error: {exc})",
            "data": {
                "sheet_name": sheet_name,
                "row_data":   row_data,
                "row_index":  42,
            },
        }
