# Lab 4 Report — Multi-Agent MycoVault MV-200 Helpdesk

**Course:** Multi-Agent Systems (MAS)  
**Stack:** Python, Ollama (`llama3.1:8b`, `nomic-embed-text`), NumPy  
**Default settings:** chunk size 900, overlap 150, RAG k=4, Retriever k=5, τ=0.50

---

## 1. Architecture

```
Customer
   │
   ▼
Coordinator  ── blackboard (Message envelope) ──► Triage
   │                                                │
   │◄───────────────────────────────────────────────┘
   │
   ├──► Retriever ──► Knowledge Base (chunk + embed + cosine)
   │
   ├──► Specialist (intent-specific prompts)
   │
   ├──► Verifier (JSON fact check; up to 2 revisions)  ← ablated on/off in E2
   │
   └──► Escalation ──► tools: lookup_error_code, create_ticket
```

Agents exchange structured `Message(sender, receiver, performative, content, ts)` objects. The coordinator owns conversation state, routes messages, and enforces the retry / escalation policy. Empty retrieval or a `NOT_IN_MANUAL` draft never invents an answer: the system declines or escalates.

---

## 2. Agent prompts

### Baseline (Part A)

> You are a helpful customer-support agent for the MycoVault MV-200 mushroom growing cabinet.

### Single RAG agent (Part B3)

> Answer ONLY from the manual excerpts given between `<context>` and `</context>`. Cite section names as `[Section: <name>]`. If the context does not contain the answer, reply exactly: `NOT_IN_MANUAL`.

### Triage

Classifies `intent` ∈ {troubleshooting, cultivation, maintenance, safety, warranty, off_topic}, `urgency`, `error_code`, `species`, and rewrites a `standalone_question` using history for follow-ups.

### Retriever

Expands the question into 2–3 alternative search queries (manual vocabulary), merges KB hits, drops chunks with score < τ, returns at most 5.

### Specialist (base + intent variants)

Answers only from CONTEXT, cites `[Section: ...]`, never invents numbers. Intent-specific add-ons for troubleshooting (numbered steps), safety (urgent protective action first), maintenance, cultivation, warranty.

### Verifier

Strict fact checker: JSON `{supported, unsupported_claims, missing_safety_warning, feedback}` against CONTEXT.

### Escalation (`ESCALATION_POLICY`)

Ticket only for Section 9 rules: E19 twice / 24 h (medium); E23 > 10 min (high); E07 back within 7 days (medium); burning smell / smoke / water leak (high, unplug). Guardrails in `tools.py` validate tool calls before execution.

---

## 3. Part A / B observations

### Baseline hallucinations (Part A)

Without the manual, `llama3.1:8b` invents fluent but wrong answers, e.g.:

- **Q9 (descale):** invents vinegar soak steps (manual: 5 % citric acid, CLEAN = MODE+FAN).
- **Q10 (E12):** invents “E12 LED candelabra bulb” (manual: SporeEye contamination / Quarantine).

It rarely says “I don’t know”.

### Retrieval demo (Task B1)

| Query | Top section | Score |
|-------|-------------|-------|
| E07 | 7. Error Codes | 0.627 |
| lion's mane humidity | 5. Cultivation Profiles | 0.666 |
| bleach | 5. Cultivation Profiles | 0.498 |

**Note:** “bleach” does **not** retrieve Maintenance first. Query expansion in the multi-agent Retriever and a wider top-k usually still surface the warranty / maintenance bleach rule.

### Single RAG (B3) on Q1–10

9/10 grounded correctly in the lab run. Q6 (5 GHz-only router) returned `NOT_IN_MANUAL` once (retrieval miss of the 2.4 GHz fact).

### Tau sweep

| τ | hit@5 (in-manual) | mean chunks kept |
|---|---|---|
| 0.40 | 17/18 | 5.0 |
| 0.45 | 17/18 | 5.0 |
| **0.50** | **17/18** | **4.7** |
| 0.55 | 16/18 | 3.1 |

Chosen τ = **0.50**. Out-of-manual Q18 still scores ~0.75 at top, so refusal must come from the Specialist / `NOT_IN_MANUAL` path, not from empty retrieval alone.

---

## 4. D1 demo traces (tools / escalation)

Full blackboard traces: [`results/d1_traces.md`](results/d1_traces.md).

| Case | Question | Ticket |
|------|----------|--------|
| No ticket | My display shows E07… | none (`lookup_error_code` only) |
| Medium | I got E19 this morning and again now. | medium priority |
| High | Water under the cabinet and a burning smell! | high + unplug |

---

## 5. E1 evaluation (20 questions, `llama3.1:8b`)

Source: [`results/eval_table.md`](results/eval_table.md).

| Metric | Baseline | Single RAG (B3) | Multi-agent |
|---|---|---|---|
| Fact accuracy (string match) | 18 % | 73 % | **83 %** |
| Fact accuracy (LLM judge) | 23 % | 59 % | **60 %** |
| Refusal correctness (Q18, Q20) | 0 % | **100 %** | **100 %** |
| False refusals on in-manual questions | 0 | 2 | 1 |
| Escalation precision | n/a | n/a | **1.00** |
| Escalation recall | 0.00 | 0.00 | **0.50** |
| Escalation F1 | n/a | n/a | **0.67** |
| Ticket priority correct | n/a | n/a | **2/2** |
| Retrieval hit@k | n/a | 94 % | **100 %** |
| Mean latency (s / question) | 3.13 | **0.66** | 4.00 |
| Mean LLM calls / question | 1.00 | 1.00 | 4.95 |

