from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.models.user import UserOut
from app.routers.trips import _check_trip_access

router = APIRouter(prefix="/trips", tags=["costs"])


@router.get("/{trip_id}/costs")
async def get_cost_summary(
    trip_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    trip = await db.find_one("trips", {"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    _check_trip_access(trip, current_user.id, "viewer")

    nodes = await db.find_many("nodes", {"trip_id": trip_id})

    total = sum(n.get("cost") or 0 for n in nodes)
    breakdown = [
        {
            "node_id": n["_id"],
            "name": n["name"],
            "cost": n.get("cost"),
            "cost_split": n.get("cost_split"),
        }
        for n in nodes
        if n.get("cost") is not None
    ]

    # Aggregate per-person totals from split configs
    person_totals: dict[str, float] = {}
    for n in nodes:
        split = n.get("cost_split")
        if not split or not n.get("cost"):
            continue
        cost = n["cost"]
        travelers = split.get("travelers", [])
        split_type = split.get("type", "equal")
        if not travelers:
            continue
        if split_type == "equal":
            per = cost / len(travelers)
            for t in travelers:
                name = t.get("name", "Unknown")
                person_totals[name] = person_totals.get(name, 0) + per
        elif split_type in ("custom", "percent"):
            for t in travelers:
                name = t.get("name", "Unknown")
                amount = t.get("share", 0)
                if split_type == "percent":
                    amount = cost * amount / 100
                person_totals[name] = person_totals.get(name, 0) + amount

    return {
        "trip_id": trip_id,
        "currency": trip.get("currency", "INR"),
        "total_cost": total,
        "budget": trip.get("total_budget"),
        "breakdown": breakdown,
        "per_person": person_totals,
    }
