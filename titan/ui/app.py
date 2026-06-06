import os
import sys
# Resolve package paths for Chainlit execution context
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import json
import asyncio
import uuid
from dotenv import load_dotenv
import chainlit as cl

# Import LangGraph and DB helpers
from titan.graph.graph import app as graph_app
from titan.db.models import SessionLocal, Negotiation, init_db

load_dotenv()

# Initialize DB on app startup
init_db()

@cl.on_chat_start
async def start():
    # Welcome message with rich aesthetics
    await cl.Message(
        content="""# 🚀 Welcome to Project Titan: Multi-Agent War Room

Titan is an autonomous digital twin monitoring your supply chain margins, drafting negotiations, and ensuring compliance.

### 💡 How to operate:
Type **`run`** or **`trigger`** to scrape global risk signals and execute the multi-agent war room pipeline.
"""
    ).send()

async def run_graph_pipeline(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    
    # Store config in user session so action handlers can resume the graph
    cl.user_session.set("thread_id", thread_id)
    cl.user_session.set("graph_config", config)
    
    # Initialize the input state
    initial_state = {
        "risk_signal": None,
        "impact_report": None,
        "negotiation_draft": None,
        "compliance_audit": None,
        "feedback": None,
        "retry_count": 0,
        "human_action": None,
        "human_edited_subject": None,
        "human_edited_body": None,
        "outcome": None
    }
    
    # Start graph execution via async stream
    try:
        async for event in graph_app.astream(initial_state, config, stream_mode="values"):
            # Update user on progress as state variables populate
            state = event
            
        # Inspect state after interrupt
        current_state = graph_app.get_state(config)
        
        # Present details to operator
        await display_state_report(current_state.values)
        
    except Exception as e:
        await cl.Message(content=f"❌ **Execution Error:** {e}").send()

async def display_state_report(state: dict):
    risk = state.get("risk_signal")
    report = state.get("impact_report")
    draft = state.get("negotiation_draft")
    audit = state.get("compliance_audit")
    
    # 1. Scout Report
    if risk:
        risk_emoji = "⚠️" if risk.risk_score >= 0.6 else "ℹ️"
        await cl.Message(
            content=f"""### 🚨 Scout Threat Alert
* **Event:** {risk.headline}
* **Commodity:** `{risk.commodity.upper()}`
* **Risk Score:** {risk.risk_score:.2f} / 1.00 {risk_emoji}
* **Source:** {risk.source}
"""
        ).send()
        
    # 2. Analyst Report
    if report:
        # Build table of SKU impacts
        sku_rows = ""
        for s in report.affected_skus:
            margin_change = f"{s.original_margin*100:.1f}% ➡️ {s.new_margin*100:.1f}%"
            drop_color = "🔴" if s.margin_drop > 0.05 else "🟡"
            sku_rows += f"| {s.sku} | {s.supplier_name} | ${s.original_cost:.2f} | ${s.new_cost:.2f} | {margin_change} | {drop_color} {s.margin_drop*100:.1f}% |\n"
            
        await cl.Message(
            content=f"""### 📊 Quant Margin Impact Report
* **Worst Affected Supplier:** {report.worst_affected_supplier_name} ({report.worst_affected_supplier})
* **Projected Supply Cost Increase:** **${report.total_cost_increase:,.2f}**
* **Strategic Recommendation:** {report.recommendation}

#### SKU Margin Degradation Ledger:
| SKU | Supplier | Original Cost | New Cost | Margin Shift | Margin Drop |
| :--- | :--- | :--- | :--- | :--- | :--- |
{sku_rows}
"""
        ).send()
        
    # 3. Negotiator Draft & Compliance Status
    if draft:
        compliance_tag = "✅ APPROVED BY COMPLIANCE OFFICER" if audit and audit.is_compliant else "⚠️ COMPLIANCE VERIFICATION REQUIRED"
        await cl.Message(
            content=f"""### 📝 Negotiation Proposal Draft
* **Status:** {compliance_tag}
* **To:** {draft.to_email}
* **Subject:** {draft.subject}

```text
{draft.body}
```
"""
        ).send()
        
    # 4. Human Approval Gateway Action Buttons
    actions = [
        cl.Action(name="approve_draft", value="approve", label="🚀 Approve & Send", description="Email negotiation directly to supplier"),
        cl.Action(name="edit_draft", value="edit", label="📝 Edit Draft", description="Adjust email body inline"),
        cl.Action(name="reject_draft", value="reject", label="❌ Discard", description="Cancel proposal and close war room cycle")
    ]
    
    await cl.Message(
        content="### 🔒 Human-in-the-Loop Gateway\nPlease select an action to resolve the interrupt:",
        actions=actions
    ).send()

@cl.on_message
async def main(message: cl.Message):
    content = message.content.strip().lower()
    
    if content in ["run", "trigger", "start"]:
        thread_id = str(uuid.uuid4())
        await cl.Message(content=f"⚙️ **Spinning up Titan Digital Twin...** (Thread ID: `{thread_id}`)").send()
        # Run pipeline
        asyncio.create_task(run_graph_pipeline(thread_id))
    else:
        # Show help if input is unrecognized
        await cl.Message(
            content="Unrecognized command. Type **`run`** to initiate the multi-agent cycle."
        ).send()

@cl.action_callback("approve_draft")
async def on_approve(action: cl.Action):
    thread_id = cl.user_session.get("thread_id")
    config = cl.user_session.get("graph_config")
    
    await cl.Message(content="✅ **Approving draft. Resuming pipeline...**").send()
    
    # Update Graph State
    graph_app.update_state(config, {
        "human_action": "approve"
    }, as_node="human_approval")
    
    # Resume graph execution
    async for event in graph_app.astream(None, config, stream_mode="values"):
        state = event
        
    await cl.Message(content="📬 **Action Completed:** Negotiation proposal dispatched. Log saved to semantic memory database.").send()

@cl.action_callback("reject_draft")
async def on_reject(action: cl.Action):
    thread_id = cl.user_session.get("thread_id")
    config = cl.user_session.get("graph_config")
    
    await cl.Message(content="❌ **Discarding proposal. Closing thread...**").send()
    
    # Update Graph State
    graph_app.update_state(config, {
        "human_action": "reject"
    }, as_node="human_approval")
    
    # Resume graph execution
    async for event in graph_app.astream(None, config, stream_mode="values"):
        state = event
        
    await cl.Message(content="📁 **Action Completed:** Proposal discarded and logged in archive.").send()

@cl.action_callback("edit_draft")
async def on_edit(action: cl.Action):
    thread_id = cl.user_session.get("thread_id")
    config = cl.user_session.get("graph_config")
    
    # Fetch current draft details
    state_data = graph_app.get_state(config).values
    draft = state_data.get("negotiation_draft")
    
    # Prompt user for edits
    res = await cl.AskUserMessage(
        content=f"Please edit the email body below and submit it as a reply. Original body is copy-pasteable:\n\n```text\n{draft.body}\n```"
    ).send()
    
    if res:
        new_body = res['output'].strip()
        await cl.Message(content="✍️ **Saving edits and dispatching proposal...**").send()
        
        # Update state with edits
        graph_app.update_state(config, {
            "human_action": "edit",
            "human_edited_body": new_body,
            "human_edited_subject": draft.subject # Keep subject same
        }, as_node="human_approval")
        
        # Resume graph execution
        async for event in graph_app.astream(None, config, stream_mode="values"):
            state = event
            
        await cl.Message(content="📬 **Action Completed:** Custom negotiation proposal dispatched. Audit logs updated.").send()
