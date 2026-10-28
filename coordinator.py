"""Part C/D - coordinator (control policy), interactive CLI and the D1 demo traces."""
import argparse
import json

import config
from agents import (EscalationAgent, Message, RetrieverAgent, SpecialistAgent,
                    TriageAgent, VerifierAgent)
from kb import KnowledgeBase

SUPPORT_HOURS = "Customer support hours: Monday–Friday 09:00–17:00 CET."
ESCALATION_INTENTS = {"troubleshooting", "safety", "warranty"}


class Coordinator:
    MAX_REVISIONS = 2

    def __init__(self, kb, use_verifier=True, query_expansion=True):
        self.triage, self.retriever = TriageAgent(), RetrieverAgent(kb, expand=query_expansion)
        self.specialist, self.verifier = SpecialistAgent(), VerifierAgent()
        self.escalation = EscalationAgent()
        self.use_verifier = use_verifier
        self.blackboard: list[Message] = []
        self.turn_start = 0
        self.last = {}

    def post(self, m):
        self.blackboard.append(m)
        return m

    def answer(self, question, history=()):
        self.turn_start = len(self.blackboard)
        self.last = {"chunks": [], "ticket": None, "outcome": None}
        t = self.post(self.triage.handle(Message("user", "triage", "request",
                      {"question": question, "history": list(history)}))).content
        if t["intent"] == "off_topic":
            self.last["outcome"] = "off_topic"
            return self.final("I can only help with the MycoVault MV-200.")

        chunks = self.post(self.retriever.handle(Message("coordinator",
                           "retriever", "request", t))).content["chunks"]
        self.last["chunks"] = chunks
        if not chunks:
            return self.escalate(t, reason="not_in_manual")

        context = "\n\n".join(f"[Section: {c['section']}]\n{c['text']}" for c in chunks)
        feedback = ""
        for attempt in range(self.MAX_REVISIONS + 1):
            draft = self.post(self.specialist.handle(Message("coordinator",
                              "specialist", "request", {**t, "context": context,
                                                        "feedback": feedback}))).content["draft"]
            if "NOT_IN_MANUAL" in draft:
                return self.escalate(t, reason="not_in_manual")
            if not self.use_verifier:
                return self.maybe_escalate(t, draft)
            v = self.post(self.verifier.handle(Message("coordinator",
                          "verifier", "request", {"context": context,
                                                  "draft": draft}))).content
            if v["supported"] and not v["missing_safety_warning"]:
                return self.maybe_escalate(t, draft)
            feedback = v["feedback"] or "; ".join(map(str, v["unsupported_claims"]))
        return self.escalate(t, reason="verification_failed")

    def run_escalation(self, t, reason, draft=None):
        m = self.post(self.escalation.handle(Message("coordinator", "escalation", "request",
                      {**t, "reason": reason, "draft": draft})))
        self.last["ticket"] = m.content["ticket"]
        return m.content["ticket"]

    def escalate(self, t, reason):
        """No verified answer: hand over to a human, with a ticket only if Section 9 requires one."""
        self.last["outcome"] = reason
        ticket = self.run_escalation(t, reason)
        if reason == "not_in_manual":
            reply = "This topic is not covered by the MycoVault MV-200 manual, so I cannot advise on it."
        else:
            reply = ("I could not produce an answer that I can fully verify against the manual. "
                     "Please contact a human support agent.")
        if ticket:
            reply += ticket_sentence(ticket)
        elif reason != "not_in_manual":
            reply += " " + SUPPORT_HOURS
        return self.final(reply)

    def maybe_escalate(self, t, draft):
        """Verified answer: add a technician ticket on top when the case needs one."""
        self.last["outcome"] = "answered"
        if t["intent"] in ESCALATION_INTENTS or t["urgency"] == "high" or t.get("error_code"):
            ticket = self.run_escalation(t, "post_answer_check", draft)
            if ticket:
                draft += ticket_sentence(ticket)
        return self.final(draft)

    def final(self, reply):
        self.post(Message("coordinator", "user", "inform", {"reply": reply}))
        return reply

    def trace(self, start=None):
        return format_trace(self.blackboard[self.turn_start if start is None else start:])


def ticket_sentence(ticket):
    return (f"\n\nI have opened service ticket {ticket['ticket_id']} "
            f"({ticket['priority']} priority); a technician will contact you.")


def short(value, limit=220):
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    s = s.replace("\n", " ")
    return s if len(s) <= limit else s[:limit] + " ..."


def format_trace(messages):
    lines = []
    for m in messages:
        lines.append(f"[{m.sender} -> {m.receiver}] {m.performative}")
        content = dict(m.content)
        if "chunks" in content:
            content["chunks"] = [f"{c['section']} (#{c['id']}, {c['score']:.2f})" for c in content["chunks"]]
        for k, v in content.items():
            if k in ("context", "history"):
                continue
            lines.append(f"    {k}: {short(v)}")
    return "\n".join(lines)


def cli(trace):
    coord = Coordinator(KnowledgeBase())
    history = []
    print(f"MycoVault MV-200 helpdesk ({config.CHAT_MODEL}). Empty line to quit.")
    while True:
        try:
            q = input("\nYou: ").strip()
        except EOFError:
            break
        if not q:
            break
        reply = coord.answer(q, history)
        if trace:
            print("\n--- trace ---\n" + coord.trace() + "\n-------------")
        print(f"\nHelpdesk: {reply}")
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": reply}]


def demo_d1():
    """Task D1: one run without ticket, one with a medium and one with a high-priority ticket."""
    cases = [("No ticket", "My display shows E07. What should I do?"),
             ("Medium-priority ticket", "I got E19 this morning and again now."),
             ("High-priority ticket", "There is water under the cabinet and a burning smell!")]
    coord = Coordinator(KnowledgeBase())
    parts = [f"# D1 demo traces\n\nModel: `{config.CHAT_MODEL}`\n"]
    for title, q in cases:
        reply = coord.answer(q)
        ticket = coord.last["ticket"]
        print(f"\n=== {title} ===\nQ: {q}\n{coord.trace()}\n\nReply: {reply}")
        parts.append(f"## {title}\n\n**Question:** {q}\n\n```\n{coord.trace()}\n```\n\n"
                     f"**Final reply:**\n\n{reply}\n\n**Ticket:** {json.dumps(ticket) if ticket else 'none'}\n")
    config.RESULTS_DIR.mkdir(exist_ok=True)
    out = config.RESULTS_DIR / "d1_traces.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MycoVault MV-200 multi-agent helpdesk")
    parser.add_argument("--trace", action="store_true", help="print the blackboard after each answer")
    parser.add_argument("--model", help="chat model, e.g. llama3.1:8b or qwen2.5:3b")
    parser.add_argument("--demo-d1", action="store_true", help="write the three Task D1 traces")
    args = parser.parse_args()
    if args.model:
        config.CHAT_MODEL = args.model
    if args.demo_d1:
        demo_d1()
    else:
        cli(args.trace)
