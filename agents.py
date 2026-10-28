"""Part C - message protocol and the helpdesk agents."""
import json
import re
import time
from dataclasses import dataclass, field

import config
import tools

INTENTS = {"troubleshooting", "cultivation", "maintenance", "safety", "warranty", "off_topic"}
URGENCIES = {"low", "medium", "high"}


@dataclass
class Message:
    sender: str
    receiver: str
    performative: str  # inform | request | propose | reject | escalate
    content: dict
    ts: float = field(default_factory=time.time)


def parse_json(text, default):
    """Small models sometimes wrap JSON in prose; recover the first object if possible."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r"\{.*\}", text or "", re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return dict(default)


class Agent:
    name = "agent"
    system_prompt = ""
    temperature = 0.0

    def llm(self, user_content, json_mode=False, system=None, default=None):
        r = config.chat(
            [{"role": "system", "content": system or self.system_prompt},
             {"role": "user", "content": user_content}],
            format="json" if json_mode else None,
            temperature=self.temperature,
        )
        out = r["message"]["content"]
        return parse_json(out, default or {}) if json_mode else out

    def handle(self, msg: Message) -> Message:
        raise NotImplementedError


class TriageAgent(Agent):
    name = "triage"
    system_prompt = (
        "You classify customer messages for the MycoVault MV-200 helpdesk. "
        "Return ONLY JSON with keys: intent (one of troubleshooting, cultivation, "
        "maintenance, safety, warranty, off_topic), urgency (low|medium|high), "
        "error_code (e.g. 'E07' or null), species (or null), "
        "standalone_question (the question rewritten to be self-contained). "
        "Use the conversation history to resolve follow-ups such as 'and how long does that take?'. "
        "Questions about the device, its errors, growing mushrooms in it, cleaning, firmware or "
        "warranty are never off_topic. Smoke, burning smell or water leaks are safety with high urgency."
    )

    def handle(self, msg):
        result = self.llm(json.dumps(msg.content), json_mode=True)
        question = msg.content["question"]
        # Guardrails on the classifier's output: enforce the schema.
        if result.get("intent") not in INTENTS:
            result["intent"] = "troubleshooting"
        if result.get("urgency") not in URGENCIES:
            result["urgency"] = "medium"
        found = re.search(r"\bE\d{2}\b", question.upper())
        code = str(result.get("error_code") or "").upper()
        result["error_code"] = code if re.fullmatch(r"E\d{2}", code) else (found.group(0) if found else None)
        if not result.get("standalone_question"):
            result["standalone_question"] = question
        result["question"] = question
        return Message(self.name, "coordinator", "inform", result)


class RetrieverAgent(Agent):
    name = "retriever"
    system_prompt = (
        "You write search queries for the MycoVault MV-200 manual. Given a customer question, "
        "return ONLY JSON {\"queries\": [..]} with 2 or 3 short alternative search queries that use "
        "the vocabulary a technical manual would use (component names, error codes, procedures)."
    )

    def __init__(self, kb, tau=None, k=None, expand=True):
        self.kb = kb
        self.tau = config.TAU if tau is None else tau
        self.k = k or config.RETRIEVER_K
        self.expand = expand

    def handle(self, msg):
        question = msg.content.get("standalone_question") or msg.content["question"]
        queries = [question]
        if self.expand:
            extra = self.llm(question, json_mode=True, default={"queries": []}).get("queries", [])
            queries += [q for q in extra if isinstance(q, str) and q.strip()][:3]
        if msg.content.get("error_code"):
            queries.append(f"error code {msg.content['error_code']}")

        best = {}
        for q in queries:
            for hit in self.kb.search(q, k=4):
                if hit["id"] not in best or hit["score"] > best[hit["id"]]["score"]:
                    best[hit["id"]] = hit
        kept = sorted((h for h in best.values() if h["score"] >= self.tau),
                      key=lambda h: -h["score"])[: self.k]
        return Message(self.name, "coordinator", "inform", {"queries": queries, "chunks": kept})


SPECIALIST_BASE = (
    "You are a MycoVault MV-200 support specialist. Write the reply to the customer using ONLY "
    "the manual excerpts in CONTEXT. Cite every section you use as [Section: <name>]. "
    "Never invent numbers, part numbers, durations or button combinations: copy them exactly from "
    "the context. If the context does not answer the question, reply exactly NOT_IN_MANUAL. "
    "Keep the answer short (at most 6 sentences). "
)

SPECIALIST_PROMPTS = {
    "troubleshooting": SPECIALIST_BASE + (
        "This is a troubleshooting request: state what the error or symptom means, then give the "
        "official steps as a numbered list in the order the manual gives them."),
    "safety": SPECIALIST_BASE + (
        "This is a safety request: start with the most urgent protective action from the manual "
        "(for example unplugging the unit or wearing an FFP2 mask), then the remaining steps. "
        "Always include every safety warning the context gives for this situation."),
    "maintenance": SPECIALIST_BASE + (
        "This is a maintenance request: give intervals, products and step-by-step procedure, and "
        "mention anything the manual says must never be used."),
    "cultivation": SPECIALIST_BASE + (
        "This is a cultivation request: give the exact profile values for the species from the table."),
    "warranty": SPECIALIST_BASE + (
        "This is a warranty request: state the warranty rule and what voids it, exactly as written."),
}


class SpecialistAgent(Agent):
    name = "specialist"
    temperature = 0.1

    def handle(self, msg):
        c = msg.content
        system = SPECIALIST_PROMPTS.get(c.get("intent"), SPECIALIST_BASE)
        user = f"CONTEXT:\n{c['context']}\n\nCUSTOMER QUESTION:\n{c.get('standalone_question') or c['question']}"
        if c.get("feedback"):
            user += ("\n\nA fact checker rejected your previous draft. Fix these problems and remove "
                     f"anything not supported by the context:\n{c['feedback']}")
        draft = self.llm(user, system=system).strip()
        return Message(self.name, "coordinator", "propose", {"draft": draft})


class VerifierAgent(Agent):
    name = "verifier"
    system_prompt = (
        "You are a strict fact checker. You receive CONTEXT from the official "
        "manual and a DRAFT answer. For each factual claim in the draft decide if "
        "it is supported by the context. Return ONLY JSON: "
        "{\"supported\": true|false, \"unsupported_claims\": [...], "
        "\"missing_safety_warning\": true|false, \"feedback\": \"...\"}"
    )

    def handle(self, msg):
        prompt = ("CONTEXT:\n" + msg.content["context"] +
                  "\n\nDRAFT:\n" + msg.content["draft"])
        v = self.llm(prompt, json_mode=True,
                     default={"supported": False, "unsupported_claims": [],
                              "missing_safety_warning": False, "feedback": "unparseable verdict"})
        v["supported"] = v.get("supported") is True or str(v.get("supported")).lower() == "true"
        v["missing_safety_warning"] = (v.get("missing_safety_warning") is True
                                       or str(v.get("missing_safety_warning")).lower() == "true")
        v.setdefault("unsupported_claims", [])
        v.setdefault("feedback", "")
        return Message(self.name, "coordinator", "inform" if v["supported"] else "reject", v)


ESCALATION_POLICY = """You are the escalation agent of the MycoVault MV-200 helpdesk.
You decide whether a human service technician is needed, following Section 9 of the manual.
A ticket is REQUIRED only in these cases:
1. E19 (Peltier module overheat) occurs twice within 24 hours -> priority medium.
2. E23 (firmware integrity error) does not clear within 10 minutes -> priority high.
3. E07 (CO2 sensor drift) reappears within 7 days after a recalibration -> priority medium.
4. Any smell of burning, smoke, or water leaking under the unit -> priority high;
   the customer must unplug the unit immediately.
