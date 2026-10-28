"""Part E - evaluation of baseline, single RAG agent and the multi-agent system (E1),
plus Verifier on/off ablation (E2) and a tau sweep for the Retriever."""
import argparse
import json
import re
import time

import config
from baseline import ask_baseline, ask_rag
from coordinator import Coordinator
from kb import KnowledgeBase

JUDGE_MODEL = "llama3.1:8b"  # fixed so ablation conditions are graded the same way

JUDGE_PROMPT = (
    "You are grading answers of a customer helpdesk against an answer key. "
    "You receive a QUESTION, a numbered list of EXPECTED FACTS and the ANSWER. "
    "For each expected fact decide whether the answer states it with the same meaning; "
    "numbers, units and button names must match exactly, paraphrasing is fine. "
    "Return ONLY JSON {\"results\": [true|false, ...]} with one entry per expected fact, in order."
)

REFUSAL_RE = re.compile(
    r"not_in_manual|not covered|can only help|cannot advise|can't advise|not able to help|"
    r"unable to help|outside (the )?scope|no information|does not (cover|mention|contain)|"
    r"doesn't (cover|mention)|i don't know|i do not know|not mentioned", re.I)


def normalise(text):
    t = (text or "").lower()
    t = t.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("°", "")
    t = re.sub(r"\s*\+\s*", "+", t)
    t = re.sub(r"(\d)\s+%", r"\1%", t)
    t = re.sub(r"(\d)\s*-\s*(\d)", r"\1-\2", t)
    t = re.sub(r"\*+", "", t)
    return re.sub(r"\s+", " ", t)


def string_match(answer, facts):
    a = normalise(answer)
    return [any(normalise(v) in a for v in variants) for variants in facts]


def judge(question, answer, facts):
    listed = "\n".join(f"{i + 1}. {' / '.join(v)}" for i, v in enumerate(facts))
    previous = config.LLM_CALLS
    r = config.chat([{"role": "system", "content": JUDGE_PROMPT},
                     {"role": "user", "content": f"QUESTION: {question}\n\nEXPECTED FACTS:\n{listed}\n\nANSWER:\n{answer}"}],
                    model=JUDGE_MODEL, format="json")
    config.LLM_CALLS = previous  # grading calls are not part of the system's cost
    try:
        res = json.loads(r["message"]["content"]).get("results", [])
    except (json.JSONDecodeError, AttributeError):
        res = []
    res = [x is True or str(x).lower() == "true" for x in res][: len(facts)]
    return res + [False] * (len(facts) - len(res))


def is_refusal(answer):
    return bool(REFUSAL_RE.search(answer or ""))


def run_question(system, q, coord):
    config.LLM_CALLS = 0
    start = time.perf_counter()
    chunks, ticket, trace = [], None, None
    if system == "baseline":
        answer = ask_baseline(q["question"])
    elif system == "rag":
        answer, chunks = ask_rag(q["question"], return_chunks=True)
    else:
        answer = coord.answer(q["question"])
        chunks, ticket, trace = coord.last["chunks"], coord.last["ticket"], coord.trace()
    return {
        "id": q["id"], "question": q["question"], "answer": answer,
        "seconds": time.perf_counter() - start, "llm_calls": config.LLM_CALLS,
        "retrieved_sections": [c["section"] for c in chunks],
        "ticket": ticket, "trace": trace,
    }


def score(rows, questions, system):
    by_id = {q["id"]: q for q in questions}
    fact_s, fact_j, refusals, hits, false_refusals = [], [], [], [], 0
    tp = fp = fn = prio_ok = 0
    for row in rows:
        q = by_id[row["id"]]
        if q["expected_facts"]:
            row["facts_string"] = string_match(row["answer"], q["expected_facts"])
            row["facts_judge"] = judge(q["question"], row["answer"], q["expected_facts"])
            fact_s.append(sum(row["facts_string"]) / len(q["expected_facts"]))
            fact_j.append(sum(row["facts_judge"]) / len(q["expected_facts"]))
            false_refusals += is_refusal(row["answer"]) and not any(row["facts_string"])
        if q["out_of_manual"]:
            row["refused"] = is_refusal(row["answer"])
            refusals.append(row["refused"])
        if q["gold_sections"] and system != "baseline":
            row["hit"] = any(s in q["gold_sections"] for s in row["retrieved_sections"])
            hits.append(row["hit"])
        predicted, gold = row["ticket"] is not None, q["escalation"]
        tp += predicted and gold
        fp += predicted and not gold
        fn += gold and not predicted
        prio_ok += predicted and gold and row["ticket"]["priority"] == q["priority"]

    mean = lambda xs: sum(xs) / len(xs) if xs else None
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else 0.0
    return {
        "fact_accuracy_string": mean(fact_s),
        "fact_accuracy_judge": mean(fact_j),
        "refusal_correctness": mean(refusals),
        "false_refusals": false_refusals,
        "escalation_precision": precision,
        "escalation_recall": recall,
        "escalation_f1": f1 if system == "mas" else None,
        "priority_correct": f"{prio_ok}/{tp}" if system == "mas" else None,
        "hit_at_k": mean(hits),
        "mean_seconds": mean([r["seconds"] for r in rows]),
        "mean_llm_calls": mean([r["llm_calls"] for r in rows]),
    }


