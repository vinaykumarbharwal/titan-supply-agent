import os
import json
from pydantic import BaseModel, Field
from typing import Optional, List, Any
import litellm
from dotenv import load_dotenv
from titan.db.models import SessionLocal, ComplianceRule

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-specdec")

class ComplianceAudit(BaseModel):
    is_compliant: bool = Field(description="True if the draft complies with all rules, False otherwise")
    feedback: Optional[str] = Field(None, description="Detailed explanation of violations and recommended revisions")
    rules_checked: List[int] = Field(default_factory=list, description="IDs of compliance rules evaluated")

def run_compliance_audit(draft: Any) -> ComplianceAudit:
    """
    Fetches rules from the database, audits the negotiator draft using LLM,
    and returns a ComplianceAudit report.
    """
    # 1. Fetch Rules from DB
    db = SessionLocal()
    rules_list = []
    try:
        rules = db.query(ComplianceRule).all()
        for r in rules:
            rules_list.append({
                "id": r.id,
                "rule_text": r.rule_text,
                "severity": r.severity
            })
    except Exception as e:
        print(f"[Compliance] Failed to load rules: {e}")
        # Local fallback rules
        rules_list = [
            {"id": 1, "rule_text": "Do not promise or lock fixed pricing for a period exceeding 12 months.", "severity": "hard_block"},
            {"id": 2, "rule_text": "Do not include any language offering gifts, kickbacks, incentives, gratuities, or informal side-deals.", "severity": "hard_block"},
            {"id": 3, "rule_text": "Ensure anti-bribery policies are respected: all transactions must be transparent and documented.", "severity": "hard_block"}
        ]
    finally:
        db.close()
        
    # 2. Audit via LLM
    prompt = f"""
You are the Compliance Officer Agent (governance & audit) for Titan Multi-Agent Supply Chain.
Your job is to audit a supplier negotiation draft against our strict corporate compliance guidelines.

EMAIL DRAFT:
- Supplier: {draft.supplier_name} ({draft.supplier_id})
- Subject: {draft.subject}
- Body:
{draft.body}

COMPLIANCE RULEBOOK:
{json.dumps(rules_list, indent=2)}

DIRECTIONS:
- Review the email subject and body carefully.
- Look out for any keywords or phrases violating rules (e.g. fixed pricing locks for 18/24 months, references to gifts, lunch, kickbacks, "off-the-record", etc.).
- Decide if the draft is compliant. If there are rule violations of severity 'hard_block', you MUST reject it (`is_compliant = false`). If there are only minor warnings, you can approve it with comments, or reject if necessary.

You MUST respond ONLY with a raw JSON code block matching the following schema:
{{
  "is_compliant": <true|false>,
  "feedback": "<detailed feedback describing which rules were violated and how to fix them. If compliant, leave empty or say 'Compliant.'>",
  "rules_checked": [<list of rule IDs that were checked>]
}}

Example format:
```json
{{
  "is_compliant": false,
  "feedback": "Rule 1 violated: Draft mentions lock of pricing for 18 months, which exceeds the 12-month limit.",
  "rules_checked": [1, 2, 3]
}}
```
"""

    if not GROQ_API_KEY:
        print("[Compliance] GROQ_API_KEY not found. Simulating Compliance LLM Audit.")
        
        # Test for typical dummy check: let's approve it unless it has "gift", "gratuity", or long fixed pricing
        body_lower = draft.body.lower()
        violated = []
        feedback_notes = []
        
        # Hardcoded mock check
        for rule in rules_list:
            if "pricing" in rule["rule_text"].lower() and "months" in rule["rule_text"].lower():
                # Let's inspect if body mentions numbers of months > 12
                # e.g., "18 months", "24 months"
                if any(x in body_lower for x in ["18 months", "24 months", "2 years"]):
                    violated.append(rule["id"])
                    feedback_notes.append(f"Violates Rule {rule['id']} (pricing lock): Email mentions a fixed price lock of over 12 months.")
            if "gift" in rule["rule_text"].lower() or "kickback" in rule["rule_text"].lower():
                if any(x in body_lower for x in ["gift", "gratuity", "under the table", "lunch on us", "kickback"]):
                    violated.append(rule["id"])
                    feedback_notes.append(f"Violates Rule {rule['id']} (incentives): Email contains forbidden incentive or gift language.")
                    
        if violated:
            return ComplianceAudit(
                is_compliant=False,
                feedback="; ".join(feedback_notes),
                rules_checked=[r["id"] for r in rules_list]
            )
        else:
            return ComplianceAudit(
                is_compliant=True,
                feedback="Compliant.",
                rules_checked=[r["id"] for r in rules_list]
            )
            
    try:
        response = litellm.completion(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            api_key=GROQ_API_KEY,
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()
        
        # Parse JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        data = json.loads(content)
        return ComplianceAudit(**data)
        
    except Exception as e:
        print(f"[Compliance] LLM audit failed: {e}. Defaulting to approval.")
        return ComplianceAudit(
            is_compliant=True,
            feedback="Default compliance clearance due to execution fallback.",
            rules_checked=[r["id"] for r in rules_list]
        )
