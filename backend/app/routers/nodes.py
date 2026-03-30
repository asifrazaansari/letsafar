from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.models.user import UserOut
from app.models.node import NodeCreate, NodeUpdate, NodeMoveRequest, NodeOut
from app.routers.trips import _check_trip_access

router = APIRouter(tags=["nodes"])


async def _build_tree(db, trip_id: str, parent_id=None) -> list[NodeOut]:
    """Recursively build the node tree for a trip."""
    query = {"trip_id": trip_id, "parent_id": parent_id}
    docs = await db.find_many("nodes", query, sort=[("order", 1)])
    result = []
    for doc in docs:
        children = await _build_tree(db, trip_id, doc["_id"])
        result.append(NodeOut.from_doc(doc, children=children))
    return result


@router.get("/trips/{trip_id}/nodes", response_model=list[NodeOut])
async def get_nodes(
    trip_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    trip = await db.find_one("trips", {"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    _check_trip_access(trip, current_user.id, "viewer")
    return await _build_tree(db, trip_id)


@router.post("/trips/{trip_id}/nodes", response_model=NodeOut, status_code=status.HTTP_201_CREATED)
async def create_node(
    trip_id: str,
    payload: NodeCreate,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    trip = await db.find_one("trips", {"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    _check_trip_access(trip, current_user.id, "editor")

    now = datetime.now(timezone.utc)
    node_data = {
        **payload.model_dump(mode="json"),
        "trip_id": trip_id,
        "status": "pending",
        "ai_summary": None,
        "created_at": now,
        "updated_at": now,
    }
    node_id = await db.insert_one("nodes", node_data)

    # If this is the first node (no root_node_id) and it's a root node, set it
    if not trip.get("root_node_id") and not payload.parent_id:
        await db.update_one("trips", {"_id": trip_id}, {"root_node_id": node_id})

    node_doc = await db.find_one("nodes", {"_id": node_id})
    return NodeOut.from_doc(node_doc)


@router.put("/nodes/{node_id}", response_model=NodeOut)
async def update_node(
    node_id: str,
    payload: NodeUpdate,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    node = await db.find_one("nodes", {"_id": node_id})
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    trip = await db.find_one("trips", {"_id": node["trip_id"]})
    _check_trip_access(trip, current_user.id, "editor")

    updates = payload.model_dump(exclude_none=True, mode="json")
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.update_one("nodes", {"_id": node_id}, updates)
    updated = await db.find_one("nodes", {"_id": node_id})
    return NodeOut.from_doc(updated)


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    node_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    """Delete node and recursively all its descendants."""
    db = await get_db()
    node = await db.find_one("nodes", {"_id": node_id})
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    trip = await db.find_one("trips", {"_id": node["trip_id"]})
    _check_trip_access(trip, current_user.id, "editor")

    async def _delete_subtree(nid: str):
        children = await db.find_many("nodes", {"parent_id": nid})
        for child in children:
            await _delete_subtree(child["_id"])
        await db.delete_one("nodes", {"_id": nid})
        await db.delete_many("comments", {"node_id": nid})

    await _delete_subtree(node_id)

    # If this was the root node, clear it from the trip
    if trip.get("root_node_id") == node_id:
        await db.update_one("trips", {"_id": node["trip_id"]}, {"root_node_id": None})


@router.patch("/nodes/{node_id}/move", response_model=NodeOut)
async def move_node(
    node_id: str,
    payload: NodeMoveRequest,
    current_user: UserOut = Depends(get_current_user),
):
    """Drag-and-drop reorder: change parent and/or order."""
    db = await get_db()
    node = await db.find_one("nodes", {"_id": node_id})
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    trip = await db.find_one("trips", {"_id": node["trip_id"]})
    _check_trip_access(trip, current_user.id, "editor")

    # Guard: a node cannot be moved under itself or its own descendant
    if payload.new_parent_id == node_id:
        raise HTTPException(status_code=400, detail="Cannot move node under itself")

    updates = {
        "parent_id": payload.new_parent_id,
        "order": payload.new_order,
        "updated_at": datetime.now(timezone.utc),
    }
    await db.update_one("nodes", {"_id": node_id}, updates)
    updated = await db.find_one("nodes", {"_id": node_id})
    return NodeOut.from_doc(updated)
