from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.models.user import UserOut, UserUpdate
from datetime import datetime, timezone

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(current_user: UserOut = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    current_user: UserOut = Depends(get_current_user),
):
    db = await get_db()
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return current_user

    updates["updated_at"] = datetime.now(timezone.utc)
    await db.update_one("users", {"_id": current_user.id}, updates)
    user_doc = await db.find_one("users", {"_id": current_user.id})
    return UserOut.from_doc(user_doc)
