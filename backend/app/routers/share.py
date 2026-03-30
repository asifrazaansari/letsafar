from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.models.user import UserOut
from app.models.trip import TripOut
from app.routers.trips import _check_trip_access

router = APIRouter(tags=["share"])

VALID_ROLES = {"viewer", "commenter", "editor"}


class ShareInviteRequest(BaseModel):
    email: EmailStr
    role: str = "viewer"


class ShareUpdateRequest(BaseModel):
    role: str


@router.post("/trips/{trip_id}/share", status_code=status.HTTP_201_CREATED)
async def invite_collaborator(
    trip_id: str,
    payload: ShareInviteRequest,
    current_user: UserOut = Depends(get_current_user),
):
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {VALID_ROLES}")

    db = await get_db()
    trip = await db.find_one("trips", {"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    _check_trip_access(trip, current_user.id, "owner")

    # Look up invited user
    invited_user = await db.find_one("users", {"email": payload.email})
    if not invited_user:
        raise HTTPException(status_code=404, detail="No user found with that email")

    invited_id = invited_user["_id"]
    if invited_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot invite yourself")

    # Prevent duplicates
    for collab in trip.get("collaborators", []):
        if collab["user_id"] == invited_id:
            raise HTTPException(status_code=409, detail="User already invited")

    new_collab = {
        "user_id": invited_id,
        "role": payload.role,
        "invited_at": datetime.now(timezone.utc).isoformat(),
        "accepted": False,
    }

    collaborators = trip.get("collaborators", []) + [new_collab]
    await db.update_one("trips", {"_id": trip_id}, {"collaborators": collaborators})
    return {"message": "Invitation sent", "invited_user_id": invited_id}


@router.put("/trips/{trip_id}/share/{user_id}")
async def update_collaborator_role(
    trip_id: str,
    user_id: str,
    payload: ShareUpdateRequest,
    current_user: UserOut = Depends(get_current_user),
):
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {VALID_ROLES}")

    db = await get_db()
    trip = await db.find_one("trips", {"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    _check_trip_access(trip, current_user.id, "owner")

    collabs = trip.get("collaborators", [])
    updated = False
    for collab in collabs:
        if collab["user_id"] == user_id:
            collab["role"] = payload.role
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Collaborator not found")

    await db.update_one("trips", {"_id": trip_id}, {"collaborators": collabs})
    return {"message": "Role updated"}


@router.delete("/trips/{trip_id}/share/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_access(
    trip_id: str,
    user_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    trip = await db.find_one("trips", {"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    _check_trip_access(trip, current_user.id, "owner")

    collabs = [c for c in trip.get("collaborators", []) if c["user_id"] != user_id]
    await db.update_one("trips", {"_id": trip_id}, {"collaborators": collabs})


@router.post("/trips/{trip_id}/share/accept")
async def accept_invite(
    trip_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    """Accept a pending invitation."""
    db = await get_db()
    trip = await db.find_one("trips", {"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    collabs = trip.get("collaborators", [])
    found = False
    for collab in collabs:
        if collab["user_id"] == current_user.id:
            collab["accepted"] = True
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail="No pending invite found")

    await db.update_one("trips", {"_id": trip_id}, {"collaborators": collabs})
    return {"message": "Invite accepted"}