def evaluate_system(system, questions, model, use_verifier=True):
    config.CHAT_MODEL = model
    coord = (Coordinator(KnowledgeBase(), use_verifier=use_verifier)
             if system == "mas" else None)
    tag = system if system != "mas" else f"mas verifier={'on' if use_verifier else 'off'}"
    rows = []
    for q in questions:
        row = run_question(system, q, coord)
        rows.append(row)
        print(f"  [{tag} {model}] Q{q['id']:>2} {row['seconds']:5.1f}s "
              f"{row['llm_calls']} calls ticket={row['ticket']['priority'] if row['ticket'] else '-'}")
    return rows, score(rows, questions, system)


def slug(model):
    return model.replace(":", "-").replace("/", "-")


def fmt(v, pct=False):
    if v is None:
        return "n/a"
    if isinstance(v, str):
        return v
    return f"{v * 100:.0f} %" if pct else f"{v:.2f}"


METRICS = [("Fact accuracy (string match)", "fact_accuracy_string", True),
           ("Fact accuracy (LLM judge)", "fact_accuracy_judge", True),
           ("Refusal correctness (Q18, Q20)", "refusal_correctness", True),
           ("False refusals on in-manual questions", "false_refusals", False),
           ("Escalation precision", "escalation_precision", False),
           ("Escalation recall", "escalation_recall", False),
           ("Escalation F1", "escalation_f1", False),
           ("Ticket priority correct", "priority_correct", False),
           ("Retrieval hit@k", "hit_at_k", True),
           ("Mean latency (s / question)", "mean_seconds", False),
           ("Mean LLM calls / question", "mean_llm_calls", False)]


def table(columns):
    head = "| Metric | " + " | ".join(name for name, _ in columns) + " |"
    sep = "|---|" + "---|" * len(columns)
    lines = [head, sep]
    for label, key, pct in METRICS:
        cells = [str(s[key]) if key == "false_refusals" else fmt(s[key], pct) for _, s in columns]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def per_question_table(results):
    systems = list(results)
    lines = ["| Q | " + " | ".join(f"{s} facts" for s in systems) + " | MAS ticket | MAS retrieved gold |",
             "|---|" + "---|" * (len(systems) + 2)]
    for i, row in enumerate(results[systems[0]]["rows"]):
        cells = []
        for s in systems:
            r = results[s]["rows"][i]
            if "facts_string" in r:
                cells.append(f"{sum(r['facts_string'])}/{len(r['facts_string'])}")
            else:
                cells.append("refused" if r.get("refused") else "answered")
        mas = results.get("mas", {}).get("rows", [{}] * (i + 1))[i]
        ticket = mas.get("ticket")
        cells.append(ticket["priority"] if ticket else "-")
        cells.append({True: "yes", False: "no"}.get(mas.get("hit"), "n/a"))
        lines.append(f"| {row['id']} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def fresh_tickets_file(name):
    config.RESULTS_DIR.mkdir(exist_ok=True)
    config.TICKETS_PATH = config.RESULTS_DIR / name
    config.TICKETS_PATH.write_text("", encoding="utf-8")


def run_e1(model):
    questions = json.loads(config.TEST_SET_PATH.read_text(encoding="utf-8"))
    fresh_tickets_file(f"tickets_eval_{slug(model)}.jsonl")
    results = {}
    for system in ("baseline", "rag", "mas"):
        rows, summary = evaluate_system(system, questions, model)
        results[system] = {"summary": summary, "rows": rows}
    out = config.RESULTS_DIR / f"eval_{slug(model)}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    md = (f"# E1 evaluation ({model}, 20 questions)\n\n"
          f"Judge model: `{JUDGE_MODEL}`. Tau = {config.TAU}, chunk size = {config.CHUNK_SIZE}. "
          "Escalation metrics are n/a for baseline and RAG because they have no ticket tool. "
          "Hit@k uses k = 4 for RAG and up to 5 chunks above tau for the multi-agent system.\n\n"
          + table([("Baseline", results["baseline"]["summary"]),
                   ("Single RAG (B3)", results["rag"]["summary"]),
                   ("Multi-agent", results["mas"]["summary"])])
          + "\n\n## Per question\n\n" + per_question_table(results) + "\n")
    (config.RESULTS_DIR / "eval_table.md").write_text(md, encoding="utf-8")
    print("\n" + md)


