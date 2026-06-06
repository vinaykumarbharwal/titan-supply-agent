# Project Titan – System Design Document

## Overview

**Titan** is a multi-agent supply chain digital twin that acts as an autonomous "War Room" for logistics companies. A swarm of specialized AI agents continuously monitors global risk signals, calculates financial impact, drafts supplier negotiations, and enforces compliance — all with a mandatory human approval gate before any real-world action is taken.

---

## Agent Roster

### 1. Scout (News Monitor)
- **Job:** Wake every 6 hours, scan news APIs for configured risk signals.
- **Triggers on:** Oil price spikes ≥5%, port strikes, sanctions, commodity shortages.
- **Output:** `RiskSignal` Pydantic object with a normalized `risk_score` (0–1).

### 2. Analyst (Quant)
- **Job:** Receive Scout's `RiskSignal`, load internal CSVs, recalculate margin impact.
- **Example logic:** "Oil +5% → shipping cost +$2k/container → margin on SKU-42 drops from 18% to 11%."
- **Output:** Structured `ImpactReport` with affected suppliers and financial delta.

### 3. Negotiator (Strategy)
- **Job:** Use `ImpactReport` to draft a supplier negotiation email.
- **Example output:** "Request 3% bulk discount from Supplier B to offset $2k/container shipping increase."
- **Output:** `NegotiationDraft` (subject, body, discount amount) — marked `compliance_status: pending`.

### 4. Compliance Officer (Guardrail)
- **Job:** Review `NegotiationDraft` against a strict Policy Rulebook.
- **Hard rules:** No promises of fixed pricing >12 months. No gift/incentive language. Anti-bribery check.
- **Output:** `approved` or `rejected` with a written `rejection_reason`.
- **On rejection:** Loops back to Negotiator for a rewrite (max 3 retries).

---

## State Graph (LangGraph)

```
[START]
   │
   ▼
[Scout Node]  ◄─── Wakes every 6h (cron/scheduler)
   │
   ▼
[Router Node]
   ├── risk_score < 0.4 → [SLEEP]
   └── risk_score ≥ 0.4 → [Analyst Node]
                               │
                               ▼
                         [Negotiator Node]
                               │
                               ▼
                         [Compliance Node]
                               ├── rejected → back to [Negotiator Node]
                               └── approved ↓
                         [INTERRUPT — Human Check]
                               │
                    ┌──────────┴──────────┐
                 [APPROVE]           [REJECT/EDIT]
                    │                     │
                    ▼                     ▼
             [Gmail Action]         [DISCARD / Reroute]
                    │
                   [END]
```

### Key LangGraph Concepts Used

| Concept | Implementation |
|---------|---------------|
| **Checkpointer** | PostgreSQL (prod) / SQLite (dev) — saves state at every node |
| **Interrupt** | Graph pauses after Compliance approval, waits for human webhook |
| **Conditional Edge** | Router node branches on `risk_score` threshold |
| **Retry Loop** | Compliance rejection re-routes to Negotiator (max_retries=3) |

---

## Human-in-the-Loop Flow

1. Compliance Officer approves draft.
2. LangGraph hits `interrupt()` — execution pauses, state saved to DB.
3. System fires a **Slack webhook**: "New negotiation draft ready. [View & Approve]"
4. Operator clicks link → sees Chainlit UI with:
   - Scout's risk signal
   - Analyst's impact report
   - Negotiator's email draft
   - Compliance Officer's approval note
5. Operator clicks **Approve** or **Reject**.
6. Webhook hits `/resume` endpoint → LangGraph resumes from checkpoint.
7. On Approve → Gmail API sends email.
8. On Reject → draft discarded, state logged.

---

## Database Schema (Neon — Serverless PostgreSQL)

> **Setup:** Create a free project at [neon.tech](https://neon.tech). Copy the connection string into your `.env` as `DATABASE_URL`. Neon has pgvector built-in — just run `CREATE EXTENSION vector;`.

```sql
-- Agent execution state (managed by LangGraph checkpointer)
TABLE checkpoints (
  thread_id   TEXT,
  checkpoint  JSONB,
  metadata    JSONB,
  created_at  TIMESTAMPTZ
);

-- Negotiation history (semantic memory via pgvector)
TABLE negotiations (
  id              UUID PRIMARY KEY,
  supplier_id     TEXT,
  risk_signal     JSONB,
  impact_report   JSONB,
  draft_body      TEXT,
  embedding       VECTOR(1536),   -- for similarity search
  outcome         TEXT,           -- 'sent' | 'rejected' | 'discarded'
  created_at      TIMESTAMPTZ
);

-- Policy rulebook (editable without redeployment)
TABLE compliance_rules (
  id          SERIAL PRIMARY KEY,
  rule_text   TEXT,
  severity    TEXT    -- 'hard_block' | 'warning'
);
```

---

## Configuration (config.yaml)

```yaml
risk_signals:
  - keyword: "crude oil"
    threshold_pct: 5
    impact_model: "shipping_cost_linear"
  - keyword: "port strike"
    threshold_pct: 0
    impact_model: "route_disruption"

suppliers:
  - id: "SUP-B"
    name: "Supplier B"
    email: "procurement@supplierb.com"
    max_discount_ask_pct: 5

compliance:
  max_pricing_lock_months: 12
  block_keywords: ["gift", "gratuity", "guaranteed fixed price"]

schedule:
  scout_interval_hours: 6
```

---

## Directory Structure

```
titan/
├── agents/
│   ├── scout.py          # News fetching + risk scoring
│   ├── analyst.py        # Margin impact calculation
│   ├── negotiator.py     # Email draft generation
│   └── compliance.py     # Policy rulebook checker
├── graph/
│   ├── state.py          # TitanState TypedDict
│   ├── nodes.py          # LangGraph node functions
│   └── graph.py          # Graph assembly + checkpointer
├── tools/
│   ├── tavily_tool.py
│   ├── gmail_tool.py
│   └── mock_email_tool.py
├── ui/
│   └── app.py            # Chainlit interface
├── db/
│   ├── models.py         # SQLAlchemy models
│   └── migrations/
├── config.yaml
└── .env.example
```

---

## Interview Talking Points

- **"Durable agents"** — The system can be killed mid-execution and resume exactly where it left off via LangGraph's checkpointer. Demonstrate by killing the process during Analyst → Compliance and restarting.
- **"Human-in-the-loop"** — No email ever sends without a human clicking Approve. The graph literally cannot proceed past the interrupt without external input.
- **"Governance layer"** — Compliance Officer is a separate LLM call with its own system prompt and a database-backed rulebook — not just a filter, but an auditable decision log.
- - **"Stateful agentic pattern"** — Unlike fire-and-forget LLM chains, this is a long-running process with state, memory, retries, and conditional branching. This is what 2026 enterprise AI actually looks like.

---

## Phase 4 – Packaging (No Docker)

Run everything locally:

```bash
# No local DB needed — Neon connection string is in .env
# Run the agent graph
python graph/graph.py

# Start Chainlit UI
chainlit run ui/app.py
```

Record a Loom video showing the Human-in-the-loop flow: receiving a Slack alert, clicking the link, reviewing the draft in Chainlit, and hitting "Approve".
