# Lab 4 — Multi-agent MycoVault MV-200 helpdesk

Local Ollama helpdesk grounded in `data/mycovault_manual.md`.

| Part | What |
|------|------|
| A | Ungrounded baseline (`baseline.py --part A`) |
| B | Knowledge base + single RAG agent (`kb.py --demo`, `baseline.py --part B3`) |
| C | Multi-agent system + CLI (`coordinator.py [--trace]`) |
| D | Tools / escalation demos (`coordinator.py --demo-d1`) |
| E | Evaluation + Verifier on/off ablation (`evaluate.py`) |

## Setup

```powershell
cd "E:\MasterSem1\An2Sem1\MultiAgentic AI\lab4_helpdesk"
python -m pip install -r requirements.txt
ollama pull llama3.1:8b
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

## Run

```powershell
$env:PYTHONIOENCODING = "utf-8"

python kb.py --demo
python baseline.py --part A
python baseline.py --part B3
python coordinator.py --trace
python coordinator.py --demo-d1
python evaluate.py --tau-sweep
python evaluate.py
python evaluate.py --ablation verifier
```

Default chat model: `llama3.1:8b`. Override with `$env:MV_CHAT_MODEL` or `python coordinator.py --model ...`.

E2 ablation is **Verifier on vs off** (same model — no VRAM swap). Verifier ON reuses the E1 multi-agent results when `results/eval_llama3.1-8b.json` exists.

## Layout

- `kb.py` — chunking, embeddings, SHA-256 cache
- `agents.py` — Triage, Retriever, Specialist, Verifier, Escalation
- `tools.py` — `lookup_error_code`, `create_ticket`, Section 9 guardrails
- `coordinator.py` — blackboard, control policy, CLI
- `evaluate.py` — metrics for baseline / RAG / multi-agent + verifier ablation
- `results/` — traces, eval tables, `ablation_verifier.md`
- `REPORT.md` — write-up for submission