def run_ablation_verifier(model):
    """E2: Verifier on vs off. Same chat model (no VRAM swap).

    Reuses the E1 multi-agent results as 'verifier on' when available.
    """
    questions = json.loads(config.TEST_SET_PATH.read_text(encoding="utf-8"))
    details = {}

    e1_path = config.RESULTS_DIR / f"eval_{slug(model)}.json"
    if e1_path.exists():
        e1 = json.loads(e1_path.read_text(encoding="utf-8"))
        details["verifier_on"] = {
            "summary": e1["mas"]["summary"],
            "rows": e1["mas"]["rows"],
            "source": str(e1_path.name),
        }
        print(f"Reusing E1 multi-agent run as verifier ON ({e1_path.name})")
    else:
        fresh_tickets_file(f"tickets_ablation_verifier_on_{slug(model)}.jsonl")
        rows, summary = evaluate_system("mas", questions, model, use_verifier=True)
        details["verifier_on"] = {"summary": summary, "rows": rows, "source": "fresh"}

    fresh_tickets_file(f"tickets_ablation_verifier_off_{slug(model)}.jsonl")
    rows_off, summary_off = evaluate_system("mas", questions, model, use_verifier=False)
    details["verifier_off"] = {"summary": summary_off, "rows": rows_off, "source": "fresh"}

    out_json = config.RESULTS_DIR / "ablation_verifier.json"
    out_json.write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8")
    columns = [
        ("Verifier ON (E1 MAS)", details["verifier_on"]["summary"]),
        ("Verifier OFF", details["verifier_off"]["summary"]),
    ]
    md = (
        f"# E2 ablation: Verifier on vs off\n\n"
        f"Same chat model (`{model}`), same KB, prompts and judge (`{JUDGE_MODEL}`). "
        "Only whether the Verifier + revision loop runs changes — no second model is loaded "
        "(avoids VRAM swapping).\n\n"
        f"Verifier ON source: `{details['verifier_on'].get('source')}`.\n\n"
        + table(columns) + "\n"
    )
    out_md = config.RESULTS_DIR / "ablation_verifier.md"
    out_md.write_text(md, encoding="utf-8")
    print("\n" + md)


def run_tau_sweep():
    """Retrieval-only sweep (no query expansion) to pick tau."""
    questions = json.loads(config.TEST_SET_PATH.read_text(encoding="utf-8"))
    kb = KnowledgeBase()
    hits = {q["id"]: kb.search(q["question"], k=8) for q in questions}
    lines = ["| tau | hit@5 (in-manual) | mean chunks kept | out-of-manual questions with 0 chunks |",
             "|---|---|---|---|"]
    for tau in (0.40, 0.45, 0.50, 0.55, 0.60):
        hit, kept, empty = [], [], 0
        for q in questions:
            ok = [h for h in hits[q["id"]] if h["score"] >= tau][:5]
            kept.append(len(ok))
            if q["gold_sections"]:
                hit.append(any(h["section"] in q["gold_sections"] for h in ok))
            if q["out_of_manual"]:
                empty += not ok
        lines.append(f"| {tau:.2f} | {sum(hit)}/{len(hit)} | {sum(kept) / len(kept):.1f} | {empty}/2 |")
    top = "\n".join(f"- Q{q['id']}: top score {hits[q['id']][0]['score']:.3f}" for q in questions
                    if q["out_of_manual"])
    md = "# Tau sweep (retrieval only)\n\n" + "\n".join(lines) + "\n\nOut-of-manual questions:\n" + top + "\n"
    config.RESULTS_DIR.mkdir(exist_ok=True)
    (config.RESULTS_DIR / "tau_sweep.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=config.CHAT_MODEL)
    parser.add_argument("--ablation", choices=["verifier"],
                        help="E2: Verifier on vs off (same model, no VRAM swap)")
    parser.add_argument("--tau-sweep", action="store_true")
    args = parser.parse_args()
    if args.tau_sweep:
        run_tau_sweep()
    elif args.ablation == "verifier":
        run_ablation_verifier(args.model)
    else:
        run_e1(args.model)
