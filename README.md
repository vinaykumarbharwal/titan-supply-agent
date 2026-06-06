# 🚀 Project Titan – Supply Chain Multi-Agent Digital Twin

**Titan** is a multi-agent digital twin and autonomous "War Room" for logistics and procurement management. It implements a stateful agentic system that continuously monitors global risk signals, calculates margin degradation on specific SKUs, drafts supplier negotiation proposals, and performs compliance audits. 

To ensure complete corporate safety, Titan implements a strict **Human-in-the-Loop Gateway** where no email ever leaves the organization without an operator's explicit review and approval.

---

## 🏗️ Multi-Agent Architecture

```
[START]
   │
   ▼
[Scout Agent]       ◄─── Scans global news via Tavily / GDELT (triggers on energy, labor, supply events)
   │
   ▼
[Router Node]
   ├── risk_score < 0.4 ──► [SLEEP / END]
   └── risk_score ≥ 0.4 ──► [Analyst Agent]
                                │
                                ▼
                           [Analyst Agent]     ◄─── Loads SKU-margins CSV; runs quant cost surcharges
                                │
                                ▼
                          [Negotiator Agent]   ◄─── Queries past deals; drafts discount ask proposals
                                │
                                ▼
                          [Compliance Agent]   ◄─── Audits terms against rules in DB; loops on blocks
                                ├── rejected ──► back to [Negotiator Agent] (max 3 retries)
                                └── approved ↓
                          [INTERRUPT — Human]  ◄─── Pauses execution thread, triggers notifications
                                │
                     ┌──────────┴──────────┐
                  [APPROVE]           [REJECT/EDIT]
                     │                     │
                     ▼                     ▼
              [Gmail Action]         [DISCARD / LOG]   ◄─── Logs decision outcome & embeddings to DB
                     │
                    [END]
```

---

## 📂 Project Directory Structure

```text
titan-supply-agent/
├── titan/
│   ├── agents/
│   │   ├── scout.py          # Scans news APIs & outputs structured RiskSignals
│   │   ├── analyst.py        # Quantifies margin drops on SKU records using Pandas
│   │   ├── negotiator.py     # Generates negotiation emails using LiteLLM/Groq
│   │   └── compliance.py     # Checks drafts against database-backed policy rules
│   ├── data/
│   │   └── suppliers_sku.csv # Simulated database of internal costs, margins, and suppliers
│   ├── db/
│   │   └── models.py         # SQLAlchemy schemas (rules & log archives) & vector embeddings
│   ├── graph/
│   │   ├── state.py          # State dictionary schema (TitanState)
│   │   ├── nodes.py          # Graph node functions & Slack notification hooks
│   │   └── graph.py          # Assembles the StateGraph compiled with SQLite checkpointers
│   ├── tools/
│   │   ├── tavily_tool.py    # Search utility with robust high-fidelity mock news fallback
│   │   ├── gmail_tool.py     # Sends emails via SMTP with mock outbox fallback
│   │   └── mock_email_tool.py# Records dispatched emails locally in titan/outbox/
│   ├── ui/
│   │   └── app.py            # Chainlit War Room approval dashboard
│   └── config.yaml           # Risk keyword lists, supplier details, and rule ceilings
├── requirements.txt          # Python dependencies
├── run_pipeline.py           # CLI runner for graph verification and simulation
├── README.md                 # Project documentation
└── .env                      # Local environment configurations (ignored from git)
```

---

## 🛠️ Setup Instructions

### 1. Pre-requisites
Make sure you have Python 3.9+ installed on your system.

### 2. Install Dependencies
Install all required libraries via `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 3. Environment Variables Setup
Copy the template `.env.example` file to `.env`:
```bash
cp titan/.env.example .env
```
Open `.env` and fill in your credentials. The code is designed to work in a **fallback mock state** out-of-the-box if keys are omitted:
- **`GROQ_API_KEY`**: (Required for LLM execution). Runs models using Groq's high-speed inference engine (`groq/llama-3.3-70b-specdec`).
- **`DATABASE_URL`**: Set a Neon Postgres connection string for remote database. If left blank, it defaults to a local `titan_dev.db` SQLite database.
- **`TAVILY_API_KEY`**: Scrapes news. If blank, Scout runs using high-fidelity simulated threat signals.
- **`SLACK_WEBHOOK_URL`**: Sends approval notifications to Slack channels. If blank, outputs notices to the console.
- **`SMTP_SERVER`/`SMTP_PASSWORD`**: Sends real emails. If blank, mails are saved as `.txt` files in `titan/outbox/`.

---

## 🚀 Execution & Verification

### 📋 Method A: CLI Simulator
To run a full simulation of the pipeline, test state transitions, trigger the interrupt gate, and approve or edit the result via your terminal:
```bash
python run_pipeline.py
```
*Observe the nodes executing in real-time, input `A` to approve the email when prompted, and inspect `titan/outbox/` for the completed file.*

### 🖥️ Method B: Chainlit Interactive Portal
To run the interactive web interface representating the War Room Operator Portal:
```bash
chainlit run titan/ui/app.py
```
1. Open the local address in your browser (typically `http://localhost:8000`).
2. Type **`run`** or **`trigger`** in the chat box to initiate a War Room Cycle.
3. Watch the Scout's alerts, the Analyst's margin analysis grid (formatted in a Markdown table), the negotiation draft, and the compliance officer audit render.
4. Use the **Action Buttons** to either:
   - **Approve & Send**: Dispatches the email.
   - **Edit Draft**: Request a text box to rewrite the email inline before sending.
   - **Discard**: Discard the proposal and log the rejection.

---

## 🧠 Features & Advanced Implementation Highlights

- **Durable State Checkpoints**: Graph checkpoints are preserved via SQLite database savers (`SqliteSaver` fallback). If the server crashes or restarts, execution resumes exactly where it left off.
- **Dynamic Governance Layer**: Compliance checks are evaluated against a live database table of rules (`compliance_rules`). Admin users can add or modify rules (e.g., banning specific terms, setting contract length thresholds) without redeploying code.
- **Semantic Negotiations Search**: Negotiators search history using a local, deterministic vectorization algorithm representing sentences in a 1536-dimensional space (fully compatible with standard `pgvector(1536)` Postgres specifications). Past negotiation strategies are loaded to reference terms.
