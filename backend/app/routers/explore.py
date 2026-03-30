from fastapi import APIRouter, Depends, Query
from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.models.user import UserOut
from app.models.trip import TripOut, TripVisibility

router = APIRouter(tags=["explore"])


@router.get("/explore", response_model=list[TripOut])
async def explore_public_trips(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    tag: str | None = None,
):
    db = await get_db()
    query: dict = {"visibility": TripVisibility.public}
    if tag:
        query["tags"] = tag
    docs = await db.find_many(
        "trips",
        query,
        skip=skip,
        limit=limit,
        sort=[("created_at", -1)],
    )
    return [TripOut.from_doc(d) for d in docs]


@router.post("/trips/{trip_id}/fork", response_model=TripOut, status_code=201)
async def fork_trip(
    trip_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    """Copy a public trip into the current user's account."""
    from datetime import datetime, timezone

    db = await get_db()
    original = await db.find_one("trips", {"_id": trip_id})
    if not original or original.get("visibility") != TripVisibility.public:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Public trip not found")

    now = datetime.now(timezone.utc)
    fork_data = {
        "owner_id": current_user.id,
        "title": f"{original['title']} (fork)",
        "description": original.get("description"),
        "root_node_id": None,
        "visibility": TripVisibility.private,
        "collaborators": [],
        "total_budget": original.get("total_budget"),
        "currency": original.get("currency", "INR"),
        "tags": original.get("tags", []),
        "status": "dream",
        "ai_enhanced": False,
        "forked_from": trip_id,
        "created_at": now,
        "updated_at": now,
    }
    forked_id = await db.insert_one("trips", fork_data)

    # Deep-copy nodes
    async def _copy_nodes(src_parent: str | None, dst_parent: str | None):
        children = await db.find_many(
            "nodes",
            {"trip_id": trip_id, "parent_id": src_parent},
            sort=[("order", 1)],
        )
        for node in children:
            new_node = {k: v for k, v in node.items() if k != "_id"}
            new_node["trip_id"] = forked_id
            new_node["parent_id"] = dst_parent
            new_node["status"] = "pending"
            new_node["ai_summary"] = None
            new_node["created_at"] = now
            new_node["updated_at"] = now
            new_id = await db.insert_one("nodes", new_node)

            if dst_parent is None and not (await db.find_one("trips", {"_id": forked_id})).get("root_node_id"):
                await db.update_one("trips", {"_id": forked_id}, {"root_node_id": new_id})

            await _copy_nodes(node["_id"], new_id)

    await _copy_nodes(None, None)

    forked = await db.find_one("trips", {"_id": forked_id})
    return TripOut.from_doc(forked)
