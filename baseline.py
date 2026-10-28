"""Part A (ungrounded baseline) and Task B3 (single grounded RAG agent)."""
import argparse
import json

import config
from kb import KnowledgeBase

BASELINE_SYSTEM = (
    "You are a helpful customer-support agent for the MycoVault MV-200 "
    "mushroom growing cabinet."
)

RAG_SYSTEM = (
    "You are a customer-support agent for the MycoVault MV-200 mushroom growing cabinet. "
    "Answer ONLY from the manual excerpts given between <context> and </context>. "
    "Cite the section names you used as [Section: <name>]. "
    "Do not add facts, numbers or advice that are not in the context. "
    "If the context does not contain the answer, reply exactly: NOT_IN_MANUAL"
)


def ask_baseline(question: str) -> str:
    msgs = [
        {"role": "system", "content": BASELINE_SYSTEM},
        {"role": "user", "content": question},
    ]
    return config.chat(msgs, temperature=0.2)["message"]["content"]


_KB = None


def get_kb():
    global _KB
    if _KB is None or _KB.chunk_size != config.CHUNK_SIZE:
        _KB = KnowledgeBase()
    return _KB


def ask_rag(question: str, return_chunks=False):
    chunks = get_kb().search(question, k=config.RAG_K)
    context = "\n\n".join(f"[Section: {c['section']}]\n{c['text']}" for c in chunks)
    msgs = [
        {"role": "system", "content": RAG_SYSTEM},
        {"role": "user", "content": f"<context>\n{context}\n</context>\n\nQuestion: {question}"},
    ]
    answer = config.chat(msgs, temperature=0.0)["message"]["content"]
    return (answer, chunks) if return_chunks else answer


def run_first_ten(part):
    questions = json.loads(config.TEST_SET_PATH.read_text(encoding="utf-8"))[:10]
    fn = ask_baseline if part == "A" else ask_rag
    results = []
    for q in questions:
        answer = fn(q["question"])
        print(f"\nQ{q['id']}: {q['question']}\n{answer}")
        results.append({"id": q["id"], "question": q["question"], "answer": answer})
    config.RESULTS_DIR.mkdir(exist_ok=True)
    out = config.RESULTS_DIR / ("partA_baseline.json" if part == "A" else "partB3_rag.json")
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--part", choices=["A", "B3"], required=True)
    args = parser.parse_args()
    run_first_ten(args.part)
