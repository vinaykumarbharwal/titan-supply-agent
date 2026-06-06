import os
import requests
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def search_news(query: str, max_results: int = 5):
    """
    Queries Tavily for supply chain risk news. 
    Falls back to mock news data if TAVILY_API_KEY is not set.
    """
    if TAVILY_API_KEY:
        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "news",
                "max_results": max_results
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])
            return [
                {
                    "title": r.get("title", ""),
                    "content": r.get("content", ""),
                    "url": r.get("url", ""),
                    "published_date": r.get("published_date", "Recent")
                }
                for r in results
            ]
        except Exception as e:
            print(f"Error calling Tavily: {e}. Falling back to mock news...")
            
    # Mock fallback news based on typical keywords
    query_lower = query.lower()
    if "oil" in query_lower or "fuel" in query_lower:
        return [
            {
                "title": "Global Brent Crude Surges 6.2% Amid Red Sea Transit Delays",
                "content": "Oil prices surged past $84 per barrel as multiple container vessels reroute around the Cape of Good Hope, adding 10-14 days to major European and American shipping lanes. Surcharges are expected to increase fuel shipping costs globally.",
                "url": "https://mocknews.supplychain.com/oil-surge-red-sea",
                "published_date": "2026-06-06"
            },
            {
                "title": "OPEC+ Signals Continued Production Cuts through Q3",
                "content": "Members of OPEC+ have agreed to extend their voluntary oil production cuts of 2.2 million barrels per day. This is putting upward pressure on energy costs and industrial logistics contracts.",
                "url": "https://mocknews.supplychain.com/opec-production-cuts",
                "published_date": "2026-06-05"
            }
        ]
    elif "strike" in query_lower or "port" in query_lower:
        return [
            {
                "title": "East Coast Ports Face Imminent Strike After Union Talks Stall",
                "content": "Negotiations between the Longshoremen Association and port operators broke down this morning, threatening a full shutdown of 14 major ports from Maine to Texas. Logistics planners warn of backlogs that could take weeks to resolve.",
                "url": "https://mocknews.supplychain.com/port-strike-threat",
                "published_date": "2026-06-06"
            }
        ]
    elif "shortage" in query_lower or "commodity" in query_lower or "copper" in query_lower:
        return [
            {
                "title": "Copper Smelter Outages Trigger Supply Crunch in South America",
                "content": "Unplanned maintenance at two of the world's largest copper smelters has constricted refined copper supplies. Base metals indexes rose by 11%, impacting electronics and construction component costs.",
                "url": "https://mocknews.supplychain.com/copper-shortage-smelter",
                "published_date": "2026-06-06"
            }
        ]
    else:
        return [
            {
                "title": "Global Logistics Indexes Report Moderately Higher Shipping Friction",
                "content": "The global shipping index rose 2.1% this week due to cumulative delays across the Panama Canal and European rail lines. Supply chains remain sensitive to geopolitical tensions.",
                "url": "https://mocknews.supplychain.com/shipping-friction",
                "published_date": "2026-06-06"
            }
        ]