In every other case do NOT create a ticket; a single error that the manual's action fixes is not a reason.
You may call lookup_error_code to check what a code means.
If a ticket is required, call create_ticket exactly once with a one-sentence summary, the priority
above and the error code (empty string if none).
When you are done, reply with one short sentence explaining your decision."""


class EscalationAgent(Agent):
    name = "escalation"
    MAX_TOOL_ROUNDS = 3

    def handle(self, msg):
        c = msg.content
        case_text = " ".join(str(x) for x in (c.get("question"), c.get("standalone_question")) if x)
        messages = [{"role": "system", "content": ESCALATION_POLICY},
                    {"role": "user", "content": json.dumps(
                        {k: c.get(k) for k in ("question", "standalone_question", "intent",
                                               "urgency", "error_code", "reason")})}]
        calls_log, ticket = [], None
        for _ in range(self.MAX_TOOL_ROUNDS):
            r = config.chat(messages, tools=list(tools.TOOLS.values()), temperature=0.0)
            tool_calls = r["message"].get("tool_calls") or []
            if not tool_calls:
                break
            messages.append(r["message"])
            for call in tool_calls:
                name = call["function"]["name"]
                args = call["function"]["arguments"]
                if name == "create_ticket" and ticket is not None:
                    allowed, args, why = False, args, "ticket already created for this case"
                else:
                    allowed, args, why = tools.validate_tool_call(name, args, case_text, c.get("error_code"))
                if allowed:
                    result = tools.TOOLS[name](**args)
                    if name == "create_ticket":
                        ticket = {**args, "ticket_id": json.loads(result)["ticket_id"]}
                else:
                    result = json.dumps({"error": f"call rejected by guardrail: {why}"})
                calls_log.append({"tool": name, "arguments": args, "allowed": allowed, "guardrail": why})
                messages.append({"role": "tool", "content": result, "tool_name": name})
        note = (r["message"].get("content") or "").strip()
        performative = "escalate" if ticket else "inform"
        return Message(self.name, "coordinator", performative,
                       {"ticket": ticket, "tool_calls": calls_log, "note": note})
