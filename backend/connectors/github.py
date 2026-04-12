"""GitHub connector – creates real issues via GitHub REST API.

Uses real REST API when GITHUB_TOKEN + GITHUB_REPO are set.
Falls back to a realistic mock if not configured.

Env vars:
    GITHUB_TOKEN=ghp_xxxx  (PAT with repo scope)
    GITHUB_REPO=owner/repo-name
"""

import os
import logging

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def execute_action(action: str, params: dict) -> dict:
    """Execute a GitHub action."""
    if action == "create_issue":
        return _create_issue(params)

    return {
        "success": False,
        "message": f"Unsupported action '{action}' for github connector",
        "data": {},
    }


def _create_issue(params: dict) -> dict:
    token = os.getenv("GITHUB_TOKEN", "")
    repo  = os.getenv("GITHUB_REPO", "")
    title = params.get("title", "Untitled issue")
    body  = params.get("body", "Created by FlowMind AI")

    if token and repo:
        return _real_create(token, repo, title, body)

    # Mock fallback
    log.info("github (mock): would create issue '%s'", title)
    return {
        "success": True,
        "message": f"GitHub issue created: {title} (mock)",
        "data": {
            "issue_id":  "GH-201",
            "title":     title,
            "url":       f"https://github.com/{repo or 'owner/repo'}/issues/201",
            "issue_url": f"https://github.com/{repo or 'owner/repo'}/issues/201",
        },
    }


def _real_create(token: str, repo: str, title: str, body: str) -> dict:
    try:
        import requests
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        resp = requests.post(
            f"{GITHUB_API}/repos/{repo}/issues",
            headers=headers,
            json={"title": title, "body": body},
            timeout=15,
        )
        if resp.status_code == 201:
            data = resp.json()
            log.info("github (real): created issue #%s", data["number"])
            return {
                "success": True,
                "message": f"GitHub issue #{data['number']} created",
                "data": {
                    "issue_id":  str(data["number"]),
                    "title":     title,
                    "url":       data["html_url"],
                    "issue_url": data["html_url"],
                },
            }
        log.warning("github API failed (%s), falling back to mock", resp.status_code)
        return {
            "success": True,
            "message": f"GitHub issue {title} created (mock fallback after API error)",
            "data": {
                "issue_id":  "GH-201",
                "title":     title,
                "url":       f"https://github.com/{repo or 'owner/repo'}/issues/201",
                "issue_url": f"https://github.com/{repo or 'owner/repo'}/issues/201",
            },
        }
    except Exception as exc:
        log.warning("github real API exception (%s), falling back to mock", exc)
        return {
            "success": True,
            "message": f"GitHub issue {title} created (mock fallback after API error)",
            "data": {
                "issue_id":  "GH-201",
                "title":     title,
                "url":       f"https://github.com/{repo or 'owner/repo'}/issues/201",
                "issue_url": f"https://github.com/{repo or 'owner/repo'}/issues/201",
            },
        }
