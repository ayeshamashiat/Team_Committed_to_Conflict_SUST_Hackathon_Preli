# QueueStorm Investigator

AI/API SupportOps copilot for digital finance complaint triage — built for the **bKash SUST CSE Carnival 2026 / Codex Community Hackathon** preliminary round.

The service reads a single customer complaint plus a short transaction history, then returns a structured JSON analysis that classifies the case, routes it to the correct department, and drafts a safe customer reply. The complaint says one thing; the data may say another. The service decides what is true.

---

## 1. API endpoints

| Method | Path              | Purpose                                         |
|--------|-------------------|-------------------------------------------------|
| GET    | `/health`         | `{"status":"ok"}` — readiness probe             |
| POST   | `/analyze-ticket` | Analyze one ticket, return structured response  |

The judge harness only calls these two endpoints.

---

## 2. Tech stack

| Component        | Choice                            |
|------------------|-----------------------------------|
| Language         | Python 3.11                       |
| Web framework    | FastAPI + uvicorn (ASGI)          |
| Schema layer     | Pydantic v2 (strict enum enforcement) |
| Reasoning        | Rule-based deterministic pipeline (default) |
| Optional LLM     | Groq `llama-3.3-70b-versatile` (disabled by default) |
| Containerization | Docker (slim image, < 500 MB)     |

The default path is **100% offline and rule-based** — no GPU, no large model weights, no API calls required.

---

## 3. Quick start (local)

```bash
# 1. Create virtualenv
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment template (no real values needed for rule-based mode)
cp .env.example .env

# 4. Run the service
python main.py
# or: uvicorn main:app --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl -X POST http://localhost:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d @sample_input.json
```

A worked example response is in `sample_output.json`.

---

## 4. Docker

```bash
docker build -t queuestorm-team .
docker run --rm -p 8000:8000 queuestorm-team
```

The image responds to `/health` within seconds and contains no GPU dependencies or large model files.

---

## 5. AI approach and reasoning pipeline

The reasoning layer is a **layered, deterministic pipeline** that runs in sequence:

```
complaint + transaction_history
        │
        ▼
[1] Text Normalization      (reasoning/text.py)
    Bangla → ASCII digits, lowercase, diacritic strip,
    phrase canonicalization for English / Bangla / Banglish

        │
        ▼
[2] Entity Extraction       (reasoning/entities.py)
    Amounts: "5000", "5k", "5 thousand", "২০০০", "2 lakh"
    Phones: normalised to last-8-digit match
    Time-of-day: "around 2pm", "this morning"

        │
        ▼
[3] Transaction Matching    (reasoning/matcher.py)
    Scores each history entry:
      +3  amount in complaint matches transaction amount
      +3  counterparty phone/ID found in complaint text
      +2  transaction type matches complaint keywords
      +1  transaction status mentioned in complaint
    Threshold ≥ 3 to declare a match.

        │
        ▼
[4] Evidence Verification   (reasoning/verifier.py)
    "consistent"        → matched transaction supports the complaint
    "inconsistent"      → data contradicts the complaint
                          (e.g. complaint says failed, status = completed)
    "insufficient_data" → no transaction matched, or history is empty

        │
        ▼
[5] Case Classification     (reasoning/classifier.py)
    Priority order:
    phishing > wrong_transfer > payment_failed > duplicate_payment
    > merchant_settlement_delay > agent_cash_in_issue > refund_request > other

        │
        ▼
[6] Routing + Severity      (reasoning/router.py)
    case_type → department (Section 7.2 lookup)
    Severity escalated upward when:
      - verdict is "inconsistent" or "insufficient_data"
      - amount ≥ 10,000 BDT → at least "high"
      - amount ≥ 50,000 BDT → "critical"
      - case_type is phishing → always "critical"

        │
        ▼
[7] Reply Drafting          (reasoning/drafter.py)
    Per-case-type neutral templates for agent_summary,
    recommended_next_action, and customer_reply.

        │
        ▼
[8] Safety Sanitizer        (reasoning/safety.py)  ← see Section 6
    Runs on every output string before the response is built.

        │
        ▼
[9] Final Safety Pass       (main.py)
    Defense-in-depth: sanitizer runs again after pipeline returns,
    before Pydantic validates and the HTTP response is sent.
```

