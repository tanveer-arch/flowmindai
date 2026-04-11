"""GitHub connector – simulates creating issues in a GitHub repository."""


def execute_action(action: str, params: dict) -> dict:
    if action == "create_issue":
        title = params.get("title", "Untitled issue")
        return {
            "success": True,
            "message": "GitHub issue created successfully",
            "data": {
                "issue_id": "GH-201",
                "title": title,
                "url": f"https://github.com/flowmind/repo/issues/201",
            },
        }

    return {
        "success": False,
        "message": f"Unsupported action '{action}' for github connector",
        "data": {},
    }
