"""Jira connector – creates issues via Jira REST API v3.

Uses real REST API when JIRA_DOMAIN + JIRA_EMAIL + JIRA_API_TOKEN are set.
Falls back to a realistic mock response if credentials are missing.

Env vars:
    JIRA_DOMAIN=yourcompany.atlassian.net
    JIRA_EMAIL=you@company.com
    JIRA_API_TOKEN=your_token
    JIRA_PROJECT_KEY=TNEXA
"""

import os
import logging
from base64 import b64encode

log = logging.getLogger(__name__)

_DOMAIN      = os.getenv("JIRA_DOMAIN", "")
_EMAIL       = os.getenv("JIRA_EMAIL", "")
_TOKEN       = os.getenv("JIRA_API_TOKEN", "")
_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "FLOW")

# Incrementing counter for mock ticket IDs
_ticket_counter = 40


def _get_headers() -> dict:
    creds = b64encode(f"{_EMAIL}:{_TOKEN}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def execute_action(action: str, params: dict) -> dict:
    """Execute a Jira action.

    Supported:
      create_ticket / create_issue → params: summary/title, description/body, priority
    """
    # Normalize action name (normalize.py uses create_ticket)
    if action in ("create_ticket", "create_issue"):
        return _create_ticket(params)

    return {
        "success": False,
        "message": f"Unsupported action '{action}' for jira connector",
        "data": {},
    }


def _create_ticket(params: dict) -> dict:
    global _ticket_counter
    summary     = params.get("summary", params.get("title", "Untitled ticket"))
    description = params.get("description", params.get("body", "Created by FlowMind AI"))
    priority    = params.get("priority", "Medium")

    # Real API call if credentials present
    if _DOMAIN and _EMAIL and _TOKEN:
        return _real_create(_DOMAIN, params, summary, description, priority)

    # Mock fallback
    return _mock_create(params)


def _real_create(domain: str, params: dict, summary: str, description: str, priority: str) -> dict:
    try:
        import requests
        payload = {
            "fields": {
                "project":     {"key": _PROJECT_KEY},
                "summary":     summary,
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [
                        {"type": "text", "text": description}
                    ]}]
                },
                "issuetype": {"name": "Task"},
                "priority":  {"name": priority},
            }
        }
        resp = requests.post(
            f"https://{domain}/rest/api/3/issue",
            headers=_get_headers(),
            json=payload,
            timeout=15,
        )
        if resp.status_code == 201:
            data = resp.json()
            ticket_id = data.get("key", "JRA-?")
            log.info("jira (real): created ticket %s", ticket_id)
            return {
                "success": True,
                "message": f"Jira ticket {ticket_id} created",
                "data": {
                    "ticket_id": ticket_id,
                    "issue_id":  ticket_id,
                    "summary":   summary,
                    "priority":  priority,
                    "url":       f"https://{domain}/browse/{ticket_id}",
                },
            }
        log.warning("jira API failed (%s), falling back to mock", resp.status_code)
        return _mock_create(params)
    except Exception as exc:
        log.warning("jira real API exception (%s), falling back to mock", exc)
        return _mock_create(params)

def _mock_create(params: dict) -> dict:
    global _ticket_counter
    summary     = params.get("summary", params.get("title", "Untitled ticket"))
    description = params.get("description", params.get("body", "Created by FlowMind AI"))
    priority    = params.get("priority", "Medium")
    
    _ticket_counter += 1
    ticket_id = f"{_PROJECT_KEY}-{_ticket_counter}"
    log.info("jira (mock): created ticket %s — '%s'", ticket_id, summary)
    return {
        "success": True,
        "message": f"Jira ticket {ticket_id} created (mock)",
        "data": {
            "ticket_id": ticket_id,
            "issue_id":  ticket_id,
            "summary":   summary,
            "priority":  priority,
            "url":       f"https://demo.atlassian.net/browse/{ticket_id}",
        },
    }
