# QueueStorm Investigator

AI/API SupportOps copilot for digital finance complaint triage — built for the **bKash SUST CSE Carnival 2026 / Codex Community Hackathon** preliminary round.

The service reads a single customer complaint plus a short transaction history, then returns a structured JSON analysis that classifies the case, routes it to the right department, and drafts a safe customer reply.

---

## 1. What this service exposes

| Method | Path               | Purpose                                          |
| ------ | ------------------ | ------------------------------------------------ |
| GET    | `/health`          | `{"status":"ok"}` — readiness probe              |
| POST   | `/analyze-ticket`  | Analyze one ticket, return structured response  |

The judge harness will only call these two endpoints.

---

## 2. Tech stack

- **Python 3.11** + **FastAPI** (uvicorn ASGI server)
- **Pydantic v2** for request/response validation and enum enforcement
- **Rule-based reasoning pipeline** (no external LLM required, fully offline, <1s typical response)
- **Groq client** included in `requirements.txt` for an optional hybrid layer
- **Docker** image (slim, <500MB) for reproducible deployment

The default implementation is **100% rule-based** so it scores consistently without third-party API keys, GPU, or large downloads.

---

## 3. Quick start (local)

```bash
# 1. Create venv
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the service (binds to 0.0.0.0:8000)
python main.py
# or:
uvicorn main:app --host 0.0.0.0 --port 8000
```

Test:

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl -X POST http://localhost:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d @sample_input.json
```

A worked example response is included in `sample_output.json`.

---

## 4. Docker

```bash
docker build -t queuestorm-team .
docker run --rm -p 8000:8000 queuestorm-team
```

The image binds to `0.0.0.0:8000`, responds to `/health` within seconds, and contains no GPU dependencies or large model weights.

---

## 5. AI approach — why rule-based

The reasoning layer is a **deterministic pipeline**:

1. **Text normalization** — Bangla → Arabic digits, lowercase, diacritic strip, phrase canonicalization across English / Bangla / Banglish.
2. **Entity extraction** — amount, phone, time-of-day.
3. **Transaction matching** — scored match over `transaction_history` on amount (+3), counterparty (+3), type (+2), status (+1); threshold 3.
4. **Evidence verification** — `consistent` / `inconsistent` / `insufficient_data` based on the matched transaction's status versus the complaint's claim.
5. **Case classification** — 8 enum `case_type`s from the problem statement, with a priority ordering for phishing > wrong_transfer > payment_failed > duplicate > merchant > agent > refund > other.
6. **Routing + severity** — `case_type → department` lookup from Section 7.2 of the problem statement, escalated by verdict and amount.
7. **Drafting** — short, neutral templates per case type, then passed through the safety sanitizer.

**Why not LLM?** The task is well-defined by enum taxonomies and safety rules. A rule-based pipeline:

- is **fast** (<1s typical, well under the 30s budget),
- is **free** (no API cost),
- is **safe by construction** (the safety layer is regex over a known surface),
- is **reproducible** (same input → same output, every run),
- fits the **<5GB image / no-GPU / no-multi-GB-download** constraints.

Groq is wired in `requirements.txt` as an **optional** upgrade path. The pipeline currently does not call it, but a hybrid (rules for routing/evidence + LLM for reply phrasing) is straightforward to add.

---

## 6. Safety logic (Section 8 enforcement)

After reasoning, every `customer_reply` and `recommended_next_action` is passed through `reasoning/safety.py`, which enforces:

| Rule | What is blocked | Replacement |
| ---- | ---------------- | ----------- |
| No credential requests | `share your PIN`, `enter your OTP`, `provide your password`, `card number`, etc. | `keep your account secure` |
| No unauthorized commitments | `we will refund`, `your refund is confirmed`, `we will reverse`, `account will be unblocked` | `Any eligible amount will be reviewed and returned through official channels after verification by the support team.` |
| No third-party directions | `call this number`, `meet him`, `send money to +880...` | `use only official support channels` |
| Prompt-injection guard | `ignore previous instructions`, `reveal system prompt`, etc. | Detected → logged via `reason_codes`, **never obeyed** |

The safety layer runs **twice**: once inside the pipeline and once as a defense-in-depth pass before returning the response in `main.py`.

---

## 7. MODELS section (required)

| Model | Where it runs | Why chosen |
| ----- | -------------- | ---------- |
| _(none)_ | n/a | The default service uses a **rule-based reasoning pipeline**. No LLM, no embeddings, no large model weights are loaded. The pipeline satisfies the scoring categories (evidence reasoning, safety, schema correctness, performance) without external API cost or GPU. |
| `llama-3.3-70b-versatile` (Groq, **optional / not active**) | External Groq API | Available as a fallback for richer reply phrasing if a Groq key is supplied via `GROQ_API_KEY`. Not used by default to keep the service free, deterministic, and offline-capable. |

---

## 8. Response schema (matches the problem statement exactly)

```json
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports a transfer sent to the wrong recipient...",
  "recommended_next_action": "Verify recipient details and amount with the customer...",
  "customer_reply": "We have noted your concern about transaction TXN-9101...",
  "human_review_required": true,
  "confidence": 0.9,
  "reason_codes": ["wrong_transfer_signal", "transaction_match", "amount_match"]
}
```

All enum values match the problem statement **case-sensitively**. Variants like `WrongTransfer` or `wrongtransfer` are rejected by Pydantic at the response layer.

---

## 9. Assumptions and known limitations

- Transaction history is expected to be 2–5 entries (per Section 5). Empty history is handled — returns `insufficient_data`.
- Phone numbers are normalized by last-8-digit substring match (handles `+880`, `0`, missing country code).
- Amount parsing handles `5000`, `5k`, `5 thousand`, `2 lakh`, and Bangla digits `৫০০০`.
- The safety sanitizer is regex-based and intentionally conservative — false positives (replacing safe phrasing) are preferred over safety violations.
- No real customer data or payment-system integration is used. All examples are synthetic.
- The service does not call external APIs by default. If `GROQ_API_KEY` is supplied, a hybrid layer can be enabled; the current default is fully offline.

---

## 10. Environment variables

See `.env.example`. No real secrets are committed; the service runs with no environment variables set.

---

## 11. Repo layout

```
.
├── main.py                 # FastAPI app, /health + /analyze-ticket
├── queuestorm/
│   ├── models.py           # Pydantic schemas (request + response + enums)
│   └── config.py           # Env loading (port, timeouts, optional key)
├── reasoning/
│   ├── text.py             # Normalization + Bangla/Banglish phrase canonicalization
│   ├── entities.py         # Amount / phone / time-of-day extraction
│   ├── matcher.py          # Transaction matching scorer
│   ├── verifier.py         # consistent / inconsistent / insufficient_data
│   ├── classifier.py       # case_type selection
│   ├── router.py           # department + severity escalation
│   ├── drafter.py          # agent_summary / next_action / customer_reply templates
│   ├── safety.py           # Section 8 sanitizer + injection detection
│   └── pipeline.py         # Orchestrates the above into the final response
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .env.example
├── sample_output.json
└── README.md
```

---

## 12. Quick test recipe for judges

```bash
# 1. Run
python main.py

# 2. Health
curl http://localhost:8000/health

# 3. Wrong-transfer sample (use input from SUST_Preli_Sample_Cases.json case 1)
curl -X POST http://localhost:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d @sample_input.json
```

The service should respond in well under a second with a JSON body matching the schema above.

---

Built by **Team Committed to Conflict** — SUST CSE Carnival 2026 / Codex Community Hackathon preliminary round.