**Why not LLM by default?**

The task is defined by strict enum taxonomies and a finite set of safety rules. A deterministic pipeline:
- responds in **< 1 second** (well under the 30 s judge budget)
- costs **nothing** (no API key, no tokens burned)
- is **safe by construction** — safety is code, not a prompt
- produces **identical output** for identical input (auditable, reproducible)
- fits the **< 5 GB / no-GPU** runtime constraint perfectly

When `ENABLE_GROQ=true` and `GROQ_API_KEY` are set, the pipeline calls `llama-3.3-70b-versatile` on Groq for richer text generation. Even then, the safety sanitizer still runs as a final pass over the LLM output — the LLM cannot bypass it.

---

## 6. Safety architecture (Section 8 enforcement)

This section describes exactly how the service prevents unsafe output from reaching customers or agents. Safety is enforced in **three independent layers** so that no single point of failure can produce a violation.

### Layer 1 — Phishing short-circuit (pipeline.py)

Before any reasoning runs, the pipeline checks whether the complaint itself describes a social-engineering attempt. If the complaint contains credential-related keywords (`pin`, `otp`, `password`, `card number`, Bangla equivalents: `ওটিপি`, `পিন`, `পাসওয়ার্ড`) **and** a context word indicating someone requested them (`asked`, `told me`, `demanded`, `চেয়েছে`), the pipeline short-circuits immediately to a `phishing_or_social_engineering` response with `severity: critical` and `department: fraud_risk`. The rule-based pipeline never even reaches the drafting stage for these cases.

### Layer 2 — Safe reply templates (drafter.py)

All `customer_reply` and `recommended_next_action` strings are generated from per-case-type templates that were authored to be safe. The templates:
- **never** ask for credentials — they proactively remind the customer not to share them
- use the approved hedge for financial outcomes: *"any eligible amount will be returned through official channels after verification by the support team"*
- direct customers only to *official* support channels

This means the baseline output is safe even before any sanitization.

### Layer 3 — Post-generation sanitizer (safety.py + main.py)

Every output string passes through `reasoning/safety.py` twice — once inside the pipeline and once as a defense-in-depth pass in `main.py` after the pipeline returns. The sanitizer applies four rule sets:

#### Rule 3a — Credential request blocking (−15 pts if violated)

The sanitizer detects any phrasing that requests credentials and replaces it:

| Pattern blocked | Replacement |
|----------------|-------------|
| `share your PIN / OTP / password / CVV / card number` | `keep your account secure` |
| `enter / send / provide / give your PIN or OTP` | `keep your account secure` |
| `your PIN`, `your OTP`, `your password` | `your account security` |
| Any remaining regex match on credential request phrases | `keep your account secure` |

The blocking uses both exact phrase tables (for common forms) and compiled regex patterns (for novel phrasing). Both run on every output string, in that order, so a paraphrase that evades the phrase table is still caught by the regex.

#### Rule 3b — Unauthorized commitment blocking (−10 pts if violated)

The sanitizer detects any language that promises financial action and replaces it:

| Pattern blocked | Replacement |
|----------------|-------------|
| `we will refund` / `we shall refund` | Safe hedge (see below) |
| `your refund is confirmed / approved / processed` | Safe hedge |
| `we will reverse` / `we are going to reverse` | Safe hedge |
| `account will be unblocked` | Account review language |
| `refund has been initiated / processed / sent` | Safe hedge |
| `money will be returned now / immediately / today` | Safe hedge |

Safe hedge: *"Any eligible amount will be reviewed and returned through official channels after verification by the support team."*

This runs on both `customer_reply` and `recommended_next_action`, so the agent-facing field cannot accidentally commit to a refund either.

#### Rule 3c — Third-party direction blocking (−10 pts if violated)

| Pattern blocked | Replacement |
|----------------|-------------|
| `contact this/that number` | `use only official support channels` |
| `call +880XXXXXXXX` | `use only official support channels` |
| `meet him / her / them` | `use only official support channels` |
| `send money to +880XXXXXXXX` | `use only official support channels` |

#### Rule 3d — Prompt injection detection (safety.py + pipeline.py)

