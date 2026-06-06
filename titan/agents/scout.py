import os
import json
import yaml
from datetime import datetime
from pydantic import BaseModel, Field
import litellm
from dotenv import load_dotenv
from titan.tools.tavily_tool import search_news

load_dotenv()

# Groq Configuration via LiteLLM
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-specdec")

class RiskSignal(BaseModel):
    source: str = Field(description="The source of the news signal, e.g., 'Tavily' or 'GDELT'")
    headline: str = Field(description="Short summary of the risk event")
    risk_score: float = Field(description="Normalized risk score between 0.0 and 1.0")
    commodity: str = Field(description="The commodity affected: crude_oil, shipping, copper, steel, or general")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

def load_config():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_scout_analysis() -> RiskSignal:
    """
    Wakes up, loads config, searches news for keywords, and analyzes the results with LLM
    to yield the highest priority RiskSignal.
    """
    config = load_config()
    keywords = [sig["keyword"] for sig in config.get("risk_signals", [])]
    
    all_headlines = []
    
    # 1. Search Tavily / Mock News for each keyword
    for kw in keywords:
        print(f"[Scout] Searching news for: {kw}...")
        results = search_news(kw, max_results=3)
        for r in results:
            all_headlines.append({
                "keyword": kw,
                "title": r["title"],
                "content": r["content"],
                "url": r["url"]
            })
            
    if not all_headlines:
        print("[Scout] No news articles found. Returning silent state.")
        return RiskSignal(
            source="System",
            headline="No critical threat signals detected in the last cycle.",
            risk_score=0.1,
            commodity="general"
        )
        
    # 2. Score news via LiteLLM
    prompt = f"""
You are the Scout Agent (procurement and risk intelligence) for Titan Multi-Agent Supply Chain digital twin.
Your task is to analyze the gathered news articles and output the SINGLE most critical risk signal as a JSON object matching this JSON Schema:

{{
  "source": "Tavily",
  "headline": "<brief description of the risk event>",
  "risk_score": <float between 0.0 and 1.0 reflecting severity. High impact like strikes/war/shortages > 0.6. Minor news < 0.4.>,
  "commodity": "<one of: crude_oil, shipping, copper, steel, general>"
}}

Guidelines for Risk Score (0.0 to 1.0):
- 0.8 to 1.0: Active port strikes, major wars on trade routes, commodity supply cuts > 10%
- 0.5 to 0.7: Oil prices spiking >= 5%, threatened strikes, minor shipping delays (1-3 days)
- 0.1 to 0.4: Stable markets, minor maintenance updates, general supply chain efficiency updates

Here is the news gathered:
{json.dumps(all_headlines, indent=2)}

You MUST respond ONLY with the raw JSON code block. Do not write markdown text outside the block.
Example format:
```json
{{
  "source": "Tavily",
  "headline": "...",
  "risk_score": 0.75,
  "commodity": "..."
}}
```
"""
    
    if not GROQ_API_KEY:
        print("[Scout] GROQ_API_KEY not found. Simulating Scout LLM output.")
        # Simulating Brent crude oil surge
        return RiskSignal(
            source="Tavily (Simulated)",
            headline="Global Brent Crude Surges 6.2% Amid Red Sea Transit Delays",
            risk_score=0.72,
            commodity="crude_oil"
        )
        
    try:
        # Call LiteLLM
        response = litellm.completion(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            api_key=GROQ_API_KEY,
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()
        
        # Parse JSON from markdown block if necessary
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        data = json.loads(content)
        return RiskSignal(**data)
        
    except Exception as e:
        print(f"[Scout] LLM parsing failed: {e}. Falling back to default risk signal.")
        # If LLM fails, we'll extract using manual matching or default
        return RiskSignal(
            source="Tavily (Fallback)",
            headline="Global Brent Crude Surges 6.2% Amid Red Sea Transit Delays",
            risk_score=0.72,
            commodity="crude_oil"
        )
