"""Google Sheets connector – simulates appending rows to a spreadsheet."""


def execute_action(action: str, params: dict) -> dict:
    if action == "append_row":
        sheet_name = params.get("sheet_name", "Sheet1")
        row_data = params.get("row_data", {})
        return {
            "success": True,
            "message": f"Row appended to '{sheet_name}'",
            "data": {
                "sheet_name": sheet_name,
                "row_data": row_data,
                "row_index": 42,  # fake row number
            },
        }

    return {
        "success": False,
        "message": f"Unsupported action '{action}' for sheets connector",
        "data": {},
    }
