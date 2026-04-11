"""Mock Project Management connector – simulates an issue tracker (Jira/Linear/Trello)."""


def execute_action(action: str, params: dict) -> dict:
    if action == "get_issue":
        return {
            "success": True,
            "message": "Issue retrieved successfully",
            "data": {
                "id": "ISSUE-101",
                "title": "Production login failure",
                "priority": params.get("priority", "critical"),
                "reporter": "qa-team",
                "status": "open",
            },
        }

    return {
        "success": False,
        "message": f"Unsupported action '{action}' for mock_pm connector",
        "data": {},
    }
