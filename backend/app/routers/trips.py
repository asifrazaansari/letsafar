from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.models.user import UserOut
from app.models.trip import TripCreate, TripUpdate, TripOut, TripVisibility

router = APIRouter(prefix="/trips", tags=["trips"])


def _check_trip_access(trip: dict, user_id: str, require_role: str = "viewer") -> None:
    """Raise 403 if the user doesn't have the required access level."""
    ROLE_HIERARCHY = {"viewer": 0, "commenter": 1, "editor": 2, "owner": 3}
    min_level = ROLE_HIERARCHY.get(require_role, 0)

    if trip["owner_id"] == user_id:
        return  # owner has all access

    if trip.get("visibility") == TripVisibility.public and require_role == "viewer":
        return

    for collab in trip.get("collaborators", []):
        if collab["user_id"] == user_id and collab.get("accepted"):
            if ROLE_HIERARCHY.get(collab["role"], -1) >= min_level:
                return

    raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.get("", response_model=list[TripOut])
async def list_trips(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserOut = Depends(get_current_user),
):
    """List all trips owned by or shared with the current user."""
    db = await get_db()
    # own trips + trips where user is a collaborator
    owned = await db.find_many(
        "trips",
        {"owner_id": current_user.id},
        skip=skip,
        limit=limit,
        sort=[("created_at", -1)],
    )
    shared = await db.find_many(
        "trips",
        {
            "collaborators": {
                "$elemMatch": {
                    "user_id": current_user.id,
                    "accepted": True,
                }
            }
        },
        skip=0,
        limit=limit,
    )
    all_trips = {doc["_id"]: doc for doc in owned + shared}
    return [TripOut.from_doc(doc) for doc in all_trips.values()]


@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
async def create_trip(
    payload: TripCreate,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    now = datetime.now(timezone.utc)
    trip_data = {
        **payload.model_dump(),
        "owner_id": current_user.id,
        "root_node_id": None,
        "collaborators": [],
        "ai_enhanced": False,
        "created_at": now,
        "updated_at": now,
    }
    trip_id = await db.insert_one("trips", trip_data)
    trip_doc = await db.find_one("trips", {"_id": trip_id})
    return TripOut.from_doc(trip_doc)


@router.get("/{trip_id}", response_model=TripOut)
async def get_trip(
    trip_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    trip = await db.find_one("trips", {"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    _check_trip_access(trip, current_user.id, "viewer")
    return TripOut.from_doc(trip)


@router.put("/{trip_id}", response_model=TripOut)
async def update_trip(
    trip_id: str,
    payload: TripUpdate,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    trip = await db.find_one("trips", {"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    _check_trip_access(trip, current_user.id, "owner")

    updates = payload.model_dump(exclude_none=True)
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.update_one("trips", {"_id": trip_id}, updates)
    updated = await db.find_one("trips", {"_id": trip_id})
    return TripOut.from_doc(updated)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(
    trip_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    trip = await db.find_one("trips", {"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    _check_trip_access(trip, current_user.id, "owner")

    # Delete all nodes in this trip
    await db.delete_many("nodes", {"trip_id": trip_id})
    # Delete all comments
    await db.delete_many("comments", {"trip_id": trip_id})
    # Delete the trip
    await db.delete_one("trips", {"_id": trip_id})