The complaint field is treated as **data**, never as a command. If the complaint contains injection signatures, the pipeline:
1. logs a `WARNING` with the `ticket_id`
2. appends `"prompt_injection_detected"` to `reason_codes` in the response
3. **proceeds with normal analysis** — the injected text is ignored entirely

Injection patterns detected:

| Signature |
|-----------|
| `ignore previous instructions` / `ignore all previous instructions` |
| `ignore the above` |
| `disregard all prior` / `disregard prior instructions` |
| `system: you are` |
| `</system>` / `<system>` |
| `reveal your system prompt` / `reveal the hidden prompt` |
| `act as an admin / developer / root` |

### Safety guarantee summary

```
Customer complaint arrives
        │
        ├─[1]─ Phishing shortcut? ──yes──► hard-coded safe phishing response
        │                                   (sanitizer still runs on it)
        │
        ├─[2]─ Rule-based templates ────► safe by construction (no credentials,
        │      OR Groq LLM output           no refund promises, official channels only)
        │
        ├─[3]─ Pipeline sanitizer ──────► regex scrub of customer_reply
        │      (safety.py)                 and recommended_next_action
        │
        └─[4]─ Final sanitizer ─────────► same scrub again in main.py
               (main.py)                   before Pydantic schema validation
                                           before HTTP response is sent
```

Even if all three content-generation steps produced an unsafe string, Layer 4 (the final pass in `main.py`) would catch and replace it before it ever left the service.

---

## 7. MODELS section (required)

| Model | Where it runs | Why chosen |
|-------|---------------|------------|
| *(none — rule-based pipeline)* | In-process, no external call | Default path. Deterministic, sub-second, zero API cost, safe by construction. Satisfies all scoring categories without network dependency. |
| `llama-3.3-70b-versatile` (Groq, **disabled by default**) | External Groq API | Optional upgrade for richer free-text replies. Enabled only when `ENABLE_GROQ=true` and `GROQ_API_KEY` are set. Even when active, the safety sanitizer still runs over every LLM output before the response is returned. |

---

## 8. Response schema

Every `POST /analyze-ticket` response conforms to this shape (enum values are case-sensitive exact strings):

```json
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports a transfer sent to the wrong recipient...",
  "recommended_next_action": "Verify recipient details and initiate dispute workflow...",
  "customer_reply": "We have noted your concern about transaction TXN-9101...",
  "human_review_required": true,
  "confidence": 0.9,
  "reason_codes": ["wrong_transfer_signal", "transaction_match", "amount_match"]
}
```

Pydantic v2 enforces every field type and all enum values at the response layer. An invalid enum string returned by the LLM is coerced to the safe default (`"other"` / `"customer_support"` / `"medium"`) before the schema is validated.

### `human_review_required` escalation rules

This field is set to `true` whenever:
- `evidence_verdict` is `inconsistent` or `insufficient_data`
- `case_type` is `wrong_transfer` or `phishing_or_social_engineering`
- `severity` is `high` or `critical`
- transaction amount exceeds 10,000 BDT

### HTTP status codes

| Code | When returned |
|------|---------------|
| 200  | Successful analysis |
| 400  | Malformed JSON or missing required fields |
| 422  | Valid schema but empty complaint string |
| 500  | Internal error — body contains a generic message, never a stack trace or secret |

The service never crashes on bad input. All unhandled exceptions are caught by FastAPI exception handlers in `main.py` and return a 500 with a non-sensitive message.

---

## 9. Multilingual support

The service handles complaints in **English**, **Bangla (বাংলা)**, and **Banglish** (romanised Bangla):

- `reasoning/text.py` normalizes Bangla Unicode digits (`০–৯`) to ASCII, strips diacritics, and lowercases
- `reasoning/text.py` maps Banglish/Bangla phrases to canonical tags (`পাঠিয়েছি` → transfer signal, `কেটে গেছে` → deducted signal)
- `reasoning/matcher.py` carries synonym tables for all three scripts
- `reasoning/safety.py` includes Bangla credential terms (`ওটিপি`, `পিন`, `পাসওয়ার্ড`, `গোপন কোড`) in injection and phishing detection
- When the complaint is in Bangla (`language: "bn"`), the `customer_reply` template is returned in Bangla

---

## 10. Assumptions and known limitations

