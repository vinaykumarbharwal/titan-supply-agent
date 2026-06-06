import os
import pandas as pd
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class SKUImpact(BaseModel):
    sku: str
    supplier_id: str
    supplier_name: str
    commodity: str
    original_cost: float
    new_cost: float
    cost_increase: float
    original_margin: float
    new_margin: float
    margin_drop: float

class ImpactReport(BaseModel):
    risk_headline: str
    commodity: str
    risk_score: float
    total_cost_increase: float
    worst_affected_supplier: str
    worst_affected_supplier_name: str
    affected_skus: List[SKUImpact]
    recommendation: str

def run_analyst_analysis(risk_signal: Any) -> ImpactReport:
    """
    Loads supplier SKU details, calculates margin impact of risk signals,
    and returns a structured ImpactReport.
    """
    csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "suppliers_sku.csv"))
    
    # Check if CSV exists
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Internal supplier SKU database not found at: {csv_path}")
        
    df = pd.read_csv(csv_path)
    
    risk_score = risk_signal.risk_score
    commodity = risk_signal.commodity
    
    affected_skus_list = []
    total_cost_increase = 0.0
    
    # Financial Impact Calculations
    for _, row in df.iterrows():
        base_cost = float(row["base_cost"])
        base_shipping = float(row["base_shipping"])
        margin_pct = float(row["margin_pct"])
        row_commodity = row["commodity"]
        
        original_total_cost = base_cost + base_shipping
        
        # Fixed Sales Price calculated from original margin
        # margin_pct = (Price - Cost) / Price => Cost = Price * (1 - margin_pct) => Price = Cost / (1 - margin_pct)
        sales_price = original_total_cost / (1 - margin_pct) if margin_pct < 1 else original_total_cost * 1.25
        
        # Calculate new costs based on the risk event
        new_base_cost = base_cost
        new_base_shipping = base_shipping
        
        if commodity == "crude_oil":
            # Crude oil spikes shipping costs across the board by up to 50%
            new_base_shipping = base_shipping * (1.0 + (risk_score * 0.5))
            # And increases crude_oil commodity costs specifically by up to 30%
            if row_commodity == "crude_oil":
                new_base_cost = base_cost * (1.0 + (risk_score * 0.3))
                
        elif commodity == "shipping":
            # Shipping disruption increases shipping costs by up to 80%
            new_base_shipping = base_shipping * (1.0 + (risk_score * 0.8))
            
        elif commodity in ["copper", "steel"]:
            # Specifc base metals increase their cost by up to 40%
            if row_commodity == commodity:
                new_base_cost = base_cost * (1.0 + (risk_score * 0.4))
                
        else:
            # General minor friction (increases shipping slightly)
            new_base_shipping = base_shipping * (1.0 + (risk_score * 0.15))
            
        new_total_cost = new_base_cost + new_base_shipping
        cost_increase = new_total_cost - original_total_cost
        total_cost_increase += cost_increase
        
        # Calculate new margin percentage
        new_margin = (sales_price - new_total_cost) / sales_price
        margin_drop = margin_pct - new_margin
        
        affected_skus_list.append(
            SKUImpact(
                sku=row["sku"],
                supplier_id=row["supplier_id"],
                supplier_name=row["supplier_name"],
                commodity=row_commodity,
                original_cost=round(original_total_cost, 2),
                new_cost=round(new_total_cost, 2),
                cost_increase=round(cost_increase, 2),
                original_margin=round(margin_pct, 4),
                new_margin=round(new_margin, 4),
                margin_drop=round(margin_drop, 4)
            )
        )
        
    # Find the supplier with the worst margin degradation
    supplier_drops = {}
    supplier_names = {}
    for sku_imp in affected_skus_list:
        sup_id = sku_imp.supplier_id
        supplier_names[sup_id] = sku_imp.supplier_name
        supplier_drops[sup_id] = supplier_drops.get(sup_id, 0.0) + sku_imp.margin_drop
        
    worst_supplier = max(supplier_drops, key=supplier_drops.get) if supplier_drops else "N/A"
    worst_supplier_name = supplier_names.get(worst_supplier, "N/A")
    
    # Generate recommendations based on the calculations
    rec_skus = [s for s in affected_skus_list if s.supplier_id == worst_supplier and s.cost_increase > 0]
    if rec_skus:
        # Suggest asking for a discount equal to the cost increase pct or margin drop
        target_sku = rec_skus[0]
        rec_discount = (target_sku.cost_increase / target_sku.original_cost) * 100
        rec_discount = min(rec_discount, 5.0) # Cap requested discount at 5% as per standard negotiations
        recommendation = (
            f"Initiate negotiation with {worst_supplier_name} ({worst_supplier}). "
            f"Request a discount of {rec_discount:.1f}% on SKU {target_sku.sku} to offset the "
            f"${target_sku.cost_increase:.2f}/unit cost spike from {commodity} shipping inflation."
        )
    else:
        recommendation = "No substantial margin degradation detected. Maintain current contracts."
        
    return ImpactReport(
        risk_headline=risk_signal.headline,
        commodity=commodity,
        risk_score=risk_score,
        total_cost_increase=round(total_cost_increase, 2),
        worst_affected_supplier=worst_supplier,
        worst_affected_supplier_name=worst_supplier_name,
        affected_skus=affected_skus_list,
        recommendation=recommendation
    )
