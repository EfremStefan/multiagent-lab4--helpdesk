# E1 evaluation (llama3.1:8b, 20 questions)

Judge model: `llama3.1:8b`. Tau = 0.5, chunk size = 900. Escalation metrics are n/a for baseline and RAG because they have no ticket tool. Hit@k uses k = 4 for RAG and up to 5 chunks above tau for the multi-agent system.

| Metric | Baseline | Single RAG (B3) | Multi-agent |
|---|---|---|---|
| Fact accuracy (string match) | 18 % | 73 % | 83 % |
| Fact accuracy (LLM judge) | 23 % | 59 % | 60 % |
| Refusal correctness (Q18, Q20) | 0 % | 100 % | 100 % |
| False refusals on in-manual questions | 0 | 2 | 1 |
| Escalation precision | n/a | n/a | 1.00 |
| Escalation recall | 0.00 | 0.00 | 0.50 |
| Escalation F1 | n/a | n/a | 0.67 |
| Ticket priority correct | n/a | n/a | 2/2 |
| Retrieval hit@k | n/a | 94 % | 100 % |
| Mean latency (s / question) | 3.13 | 0.66 | 4.00 |
| Mean LLM calls / question | 1.00 | 1.00 | 4.95 |

## Per question

| Q | baseline facts | rag facts | mas facts | MAS ticket | MAS retrieved gold |
|---|---|---|---|---|---|
| 1 | 0/4 | 4/4 | 4/4 | - | yes |
| 2 | 0/1 | 0/1 | 1/1 | - | yes |
| 3 | 0/5 | 3/5 | 3/5 | - | yes |
| 4 | 0/2 | 2/2 | 2/2 | - | yes |
| 5 | 2/3 | 3/3 | 3/3 | - | yes |
| 6 | 1/1 | 0/1 | 1/1 | - | yes |
| 7 | 0/1 | 1/1 | 1/1 | - | yes |
| 8 | 0/3 | 3/3 | 1/3 | - | yes |
| 9 | 0/5 | 5/5 | 5/5 | - | yes |
| 10 | 0/5 | 5/5 | 5/5 | - | yes |
| 11 | 0/2 | 2/2 | 1/2 | medium | yes |
| 12 | 0/2 | 1/2 | 1/2 | - | yes |
| 13 | 1/2 | 0/2 | 2/2 | high | yes |
| 14 | 0/1 | 1/1 | 1/1 | - | yes |
| 15 | 1/2 | 2/2 | 2/2 | - | yes |
| 16 | 1/2 | 2/2 | 2/2 | - | yes |
| 17 | 0/1 | 1/1 | 1/1 | - | yes |
| 18 | answered | refused | refused | - | n/a |
| 19 | 0/1 | 0/1 | 0/1 | - | yes |
| 20 | answered | refused | refused | - | n/a |