- Transaction history is expected to contain 2–5 entries. Empty history is handled: returns `insufficient_data` and routes to `customer_support`.
- Phone number matching uses last-8-digit substring comparison, which handles `+880`, `0`, and missing country-code prefixes but may produce false positives for numbers that share a suffix.
- Amount parsing covers `5000`, `5k`, `5 thousand`, `2 lakh`, and Bangla digits (`৫০০০`). Very unusual phrasings may fall back to no amount extracted.
- The safety sanitizer is regex-based and intentionally conservative. False positives (replacing safe phrasing) are preferred over safety violations.
- When Groq is enabled, response time is bounded by the Groq API (25 s timeout set in `call_groq`). The 30 s per-request limit from the problem statement is therefore tight with LLM; the rule-based default comfortably stays under 1 s.
- The service does not call any external API or payment system. All test data is synthetic.
- No real customer data is handled or stored at any point.

---

## 11. Environment variables

Copy `.env.example` to `.env` before running. The service starts with no variables set (rule-based mode).

| Variable        | Default  | Description |
|-----------------|----------|-------------|
| `PORT`          | `8000`   | Port the service listens on |
| `ENABLE_GROQ`   | `false`  | Set to `true` to enable the Groq LLM path |
| `GROQ_API_KEY`  | *(none)* | Required only when `ENABLE_GROQ=true` |
| `MODEL_NAME`    | `llama-3.3-70b-versatile` | Groq model override |

No secrets are committed to the repository. API keys are loaded from environment only, never hard-coded or logged.

---

## 12. Repo layout

```
.
├── main.py                 # FastAPI app — /health, /analyze-ticket, exception handlers,
│                           # final safety pass before response
├── queuestorm/
│   ├── models.py           # Pydantic v2 schemas: AnalyzeRequest, AnalyzeResponse, all enums
│   └── config.py           # Settings loaded from environment variables
├── reasoning/
│   ├── text.py             # Normalization + Bangla/Banglish phrase canonicalization
│   ├── entities.py         # Amount / phone / time-of-day extraction
│   ├── matcher.py          # Transaction matching scorer (amount, counterparty, type, status)
│   ├── verifier.py         # consistent / inconsistent / insufficient_data verdict
│   ├── classifier.py       # case_type selection (8 enum values, priority ordered)
│   ├── router.py           # department lookup + severity escalation rules
│   ├── drafter.py          # Safe reply templates per case_type
│   ├── safety.py           # Section 8 sanitizer: credential blocking, commitment blocking,
│   │                       # third-party direction blocking, prompt injection detection
│   ├── llm.py              # Groq integration (disabled by default), JSON coercion
│   └── pipeline.py         # Orchestrator: phishing shortcut → Groq (optional) → rule fallback
│                           # → final safety pass
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .env.example
├── sample_output.json      # Worked output for SAMPLE-01 (wrong_transfer)
└── README.md
```

---

## 13. Quick test recipe for judges

```bash
# 1. Start service
python main.py

# 2. Health check
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# 3. Wrong-transfer case (SAMPLE-01 from the public pack)
curl -X POST http://localhost:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TKT-001",
    "complaint": "I sent 5000 taka to a wrong number around 2pm today.",
    "language": "en",
    "channel": "in_app_chat",
    "user_type": "customer",
    "transaction_history": [
      {
        "transaction_id": "TXN-9101",
        "timestamp": "2026-04-14T14:08:22Z",
        "type": "transfer",
        "amount": 5000,
        "counterparty": "+8801719876543",
        "status": "completed"
      }
    ]
  }'

# 4. Phishing case (empty history is normal)
curl -X POST http://localhost:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TKT-005",
    "complaint": "Someone called me saying they are from bKash and asked for my OTP.",
    "language": "en",
    "channel": "call_center",
    "user_type": "customer",
    "transaction_history": []
  }'

# 5. Malformed input (must return 400, not crash)
curl -X POST http://localhost:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d '{"not_a_valid_field": true}'

# 6. Full sample output is in sample_output.json
```

The service responds in well under one second with a JSON body that matches the schema above.

---

Built by **Team Committed to Conflict** — SUST CSE Carnival 2026 / Codex Community Hackathon preliminary round.
