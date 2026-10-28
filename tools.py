"""Part D - functions exposed to the Escalation agent, plus their guardrails."""
import datetime
import json
import re
import uuid

import config

VALID_PRIORITIES = {"low", "medium", "high"}
ERROR_CODE_RE = re.compile(r"^E\d{2}$")


def load_error_table(path=config.MANUAL_PATH):
    """Parse the Markdown table of the 'Error Codes' section into {code: {meaning, action}}."""
    text = open(path, encoding="utf-8").read()
    section = re.search(r"^#{1,3} .*Error Codes.*?$(.*?)(?=^#{1,3} |\Z)", text, re.M | re.S)
    if not section:
        raise ValueError("No 'Error Codes' section found in the manual")
    table = {}
    for line in section.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and ERROR_CODE_RE.match(cells[0]):
            table[cells[0]] = {"code": cells[0], "meaning": cells[1], "action": cells[2]}
    return table


ERROR_TABLE = load_error_table()


def lookup_error_code(code: str) -> str:
    """Return the official meaning and action for a MycoVault error code.

    Args:
      code: Error code exactly as shown on the display, e.g. 'E07'.
    """
    return json.dumps(ERROR_TABLE.get(str(code).strip().upper(), {"error": "unknown code"}))


def create_ticket(summary: str, priority: str, error_code: str = "") -> str:
    """Open a ticket for a human service technician.

    Args:
      summary: One-sentence description of the customer's problem.
      priority: One of 'low', 'medium', 'high'.
      error_code: Related error code, if any.
    """
    tid = "MV-" + uuid.uuid4().hex[:6].upper()
    with open(config.TICKETS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": tid, "summary": summary, "priority": priority,
                            "error_code": error_code,
                            "created": datetime.datetime.now().isoformat()}) + "\n")
    return json.dumps({"ticket_id": tid})


TOOLS = {"lookup_error_code": lookup_error_code, "create_ticket": create_ticket}


def policy_check(text: str, error_code: str | None):
    """Rule-based reading of manual Section 9. Returns (ticket_required, priority, rule).

    Used only as a guardrail on the LLM's tool calls, never to create tickets by itself.
    """
    t = text.lower()
    code = (error_code or "").upper()
    codes = {c.upper() for c in re.findall(r"\be\d{2}\b", t)} | ({code} if code else set())

    if re.search(r"burn|smoke|leak|water (under|below|beneath)|under the (unit|cabinet)", t):
        return True, "high", "burning smell, smoke or water leak"
    if "E23" in codes:
        minutes = [int(m) for m in re.findall(r"(\d+)\s*(?:min|minute)", t)]
        hours = re.search(r"\d+\s*(?:h|hour)", t)
        if hours or any(m > 10 for m in minutes) or re.search(r"not clear|still|won't clear|does not clear", t):
            return True, "high", "E23 not cleared within 10 minutes"
    if "E19" in codes and re.search(r"twice|again|second time|two times|2 times|another", t):
        return True, "medium", "E19 twice within 24 hours"
    if "E07" in codes and re.search(r"again|back|reappear|return|recalibrat", t):
        days = [int(d) for d in re.findall(r"(\d+)\s*day", t)]
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
        days += [words[w] for w in re.findall(r"\b(one|two|three|four|five|six|seven) days?", t)]
        if not days or min(days) <= 7:
            return True, "medium", "E07 back within 7 days of recalibration"
    return False, None, None


def validate_tool_call(name, args, context_text, error_code):
    """Guardrail for one LLM tool call. Returns (allowed, cleaned_args, reason)."""
    if name not in TOOLS:
        return False, args, f"unknown tool '{name}'"
    if not isinstance(args, dict):
        return False, args, "arguments are not an object"

    if name == "lookup_error_code":
        code = str(args.get("code", "")).strip().upper()
        if not ERROR_CODE_RE.match(code):
            return False, args, f"invalid error code '{code}'"
        return True, {"code": code}, "ok"

    summary = str(args.get("summary", "")).strip()
    priority = str(args.get("priority", "")).strip().lower()
    code = str(args.get("error_code", "") or "").strip().upper()
    if not summary:
        return False, args, "empty summary"
    if priority not in VALID_PRIORITIES:
        return False, args, f"invalid priority '{priority}'"
    if code and not ERROR_CODE_RE.match(code):
        code = ""

    required, policy_priority, rule = policy_check(context_text, error_code or code)
    if not required:
        return False, args, "no Section 9 rule requires a technician"
    reason = f"matches rule: {rule}"
    if priority != policy_priority:
        reason += f" (priority corrected {priority} -> {policy_priority})"
        priority = policy_priority
    return True, {"summary": summary, "priority": priority, "error_code": code}, reason
