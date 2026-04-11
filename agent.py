"""
FlowMind AI — LLM Agent Brain (Groq Edition)
Converts natural language workflow instructions into structured JSON tool steps.
Uses Groq API (FREE) with Llama 3.3 70B model.
Team NexaMind | Tic Tech Toe '26
"""

import json
import os
import sys
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# ============================================================
# 1. SYSTEM PROMPT (READY TO USE)
# ============================================================

SYSTEM_PROMPT = """You are FlowMind AI, a workflow automation engine.

Your ONLY job: convert the user's natural language instruction into a JSON list of tool steps.

AVAILABLE TOOLS (use ONLY these):
1. send_slack_message(message: string)   — sends a message to Slack
2. create_github_issue(title: string)    — creates a GitHub issue
3. update_google_sheet(data: string)     — adds/updates a row in Google Sheets

RULES:
- Return ONLY valid JSON. No explanations. No markdown. No extra text. No code fences.
- Use ONLY the tools listed above. If the user asks for a tool that doesn't exist, skip it.
- Each step must have exactly two fields: "tool" (string) and "input" (string).
- "input" must be a short, clear string describing what to pass to the tool.
- Order steps logically based on the user's intent.
- If the user's input is vague, interpret it reasonably and generate the best possible steps.
- If no valid tool matches the request, return: {"steps": []}
- Do NOT wrap output in ```json``` or any markdown.

OUTPUT FORMAT (strict):
{"steps": [{"tool": "<tool_name>", "input": "<string>"}]}"""


# ============================================================
# 2. CORE FUNCTIONS
# ============================================================

