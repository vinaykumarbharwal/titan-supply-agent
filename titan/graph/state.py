from typing import TypedDict, Optional, List, Dict, Any
from titan.agents.scout import RiskSignal
from titan.agents.analyst import ImpactReport
from titan.agents.negotiator import NegotiationDraft
from titan.agents.compliance import ComplianceAudit

class TitanState(TypedDict):
    # Core Data Blocks
    risk_signal: Optional[RiskSignal]
    impact_report: Optional[ImpactReport]
    negotiation_draft: Optional[NegotiationDraft]
    compliance_audit: Optional[ComplianceAudit]
    
    # Retry Loop Tracking (Negotiator <-> Compliance)
    feedback: Optional[str]
    retry_count: int
    
    # Human-in-the-Loop Gateway Inputs
    human_action: Optional[str]            # 'approve' | 'reject' | 'edit'
    human_edited_subject: Optional[str]
    human_edited_body: Optional[str]
    
    # Final Output Status
    outcome: Optional[str]                 # 'sent' | 'rejected' | 'discarded' | 'pending_approval'
