# E2 ablation: Verifier on vs off

Same chat model (`llama3.1:8b`), same KB, prompts and judge (`llama3.1:8b`). Only whether the Verifier + revision loop runs changes — no second model is loaded (avoids VRAM swapping).

Verifier ON source: `eval_llama3.1-8b.json`.

| Metric | Verifier ON (E1 MAS) | Verifier OFF |
|---|---|---|
| Fact accuracy (string match) | 83 % | 82 % |
| Fact accuracy (LLM judge) | 60 % | 63 % |
| Refusal correctness (Q18, Q20) | 100 % | 100 % |
| False refusals on in-manual questions | 1 | 0 |
| Escalation precision | 1.00 | 1.00 |
| Escalation recall | 0.50 | 0.50 |
| Escalation F1 | 0.67 | 0.67 |
| Ticket priority correct | 2/2 | 2/2 |
| Retrieval hit@k | 100 % | 100 % |
| Mean latency (s / question) | 4.00 | 2.81 |
| Mean LLM calls / question | 4.95 | 3.90 |