def generate_steps(user_prompt: str) -> dict:
    """
    Takes a natural language workflow instruction and returns
    structured JSON steps by calling the Groq LLM.

    Args:
        user_prompt: Natural language string from the user.

    Returns:
        dict with "steps" key containing list of tool steps.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[ERROR] GROQ_API_KEY not set in .env file!")
        return {"steps": []}

    client = Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",   # Free, fast, reliable
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=512,
            response_format={"type": "json_object"}  # Forces JSON output
        )
        raw_output = response.choices[0].message.content
        return parse_llm_output(raw_output)

    except Exception as e:
        print(f"[ERROR] Groq API call failed: {e}")
        return {"steps": []}


def parse_llm_output(raw: str) -> dict:
    """
    Safely parses LLM output string into validated JSON.

    Args:
        raw: Raw string from the LLM response.

    Returns:
        dict with "steps" list. Returns {"steps": []} on any error.
    """
    # Strip markdown fences if LLM wraps output (safety net)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"[ERROR] LLM returned invalid JSON:\n{raw}")
        return {"steps": []}

    # Validate structure
    if "steps" not in data or not isinstance(data["steps"], list):
        print(f"[ERROR] Missing or invalid 'steps' key in LLM output")
        return {"steps": []}

    valid_tools = {
        "send_slack_message",
        "create_github_issue",
        "update_google_sheet"
    }

    validated_steps = []
    for step in data["steps"]:
        tool = step.get("tool", "")
        inp = step.get("input", "")

        if tool not in valid_tools:
            print(f"[WARN] Skipping unknown tool: {tool}")
            continue

        if not isinstance(inp, str) or not inp.strip():
            print(f"[WARN] Skipping step with empty input for tool: {tool}")
            continue

        validated_steps.append({"tool": tool, "input": inp})

    return {"steps": validated_steps}


# ============================================================
# 3. TEST CASES
# ============================================================

TEST_CASES = [
    {
        "input": "When a bug is reported, create a GitHub issue and notify the team on Slack",
        "expected_tools": ["create_github_issue", "send_slack_message"]
    },
    {
        "input": "Log today's sales data in the spreadsheet and send a summary to Slack",
        "expected_tools": ["update_google_sheet", "send_slack_message"]
    },
    {
        "input": "Create a GitHub issue for login page crash, update the bug tracker sheet, and alert the dev channel",
        "expected_tools": ["create_github_issue", "update_google_sheet", "send_slack_message"]
    },
    {
        "input": "Send a Slack message saying deployment is complete",
        "expected_tools": ["send_slack_message"]
    },
    {
        "input": "Play some music",
        "expected_tools": []
    }
]


def run_tests_mock():
    """Run test cases using mock LLM responses (no API key needed)."""
    print("\n" + "=" * 60)
    print("  MOCK TEST CASES (no API key needed)")
    print("=" * 60)

    mock_responses = [
        '{"steps": [{"tool": "create_github_issue", "input": "Bug reported"}, {"tool": "send_slack_message", "input": "A bug has been reported. GitHub issue created."}]}',
        '{"steps": [{"tool": "update_google_sheet", "input": "Today\'s sales data"}, {"tool": "send_slack_message", "input": "Sales data has been logged in the spreadsheet"}]}',
        '{"steps": [{"tool": "create_github_issue", "input": "Login page crash"}, {"tool": "update_google_sheet", "input": "Login page crash - bug logged"}, {"tool": "send_slack_message", "input": "Alert: Login page crash issue created and logged"}]}',
        '{"steps": [{"tool": "send_slack_message", "input": "Deployment is complete"}]}',
        '{"steps": []}',
    ]

    passed = 0
    for i, (test, mock_resp) in enumerate(zip(TEST_CASES, mock_responses)):
        result = parse_llm_output(mock_resp)
        actual_tools = [s["tool"] for s in result["steps"]]
        match = test["expected_tools"] == actual_tools

        status = "PASS" if match else "FAIL"
        if match:
            passed += 1

        print(f"\nTest {i+1}: {status}")
        print(f"  Input:    {test['input']}")
        print(f"  Expected: {test['expected_tools']}")
        print(f"  Got:      {actual_tools}")

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{len(TEST_CASES)} passed")
    print(f"{'='*60}\n")


def run_tests_live():
    """Run test cases against the real Groq API."""
    print("\n" + "=" * 60)
    print("  LIVE TEST CASES (calling Groq API)")
    print("=" * 60)

    if not os.getenv("GROQ_API_KEY"):
        print("  GROQ_API_KEY not set in .env -- skipping live tests")
        return

    passed = 0
    for i, test in enumerate(TEST_CASES):
        try:
            result = generate_steps(test["input"])
            actual_tools = [s["tool"] for s in result["steps"]]
            match = test["expected_tools"] == actual_tools

            status = "PASS" if match else "CLOSE" if len(test["expected_tools"]) == len(actual_tools) else "FAIL"
            if match:
                passed += 1

            print(f"\nTest {i+1}: {status}")
            print(f"  Input:    {test['input']}")
            print(f"  Expected: {test['expected_tools']}")
            print(f"  Got:      {actual_tools}")
            print(f"  Output:   {json.dumps(result, indent=2)}")

        except Exception as e:
            print(f"\nTest {i+1}: ERROR -- {e}")

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{len(TEST_CASES)} passed")
    print(f"{'='*60}\n")


# ============================================================
# 4. INTERACTIVE MODE
# ============================================================

def interactive():
    """Run the agent in interactive CLI mode."""
    print("\n" + "=" * 60)
    print("  FlowMind AI -- LLM Agent Brain (Groq)")
    print("  Type a workflow instruction. Type 'quit' to exit.")
    print("=" * 60)

    if not os.getenv("GROQ_API_KEY"):
        print("\n  GROQ_API_KEY not set! Add it to .env file.")
        print("  Running in MOCK mode (test cases only).\n")
        run_tests_mock()
        return

    while True:
        user_input = input("\n>>> ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("Done.")
            break
        if not user_input:
            continue

        print("Generating steps...")
        result = generate_steps(user_input)
        print(json.dumps(result, indent=2))


# ============================================================
# 5. ENTRY POINT
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            run_tests_mock()
        elif sys.argv[1] == "--test-live":
            run_tests_live()
        elif sys.argv[1] == "--prompt":
            print(SYSTEM_PROMPT)
        else:
            result = generate_steps(" ".join(sys.argv[1:]))
            print(json.dumps(result, indent=2))
    else:
        interactive()
