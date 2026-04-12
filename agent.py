"""
FlowMind — Member 4: Agent & Orchestration
File: agent.py

Exposes: generate_steps(prompt: str) -> {"steps": [...]}

Calls Groq API (llama-3.3-70b-versatile) with a structured system prompt that forces
the LLM to produce a strict JSON workflow plan.  Includes one automatic retry
on JSON parse failure before raising.
"""

import json
import logging
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client (initialised lazily so missing key doesn't crash import)
# ---------------------------------------------------------------------------
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. Add it to your .env file."
            )
        _client = Groq(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are FlowMind AI, a workflow automation engine \
powered by real MCP (Model Context Protocol) servers.

AVAILABLE TOOLS — use ONLY these exact names:
1. create_jira_ticket
   params: summary (string), description (string), priority (string)
   → creates Jira ticket, returns ticket_id like JRA-42

2. create_github_issue
   params: title (string), body (string)
   → creates GitHub issue via real MCP server
   → if Jira ran before this, mention ticket_id in body

3. update_google_sheet
   params: sheet_name (string), row_data (object)
   → appends row via real Google Sheets MCP server
   → include ALL data from prior steps in row_data

4. send_email
   params: to (string), subject (string), body (string)
   → sends real email via Gmail MCP server

5. request_approval
   params: reason (string)
   → pauses workflow, human must approve before continuing

6. request_user_input
   params: question (string)
   → pauses to collect custom input from user

STRICT RULES:
- Return ONLY valid JSON. No markdown. No explanation. No text outside JSON.
- If workflow involves email: ALWAYS put request_user_input \
  IMMEDIATELY BEFORE send_email. No exceptions.
- If action is sensitive (delete, publish, broadcast to all): \
  add request_approval before it.
- Chain data between steps: if Jira creates JRA-42, \
  GitHub body must reference JRA-42. \
  Sheets row must include jira_id and github issue url.

RESPONSE FORMAT — return exactly this structure, nothing else:
{
  "steps": [
    {
      "tool": "tool_name_here",
      "params": {
        "field1": "value1"
      }
    }
  ]
}

EXAMPLES:

Input: "when a bug is reported create a ticket and notify the team"
Output:
{
  "steps": [
    {
      "tool": "create_jira_ticket",
      "params": {
        "summary": "Bug reported",
        "description": "A bug has been reported and logged via FlowMind.",
        "priority": "High"
      }
    },
    {
      "tool": "create_github_issue",
      "params": {
        "title": "Bug fix needed (Jira: JRA-?)",
        "body": "Bug reported. Linked to Jira ticket JRA-?. Needs investigation."
      }
    },
    {
      "tool": "update_google_sheet",
      "params": {
        "sheet_name": "Bug Log",
        "row_data": {
          "jira_id": "JRA-?",
          "github_issue": "pending",
          "status": "open",
          "type": "bug"
        }
      }
    }
  ]
}

Input: "create a task for the design team and email the designer"
Output:
{
  "steps": [
    {
      "tool": "create_jira_ticket",
      "params": {
        "summary": "Design task assigned",
        "description": "New design task needs attention from the design team.",
        "priority": "Medium"
      }
    },
    {
      "tool": "request_user_input",
      "params": {
        "question": "What should the email to the designer say?"
      }
    },
    {
      "tool": "send_email",
      "params": {
        "to": "designer@company.com",
        "subject": "New design task assigned",
        "body": "Please check Jira for your new task details."
      }
    }
  ]
}

Input: "log a security incident and get approval before notifying clients"
Output:
{
  "steps": [
    {
      "tool": "create_jira_ticket",
      "params": {
        "summary": "Security incident logged",
        "description": "Security incident detected and requires immediate review.",
        "priority": "Critical"
      }
    },
    {
      "tool": "update_google_sheet",
      "params": {
        "sheet_name": "Incidents",
        "row_data": {
          "type": "security",
          "jira_id": "JRA-?",
          "status": "under review"
        }
      }
    },
    {
      "tool": "request_approval",
      "params": {
        "reason": "About to notify all clients about a security incident. Please approve."
      }
    },
    {
      "tool": "request_user_input",
      "params": {
        "question": "What should the client notification email say?"
      }
    },
    {
      "tool": "send_email",
      "params": {
        "to": "clients@company.com",
        "subject": "Important security update",
        "body": "We are writing to inform you about a recent security incident."
      }
    }
  ]
}
"""

# Valid tool names the LLM is allowed to produce
VALID_TOOLS: set[str] = {
    "create_jira_ticket",
    "create_github_issue",
    "update_google_sheet",
    "send_email",
    "request_approval",
    "request_user_input",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_steps(prompt: str) -> dict:
    """
    Convert a natural-language workflow description into a structured step plan.

    Args:
        prompt: User's workflow instruction.

    Returns:
        {"steps": [{"tool": "...", "params": {...}}, ...]}

    Raises:
        ValueError: If the LLM returns invalid JSON on both the first attempt
                    and a single automatic retry.
        EnvironmentError: If GROQ_API_KEY is not set.
    """
    client = _get_client()

    raw = _call_groq(client, prompt, retry_message=None)
    try:
        return _parse_and_validate(raw)
    except ValueError:
        # --- Retry once with an explicit correction instruction ---
        log.warning("agent: JSON parse failed on first attempt — retrying with correction hint")
        raw2 = _call_groq(
            client,
            prompt,
            retry_message="You must return only valid JSON. No text. No markdown. No code fences.",
        )
        try:
            return _parse_and_validate(raw2)
        except ValueError:
            raise ValueError(f"LLM returned invalid JSON: {raw2}")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _call_groq(client: Groq, prompt: str, retry_message: str | None) -> str:
    """Build messages and call the Groq API. Returns the raw string response."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    if retry_message:
        messages.append({"role": "user", "content": retry_message})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.0,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _parse_and_validate(raw: str) -> dict:
    """
    Parse raw LLM string as JSON and validate the steps list.

    Filters out any step whose tool is not in VALID_TOOLS.
    Raises ValueError on JSON decode failure.
    """
    cleaned = raw.strip()
    # Strip accidental markdown fences
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from LLM: {exc}") from exc

    raw_steps = data.get("steps", [])
    if not isinstance(raw_steps, list):
        raise ValueError("'steps' is not a list")

    valid_steps = []
    for step in raw_steps:
        tool = step.get("tool", "")
        if tool not in VALID_TOOLS:
            log.warning("agent: skipping unknown tool '%s'", tool)
            continue
        # Ensure params is always a dict
        params = step.get("params", {})
        if not isinstance(params, dict):
            params = {"raw_input": str(params)}
        valid_steps.append({"tool": tool, "params": params})

    log.info("agent: generated %d valid steps for prompt", len(valid_steps))
    return {"steps": valid_steps}
