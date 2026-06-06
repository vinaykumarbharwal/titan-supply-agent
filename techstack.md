# Project Titan – Tech Stack Reference

## Core Orchestration

| Tool | Role | Why |
|------|------|-----|
| **LangGraph** | Agent state machine & durable execution | Pause/resume nodes, checkpointing, human-in-the-loop interrupts |
| **LiteLLM** | Unified LLM gateway | Swap between GPT-4, Claude 3, Llama 3 without rewriting agent code |
| **CrewAI / LangChain** | Agent role definitions | Role-based agent personas (Scout, Analyst, Negotiator, Compliance) |

---

## LLM Providers (via LiteLLM)

| Provider | Model | Use Case |
|----------|-------|----------|
| Anthropic | claude-3-opus / sonnet | Negotiator & Compliance (nuanced reasoning) |
| OpenAI | gpt-4o | Analyst (structured output, function calling) |
| Meta (local) | Llama 3 via Ollama | Fallback / cost reduction in dev |

---

## Agent Tooling

| Tool | Agent | Purpose |
|------|-------|---------|
| **TavilySearchAPIWrapper** | Scout | Real-time market news & risk signals |
| **GDELT API** | Scout | Global event monitoring (geopolitical risk) |
| **Pandas + CSV** | Analyst | Internal cost/margin recalculation |
| **Gmail API** | Negotiator | Send approved supplier emails |
| **Slack Webhook** | System | Human-in-the-loop notifications |
| **Mock Email Tool** | Dev/Testing | Console-print emails before real API wiring |

---

## Database & Memory

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Primary DB** | [Neon](https://neon.tech) (serverless Postgres, free tier) | Persistent agent state, negotiation logs |
| **Vector Extension** | pgvector (built-in on Neon) | Semantic memory of past negotiations |
| **Checkpointer** | LangGraph + SQLite (dev) / Neon Postgres (prod) | Durable execution — restart mid-graph |

---

## Frontend & Visualization

| Tool | Purpose |
|------|---------|
| **Chainlit** | Python-native UI; visualizes agent thought process, chat traces |
| **Slack / Discord Webhook** | Approval notifications for Human-in-the-loop |
| **Loom** | Demo recording (Human approval flow) |

---

## Infrastructure & DevOps

| Tool | Purpose |
|------|---------|
| **Neon (neon.tech)** | Serverless Postgres online — free tier, no local install needed |
| **`.env` file** | Secrets management (API keys, DB connection string, webhook URLs) |
| **GitHub Actions** (optional) | CI for linting/testing agent logic |

---

## Data Models (Pydantic)

```python
class RiskSignal(BaseModel):
    source: str           # "Tavily" | "GDELT"
    headline: str
    risk_score: float     # 0.0 – 1.0
    commodity: str        # "crude_oil" | "shipping" | etc.
    timestamp: datetime

class NegotiationDraft(BaseModel):
    supplier_id: str
    subject: str
    body: str
    discount_requested: float
    compliance_status: Literal["pending", "approved", "rejected"]
    rejection_reason: Optional[str]
```

---

## Development Phases → Tools Used

| Phase | Primary Tools |
|-------|--------------|
| Phase 1 – Durable Skeleton | LangGraph, SQLite checkpointer |
| Phase 2 – Live Tooling | Tavily API, LiteLLM, Mock Email |
| Phase 3 – Governance Layer | LangGraph interrupt node, Compliance LLM prompt |
| Phase 4 – Packaging | Chainlit, Slack webhook, Loom |
