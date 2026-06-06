import os
import json
import yaml
from pydantic import BaseModel, Field
from typing import Optional, Literal, Any
import litellm
from dotenv import load_dotenv
from titan.db.models import SessionLocal, Negotiation, find_similar_negotiations

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-specdec")

class NegotiationDraft(BaseModel):
    supplier_id: str
    supplier_name: str
    to_email: str
    subject: str
    body: str
    discount_requested: float
    compliance_status: Literal["pending", "approved", "rejected"] = "pending"
    rejection_reason: Optional[str] = None

def load_config():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_negotiator_draft(impact_report: Any, feedback: Optional[str] = None) -> NegotiationDraft:
    """
    Drafts a supplier negotiation email. Looks up past negotiations for context,
    and applies compliance feedback if looping back from rejection.
    """
    config = load_config()
    
    # 1. Resolve Supplier Info
    worst_sup_id = impact_report.worst_affected_supplier
    worst_sup_name = impact_report.worst_affected_supplier_name
    
    supplier_info = None
    for sup in config.get("suppliers", []):
        if sup["id"] == worst_sup_id:
            supplier_info = sup
            break
            
    if not supplier_info:
        # Fallback details
        supplier_info = {
            "id": worst_sup_id,
            "name": worst_sup_name,
            "email": f"procurement@{worst_sup_id.lower()}.com",
            "max_discount_ask_pct": 5.0
        }
        
    to_email = supplier_info["email"]
    max_discount = supplier_info["max_discount_ask_pct"]
    
    # Extract recommendation discount ask (parse from recommendation string or default)
    # Default discount is calculated as base_impact
    discount_ask = 3.0
    if "discount of " in impact_report.recommendation:
        try:
            discount_ask = float(impact_report.recommendation.split("discount of ")[1].split("%")[0])
        except Exception:
            pass
    discount_ask = min(discount_ask, max_discount)
    
    # 2. Vector Similarity Search for Past Negotiations
    past_negotiation_text = ""
    db = SessionLocal()
    try:
        from titan.db.models import get_text_embedding
        target_str = f"{worst_sup_id} {impact_report.commodity} discount request"
        target_emb = get_text_embedding(target_str)
        
        sim_records = find_similar_negotiations(db, target_emb, supplier_id=worst_sup_id, limit=2)
        if sim_records:
            past_negotiation_text = "\n\nPAST NEGOTIATIONS FOUND FOR REFERENCE:\n"
            for rec, score in sim_records:
                past_negotiation_text += (
                    f"- Date: {rec.created_at.date()}\n"
                    f"  Outcome: {rec.outcome}\n"
                    f"  Email Draft Snippet: {rec.draft_body[:150]}...\n"
                )
    except Exception as e:
        print(f"[Negotiator] Failed similarity search: {e}")
    finally:
        db.close()
        
    # 3. Formulate the LLM Prompt
    feedback_section = ""
    if feedback:
        feedback_section = f"""
IMPORTANT: The previous email draft was REJECTED by Compliance. You must address the following feedback and rewrite the email:
Compliance Feedback: {feedback}
"""

    prompt = f"""
You are the Negotiator Agent (strategy & sourcing) for Titan Multi-Agent Supply Chain.
Your job is to draft a collaborative and professional supplier negotiation email to {worst_sup_name} ({worst_sup_id}) seeking a bulk discount to offset market spikes.

CONTEXT:
- Risk Event: {impact_report.risk_headline}
- Commodity Impacted: {impact_report.commodity} (Risk Score: {impact_report.risk_score})
- Financial Impact: Overall cost spike of ${impact_report.total_cost_increase:,.2f} calculated across SKUs.
- Suggested Discount to ask: {discount_ask:.2f}% (Supplier Limit: {max_discount}%)
- Contact Email: {to_email}
{past_negotiation_text}
{feedback_section}

RULES:
- Address the email to {worst_sup_name} Procurement Team.
- State the factual reason for the request (e.g. shipping surcharges, commodity index spikes).
- Frame the request as a collaborative partnership to absorb cost shocks together.
- Request exactly {discount_ask:.2f}% discount.
- Keep the tone professional, firm, yet collaborative.
- DO NOT promise fixed pricing beyond 12 months, offer gifts, or write incentive language (Compliance rules).

You MUST output ONLY a JSON code block matching the following schema:
{{
  "supplier_id": "{worst_sup_id}",
  "supplier_name": "{worst_sup_name}",
  "to_email": "{to_email}",
  "subject": "<Compelling and professional email subject line>",
  "body": "<Complete email body, formatted with linebreaks>",
  "discount_requested": {discount_ask:.2f}
}}

Example response structure:
```json
{{
  "supplier_id": "...",
  "supplier_name": "...",
  "to_email": "...",
  "subject": "...",
  "body": "Dear ...,\n\nI hope this email finds you well...\n\nSincerely,\nProcurement Team",
  "discount_requested": ...
}}
```
"""

    if not GROQ_API_KEY:
        print("[Negotiator] GROQ_API_KEY not found. Simulating Negotiator LLM output.")
        mock_subject = f"Urgent: Collaborative Cost-Sharing Proposal - Titan Logistics & {worst_sup_name}"
        mock_body = f"""Dear {worst_sup_name} Procurement Team,

I hope this email finds you well.

We value our long-standing partnership and are writing to discuss recent developments in the logistics market. Due to the recent {impact_report.risk_headline}, we have experienced a significant surge in shipping costs of ${impact_report.total_cost_increase:,.2f} across our shared supply lines.

To maintain our inventory levels and avoid downstream pricing hikes, we are proposing a collaborative cost-sharing initiative. Specifically, we request a temporary discount of {discount_ask:.2f}% on SKU deliveries over the next quarter.

We appreciate your flexibility and commitment to our mutual success. Please let us know when we can hop on a brief call to align on these terms.

Sincerely,
Strategic Sourcing Department
Titan Supply Logistics"""
        
        return NegotiationDraft(
            supplier_id=worst_sup_id,
            supplier_name=worst_sup_name,
            to_email=to_email,
            subject=mock_subject,
            body=mock_body,
            discount_requested=discount_ask,
            compliance_status="pending"
        )
        
    try:
        response = litellm.completion(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            api_key=GROQ_API_KEY,
            temperature=0.7
        )
        content = response.choices[0].message.content.strip()
        
        # Parse JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        data = json.loads(content)
        # Force pending
        data["compliance_status"] = "pending"
        return NegotiationDraft(**data)
        
    except Exception as e:
        print(f"[Negotiator] LLM execution failed: {e}. Returning fallback draft.")
        return run_negotiator_draft(impact_report, feedback=feedback) # Retries once
