from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.models.user import UserOut
from app.routers.trips import _check_trip_access

router = APIRouter(tags=["comments"])


class CommentCreate(BaseModel):
    text: str
    trip_id: str


class CommentOut(BaseModel):
    id: str
    node_id: str
    trip_id: str
    user_id: str
    user_name: str
    user_avatar: str | None
    text: str
    created_at: datetime


@router.get("/trips/{trip_id}/comments", response_model=list[CommentOut])
async def list_comments(
    trip_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    trip = await db.find_one("trips", {"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    _check_trip_access(trip, current_user.id, "viewer")

    comments = await db.find_many(
        "comments",
        {"trip_id": trip_id},
        sort=[("created_at", 1)],
    )
    # Enrich with user info
    result = []
    user_cache: dict[str, dict] = {}
    for c in comments:
        uid = c["user_id"]
        if uid not in user_cache:
            u = await db.find_one("users", {"_id": uid})
            user_cache[uid] = u or {}
        u = user_cache[uid]
        result.append(
            CommentOut(
                id=c["_id"],
                node_id=c["node_id"],
                trip_id=c["trip_id"],
                user_id=uid,
                user_name=u.get("name", "Unknown"),
                user_avatar=u.get("avatar_url"),
                text=c["text"],
                created_at=c["created_at"],
            )
        )
    return result


@router.post("/nodes/{node_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def add_comment(
    node_id: str,
    payload: CommentCreate,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    node = await db.find_one("nodes", {"_id": node_id})
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    trip = await db.find_one("trips", {"_id": node["trip_id"]})
    # commenter role or higher required
    _check_trip_access(trip, current_user.id, "commenter")

    now = datetime.now(timezone.utc)
    comment_data = {
        "node_id": node_id,
        "trip_id": node["trip_id"],
        "user_id": current_user.id,
        "text": payload.text,
        "created_at": now,
    }
    comment_id = await db.insert_one("comments", comment_data)
    return CommentOut(
        id=comment_id,
        node_id=node_id,
        trip_id=node["trip_id"],
        user_id=current_user.id,
        user_name=current_user.name,
        user_avatar=current_user.avatar_url,
        text=payload.text,
        created_at=now,
    )


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: str,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    comment = await db.find_one("comments", {"_id": comment_id})
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Only comment owner or trip owner can delete
    if comment["user_id"] != current_user.id:
        trip = await db.find_one("trips", {"_id": comment["trip_id"]})
        if trip["owner_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Cannot delete someone else's comment")

    await db.delete_one("comments", {"_id": comment_id})
