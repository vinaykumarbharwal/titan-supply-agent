import os
import sys
from dotenv import load_dotenv

# Ensure the root workspace is in the python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Load environment
load_dotenv()

from titan.db.models import init_db
from titan.graph.graph import app as graph_app

def print_divider(title):
    print("\n" + "=" * 50)
    print(f" {title} ")
    print("=" * 50)

def main():
    # 1. Initialize DB tables and seed rules
    print_divider("DATABASE INITIALIZATION")
    init_db()
    
    # 2. Setup Thread configuration
    thread_id = "cli-test-thread-101"
    config = {"configurable": {"thread_id": thread_id}}
    
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
    
    print_divider("STARTING AUTOMATED WAR ROOM CYCLE")
    print(f"Executing Multi-Agent Graph stream under Thread ID: {thread_id}...\n")
    
    # Run the pipeline until it hits the interrupt node
    try:
        for event in graph_app.stream(initial_state, config, stream_mode="values"):
            # We can stream and print state attributes as they populate
            state = event
            
        print("\n[Pipeline] Interrupt encountered. The state graph is paused and saved.")
        
        # Retrieve the paused state details
        state_data = graph_app.get_state(config).values
        risk = state_data.get("risk_signal")
        report = state_data.get("impact_report")
        draft = state_data.get("negotiation_draft")
        audit = state_data.get("compliance_audit")
        
        # Display paused report
        print_divider("WAR ROOM ACTION BOARD (PAUSED)")
        print(f"🚨 SCOUT RISK DETECTED: {risk.headline if risk else 'None'}")
        print(f"   Commodity: {risk.commodity if risk else 'None'} | Risk Score: {risk.risk_score if risk else 0.0}")
        print(f"📊 ANALYST ESTIMATED LOSS: ${report.total_cost_increase:,.2f} cost increase across suppliers.")
        print(f"   Recommendation: {report.recommendation if report else 'None'}")
        print(f"📝 NEGOTIATOR DRAFT TO {draft.to_email if draft else 'None'}:")
        print(f"   Subject: {draft.subject if draft else 'None'}")
        print(f"   Body Preview: {draft.body[:250] if draft else 'None'}...\n")
        print(f"✅ COMPLIANCE REPORT: Compliant={audit.is_compliant if audit else False}")
        print(f"   Feedback: {audit.feedback if audit else 'None'}")
        
        print_divider("HUMAN INTERRUPT GATEWAY")
        print("Please choose an option to resolve the pause:")
        print("  [A] Approve & Send Email")
        print("  [R] Reject & Discard Proposal")
        print("  [E] Edit Email Body Inline")
        
        choice = input("Enter choice (A / R / E): ").strip().upper()
        
        action = "approve"
        edited_body = None
        
        if choice == "R":
            action = "reject"
            print("\nDiscarding proposal...")
        elif choice == "E":
            action = "edit"
            print("\n--- Original Body ---")
            print(draft.body)
            print("-" * 21)
            edited_body = input("Type or paste your new email body:\n")
            print("\nSaving modifications and resuming...")
        else:
            print("\nApproving proposal & queueing send task...")
            
        # 3. Update Graph state and resume execution
        graph_app.update_state(config, {
            "human_action": action,
            "human_edited_body": edited_body
        }, as_node="human_approval")
        
        print("\nResuming state graph execution thread...")
        for event in graph_app.stream(None, config, stream_mode="values"):
            state = event
            
        # 4. Check final outcome
        final_state = graph_app.get_state(config).values
        print_divider("WAR ROOM CYCLE COMPLETE")
        print(f"Final Thread Outcome: {final_state.get('outcome').upper()}")
        print("Done!")
        
    except KeyboardInterrupt:
        print("\nExecution aborted.")
    except Exception as e:
        print(f"\n❌ Pipeline failed with error: {e}")

if __name__ == "__main__":
    main()
