import os
from typing import Dict, Any
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from titan.graph.state import TitanState
from titan.agents.scout import run_scout_analysis
from titan.agents.analyst import run_analyst_analysis
from titan.agents.negotiator import run_negotiator_draft
from titan.agents.compliance import run_compliance_audit
from titan.tools.gmail_tool import send_email
from titan.db.models import SessionLocal, Negotiation, get_text_embedding

load_dotenv()

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def scout_node(state: TitanState) -> Dict[str, Any]:
    print("\n--- [NODE] SCOUT: SCANNING THREAT INTELLIGENCE ---")
    risk_sig = run_scout_analysis()
    print(f"Scout Result: {risk_sig.headline} (Score: {risk_sig.risk_score})")
    return {"risk_signal": risk_sig}

def analyst_node(state: TitanState) -> Dict[str, Any]:
    print("\n--- [NODE] ANALYST: CALCULATING MARGIN DEGRADATION ---")
    risk_sig = state.get("risk_signal")
    if not risk_sig:
        raise ValueError("No RiskSignal found in state for Analyst node.")
    report = run_analyst_analysis(risk_sig)
    print(f"Analyst Result: worst affected supplier is {report.worst_affected_supplier_name} ({report.worst_affected_supplier})")
    print(f"Projected Total Cost Delta: ${report.total_cost_increase:,.2f}")
    return {"impact_report": report}

def negotiator_node(state: TitanState) -> Dict[str, Any]:
    print("\n--- [NODE] NEGOTIATOR: DRAFTING COMMERCIAL PROPOSAL ---")
    report = state.get("impact_report")
    feedback = state.get("feedback")
    retry = state.get("retry_count", 0)
    
    if not report:
        raise ValueError("No ImpactReport found in state for Negotiator node.")
        
    draft = run_negotiator_draft(report, feedback=feedback)
    print(f"Negotiator Result: Drafted email to {draft.to_email} seeking {draft.discount_requested}% discount.")
    return {
        "negotiation_draft": draft,
        "retry_count": retry + 1,
        "feedback": None # Reset feedback
    }

def compliance_node(state: TitanState) -> Dict[str, Any]:
    print("\n--- [NODE] COMPLIANCE: AUDITING CORRESPONDENCE ---")
    draft = state.get("negotiation_draft")
    if not draft:
        raise ValueError("No NegotiationDraft found in state for Compliance node.")
        
    audit = run_compliance_audit(draft)
    print(f"Compliance Result: Compliant={audit.is_compliant}. Feedback: {audit.feedback}")
    
    # Set feedback if rejected to instruct negotiator
    fb = None if audit.is_compliant else audit.feedback
    return {
        "compliance_audit": audit,
        "feedback": fb
    }

def human_notification_node(state: TitanState) -> Dict[str, Any]:
    print("\n--- [NODE] NOTIFIER: TRIGGERING HUMAN APPROVAL STAGE ---")
    draft = state.get("negotiation_draft")
    report = state.get("impact_report")
    
    # Create Slack Block message if Slack URL is specified
    message_text = (
        f"🚨 *Titan Multi-Agent War Room Notice* 🚨\n"
        f"A negotiation proposal is ready for your review!\n"
        f"*Supplier:* {draft.supplier_name} ({draft.supplier_id})\n"
        f"*Target Discount:* {draft.discount_requested}%\n"
        f"*Margin Impact:* ${report.total_cost_increase:,.2f} cost increase.\n"
        f"Please open your Chainlit Portal to review, edit, or approve this draft."
    )
    
    if SLACK_WEBHOOK_URL:
        try:
            payload = {
                "text": message_text,
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": message_text}
                    }
                ]
            }
            res = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
            if res.status_code == 200:
                print("[Slack Alert] Webhook sent successfully.")
            else:
                print(f"[Slack Alert] Webhook failed with status: {res.status_code}")
        except Exception as e:
            print(f"[Slack Alert] Error executing webhook: {e}")
    else:
        print("[Notifier Console] Slack hook not configured. Printing alert notification details:")
        print(message_text)
        
    return {"outcome": "pending_approval"}

def human_approval_node(state: TitanState) -> Dict[str, Any]:
    # This node executes directly after the interrupt is resolved.
    # It reads inputs from state and logs the decision.
    action = state.get("human_action", "approve")
    print(f"\n--- [NODE] HUMAN RESUME: ACTION REGISTERED -> {action.upper()} ---")
    return {}

def email_node(state: TitanState) -> Dict[str, Any]:
    print("\n--- [NODE] ACTIONS: DISPATCHING CORRESPONDENCE ---")
    draft = state.get("negotiation_draft")
    report = state.get("impact_report")
    risk = state.get("risk_signal")
    
    subject = state.get("human_edited_subject") or draft.subject
    body = state.get("human_edited_body") or draft.body
    
    # 1. Send Email
    print(f"Sending email to {draft.to_email}...")
    email_status = send_email(draft.to_email, subject, body)
    
    # 2. Log negotiation outcome and embed state into database
    db = SessionLocal()
    try:
        # Generate semantic memory embedding for similarity search
        embedding_text = f"{draft.supplier_id} {report.commodity} discount request approved"
        embedding_vector = get_text_embedding(embedding_text)
        
        negotiation_log = Negotiation(
            supplier_id=draft.supplier_id,
            risk_signal=risk.dict() if risk else None,
            impact_report=report.dict() if report else None,
            draft_body=body,
            embedding=json.dumps(embedding_vector),
            outcome="sent"
        )
        db.add(negotiation_log)
        db.commit()
        print("[Database Log] Successfully committed negotiation transcript to semantic memories.")
    except Exception as e:
        db.rollback()
        print(f"[Database Error] Could not commit negotiation transcript: {e}")
    finally:
        db.close()
        
    return {"outcome": "sent"}

def discard_node(state: TitanState) -> Dict[str, Any]:
    print("\n--- [NODE] ACTIONS: DISCARDING NEGOTIATION PROPOSAL ---")
    draft = state.get("negotiation_draft")
    report = state.get("impact_report")
    risk = state.get("risk_signal")
    
    db = SessionLocal()
    try:
        # Log negotiation outcome as discarded in database without writing heavy embedding
        negotiation_log = Negotiation(
            supplier_id=draft.supplier_id,
            risk_signal=risk.dict() if risk else None,
            impact_report=report.dict() if report else None,
            draft_body=draft.body,
            embedding=json.dumps([0.0] * 1536),
            outcome="discarded"
        )
        db.add(negotiation_log)
        db.commit()
        print("[Database Log] Logged draft rejection and closed thread.")
    except Exception as e:
        db.rollback()
        print(f"[Database Error] Could not commit rejection log: {e}")
    finally:
        db.close()
        
    return {"outcome": "discarded"}
