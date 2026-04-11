"""Slack connector – simulates sending messages to a Slack channel."""


def execute_action(action: str, params: dict) -> dict:
    if action == "send_message":
        channel = params.get("channel", "#general")
        text = params.get("text", "")
        return {
            "success": True,
            "message": f"Message sent to {channel}",
            "data": {
                "channel": channel,
                "text": text,
                "ts": "1712345678.000100",  # fake Slack timestamp
            },
        }

    return {
        "success": False,
        "message": f"Unsupported action '{action}' for slack connector",
        "data": {},
    }
