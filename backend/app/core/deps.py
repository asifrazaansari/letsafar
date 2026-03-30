"""Dependency: extract and validate the current user from Bearer JWT."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token
from app.db.mongo import get_db
from app.models.user import UserOut

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserOut:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")

    db = await get_db()
    user_doc = await db.find_one("users", {"_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    return UserOut.from_doc(user_doc)
