import os
import sqlite3
from typing import Dict, Any, Literal
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Import state and nodes
from titan.graph.state import TitanState
from titan.graph.nodes import (
    scout_node,
    analyst_node,
    negotiator_node,
    compliance_node,
    human_notification_node,
    human_approval_node,
    email_node,
    discard_node
)

load_dotenv()

# Setup Persistency Checkpointer
# We will use SqliteSaver for local state checkpointing persistence
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "titan_checkpoints.db"))
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    print(f"[Checkpointer] Persistent SqliteSaver configured at {db_path}")
except Exception as e:
    print(f"[Checkpointer Fallback] Could not initialize SqliteSaver: {e}. Using MemorySaver.")
    checkpointer = MemorySaver()

# Build Graph Workflow
workflow = StateGraph(TitanState)

# Add Nodes
workflow.add_node("scout", scout_node)
workflow.add_node("analyst", analyst_node)
workflow.add_node("negotiator", negotiator_node)
workflow.add_node("compliance", compliance_node)
workflow.add_node("notifier", human_notification_node)
workflow.add_node("human_approval", human_approval_node)
workflow.add_node("sender", email_node)
workflow.add_node("discarder", discard_node)

# Set entry node
workflow.set_entry_point("scout")

# Conditional edge functions
def route_scout(state: TitanState) -> Literal["analyst", "end"]:
    risk_sig = state.get("risk_signal")
    if not risk_sig or risk_sig.risk_score < 0.4:
        print(f"[Router] Scout risk score ({risk_sig.risk_score if risk_sig else 0.0}) under 0.4. Routing to SLEEP (END).")
        return "end"
    print(f"[Router] Scout risk score ({risk_sig.risk_score}) exceeds 0.4. Routing to Analyst.")
    return "analyst"

def route_compliance(state: TitanState) -> Literal["notifier", "negotiator", "discarder"]:
    audit = state.get("compliance_audit")
    retry = state.get("retry_count", 0)
    
    if audit and audit.is_compliant:
        print("[Router] Compliance audit PASSED. Routing to Operator Notification.")
        return "notifier"
        
    if retry < 3:
        print(f"[Router] Compliance audit FAILED (Retry {retry}/3). Routing back to Negotiator for edits.")
        return "negotiator"
    else:
        print("[Router] Compliance audit FAILED. Max retry limit (3) exceeded. Routing to Discarder.")
        return "discarder"

def route_human_approval(state: TitanState) -> Literal["sender", "discarder"]:
    action = state.get("human_action")
    if action == "reject":
        print("[Router] Operator REJECTED proposal. Routing to Discarder.")
        return "discarder"
    else:
        print("[Router] Operator APPROVED/EDITED proposal. Routing to SMTP Sender.")
        return "sender"

# Connect Graph Edges
workflow.add_conditional_edges(
    "scout",
    route_scout,
    {
        "analyst": "analyst",
        "end": END
    }
)

workflow.add_edge("analyst", "negotiator")
workflow.add_edge("negotiator", "compliance")

workflow.add_conditional_edges(
    "compliance",
    route_compliance,
    {
        "notifier": "notifier",
        "negotiator": "negotiator",
        "discarder": "discarder"
    }
)

workflow.add_edge("notifier", "human_approval")

workflow.add_conditional_edges(
    "human_approval",
    route_human_approval,
    {
        "sender": "sender",
        "discarder": "discarder"
    }
)

workflow.add_edge("sender", END)
workflow.add_edge("discarder", END)

# Compile Graph with Human Interrupt gate
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["human_approval"]
)

# Test script entry point
if __name__ == "__main__":
    from titan.db.models import init_db
    init_db()
    
    print("\n[Titan Graph] Compiled successfully. Ready to run.")
    config = {"configurable": {"thread_id": "thread-dev-test"}}
    print("Initiating graph pipeline stream...")
    
    # Run from scratch
    for event in app.stream({
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
    }, config):
        print(f"Stream update: {event}")