Grounding (RAG / MAS) beats the baseline by a large margin. MAS is slower and more expensive per question than single RAG, but improves fact string match, hit@k, and adds escalation with perfect precision on the tickets it opens.

---

## 6. E2 ablation — Verifier on vs off

**Design choice:** keep `llama3.1:8b` fixed and toggle only the Verifier + revision loop. This avoids loading a second chat model into VRAM (the earlier 3B vs 8B ablation heated the machine).

Source: [`results/ablation_verifier.md`](results/ablation_verifier.md). Verifier ON reuses the E1 multi-agent run.

| Metric | Verifier ON | Verifier OFF |
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
| Mean latency (s / question) | 4.00 | **2.81** |
| Mean LLM calls / question | 4.95 | **3.90** |

### Accuracy / latency trade-off

Turning the Verifier off saves about **1.2 s** and **~1 LLM call** per question (~30 % latency, ~20 % calls) with almost the same fact accuracy on this 20-question set. Escalation metrics are unchanged because tickets are decided by the Escalation agent + Section 9 guardrails, not by the Verifier.

On this small gold set the Verifier does not raise string-match accuracy; the LLM-as-judge even scores OFF slightly higher (noise / judge variance). The Verifier’s value is more about **safety / unsupported-claim filtering** on harder drafts than about mean fact scores here. For a production helpdesk, keeping it ON is still reasonable if latency budget allows; for interactive demos, OFF is much cheaper.

---

## 7. Failure cases

### 1. Retrieval ranking for “bleach” (B1)

Embedding search for “bleach” ranked Cultivation / Warranty / Safety above Maintenance, even though the bleach ban lives in Section 6. Dense retrieval alone is weak on rare keywords; query expansion and hybrid BM25 would help.

### 2. Escalation recall (Q12 / Q14)

Gold expects tickets for E23 after 25 minutes (high) and E07 returning after recalibration (medium). In E1, MAS opened correct tickets for Q11 and Q13 but missed Q12/Q14 (recall 0.50, precision 1.00). The Escalation LLM sometimes treats the case as “manual action still applies” and does not call `create_ticket`; the guardrail only *blocks* unjustified tickets — it does not force missing ones.

### 3. Partial facts / false refusal (e.g. Q8, Q19, RAG false refusals)

Some answers miss a subset of expected key facts (e.g. Lion’s Mane coral: CO₂ / FAN level) even when the right section is retrieved. Single RAG also had 2 false refusals on in-manual questions. Grounding reduces hallucination but can over-refuse when context is incomplete.

---

## 8. Reflection questions

### Part A — baseline (Q1–10)

**1. How many answers are correct according to the manual? How many are confidently wrong?**  
~0 fully correct. A couple are only vaguely right (bleach / tap water discouraged) but with wrong details. The other ~8–10 are confidently wrong (invented numbers and procedures).

**2. Did the model ever say “I don’t know”? Why is this behaviour rare?**  
No. Chat models are trained to be helpful and complete; with a support-agent prompt and no grounding, fluent guessing beats refusing.

**3. Which wrong answers would be dangerous for a customer (safety, warranty, money)?**  
Safety: wrong E07/E12 meaning (misses contamination / Quarantine / FFP2); bleach advice that skips CO₂-sensor damage. Warranty/money: “5-year warranty”; vinegar descaling; wrong humidity/filter intervals that can void warranty or ruin a grow.

### Report (deliverable)

**1. In which sense is your system a multi-agent system and not just a pipeline of function calls?**  
Each agent has its own goal and decision rule; they talk via structured blackboard messages; the coordinator’s retry/escalation policy can change control flow (reject, `NOT_IN_MANUAL`) — not a fixed function chain.

**2. What does the Verifier catch that the Specialist alone misses? What does it cost?**  
Unsupported claims / missing safety warnings, with revision feedback. On this set mean fact scores barely change when it is off; cost is ~+1 LLM call and ~+1.2 s per question (E2).

**3. Same base model for Verifier and Specialist — weakness and mitigation?**  
Shared blind spots (both may accept the same invented number). Mitigate with a different judge model, rule-based number checks against chunks, or require cited spans.

**4. Prompt injection via a manual chunk — where and how to defend?**  
Injected text in retrieved CONTEXT hits Specialist/Verifier prompts. Defend by treating chunks as untrusted data, stripping instruction-like lines, citing only chunk spans, and keeping ticket tools behind the Section 9 guardrail.

---

## 9. How to reproduce

See [`README.md`](README.md).

```powershell
python kb.py --demo
python baseline.py --part A
python baseline.py --part B3
python coordinator.py --demo-d1
python evaluate.py --tau-sweep
python evaluate.py
python evaluate.py --ablation verifier
```

Main artefacts: `results/partA_baseline.json`, `partB3_rag.json`, `d1_traces.md`, `eval_table.md`, `eval_llama3.1-8b.json`, `ablation_verifier.md`, `tau_sweep.md`.
