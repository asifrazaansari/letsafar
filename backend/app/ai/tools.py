"""
MCP-style tool definitions for the Rihla AI agents.
Each tool is a plain async function decorated with @tool from LangChain.
"""
from langchain_core.tools import tool
from typing import Any


@tool
async def get_trip_tree(trip_id: str) -> dict:
    """
    Fetch the full destination tree for a given trip.
    Returns a flat list of nodes with their parent/child relationships.
    """
    from app.db.mongo import get_db
    try:
        db = await get_db()
        nodes = await db.find_many("nodes", {"trip_id": trip_id}, limit=200)
        return {"nodes": nodes, "count": len(nodes)}
    except Exception as e:
        return {"error": str(e), "nodes": []}


@tool
async def update_node(node_id: str, updates: dict) -> dict:
    """
    Update a destination node with new AI-generated content.
    Allowed fields: ai_summary, notes, cost, arrival, departure.
    """
    from app.db.mongo import get_db
    ALLOWED = {"ai_summary", "notes", "cost", "arrival", "departure"}
    safe_updates = {k: v for k, v in updates.items() if k in ALLOWED}
    if not safe_updates:
        return {"error": "No allowed fields to update"}
    try:
        db = await get_db()
        ok = await db.update_one("nodes", {"_id": node_id}, safe_updates)
        return {"ok": ok, "updated_fields": list(safe_updates.keys())}
    except Exception as e:
        return {"error": str(e)}


@tool
async def search_place(query: str, location: str = "") -> dict:
    """
    Search for information about a place, attraction, or service.
    Returns description, tips, and practical info.
    """
    import httpx
    # Uses a mock/placeholder — replace with a real maps/search API
    search_term = f"{query} {location}".strip()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": search_term, "format": "json", "limit": 3},
                headers={"User-Agent": "Rihla/1.0"},
            )
            data = resp.json()
            return {
                "results": [
                    {
                        "name": r.get("display_name", ""),
                        "lat": r.get("lat"),
                        "lon": r.get("lon"),
                        "type": r.get("type"),
                    }
                    for r in data[:3]
                ]
            }
    except Exception as e:
        return {"error": str(e), "results": []}


@tool
async def get_prayer_times(city: str, country: str, date: str = "") -> dict:
    """
    Get Islamic prayer times for a city on a specific date (YYYY-MM-DD).
    Uses the Aladhan API.
    """
    import httpx
    from datetime import date as dtdate
    d = date or dtdate.today().isoformat()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.aladhan.com/v1/timingsByCity",
                params={"city": city, "country": country, "date": d, "method": 2},
            )
            data = resp.json()
            timings = data.get("data", {}).get("timings", {})
            return {
                "date": d,
                "city": city,
                "country": country,
                "fajr": timings.get("Fajr"),
                "dhuhr": timings.get("Dhuhr"),
                "asr": timings.get("Asr"),
                "maghrib": timings.get("Maghrib"),
                "isha": timings.get("Isha"),
                "friday_prayer": timings.get("Jumu'ah"),
            }
    except Exception as e:
        return {"error": str(e)}


@tool
async def calculate_cost_split(
    total_amount: float,
    currency: str,
    travellers: list[str],
    custom_splits: dict | None = None,
) -> dict:
    """
    Calculate how to split a cost among travellers.
    custom_splits: dict mapping traveller name → percentage (0–100).
    If not provided, splits equally.
    """
    n = len(travellers)
    if n == 0:
        return {"error": "No travellers provided"}

    if custom_splits:
        total_pct = sum(custom_splits.values())
        if abs(total_pct - 100) > 0.01:
            return {"error": f"Custom splits must sum to 100, got {total_pct}"}
        splits = {
            name: round((pct / 100) * total_amount, 2)
            for name, pct in custom_splits.items()
        }
    else:
        equal_share = round(total_amount / n, 2)
        splits = {name: equal_share for name in travellers}

    return {
        "currency": currency,
        "total": total_amount,
        "per_person": splits,
        "method": "custom" if custom_splits else "equal",
    }


@tool
async def get_weather(city: str, country: str, date: str = "") -> dict:
    """
    Get weather forecast for a city on a date.
    Returns temperature range, conditions, and travel tips.
    """
    # Placeholder — in production use OpenWeatherMap or similar
    from datetime import date as dtdate
    d = date or dtdate.today().isoformat()
    return {
        "city": city,
        "date": d,
        "note": "Weather integration requires OPENWEATHERMAP_API_KEY in environment",
        "temp_min_c": None,
        "temp_max_c": None,
        "condition": "unavailable",
    }


# All tools available to agents
ALL_TOOLS = [
    get_trip_tree,
    update_node,
    search_place,
    get_prayer_times,
    calculate_cost_split,
    get_weather,
]
