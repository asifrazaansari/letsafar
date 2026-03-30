"""
Socket.IO server for real-time collaboration features:
  - Live comments on nodes
  - Presence indicators (who is viewing a trip)
  - Optimistic node updates
"""
import socketio
from app.core.security import decode_token
from app.db.mongo import get_db
from datetime import datetime, timezone

# Standalone async server — will be mounted into FastAPI via ASGI
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",  # tightened via CORS middleware in production
    logger=False,
    engineio_logger=False,
)

# ── Namespace: /trips ─────────────────────────────────────────────────────────

@sio.event(namespace="/trips")
async def connect(sid: str, environ: dict, auth: dict | None = None):
    """Authenticate with JWT on socket connect."""
    token = (auth or {}).get("token", "")
    payload = decode_token(token) if token else None
    if not payload:
        # Allow unauthed for now so public trips can receive comments
        await sio.save_session(sid, {"user_id": None, "user_name": "Guest"}, namespace="/trips")
        return True
    await sio.save_session(
        sid,
        {"user_id": payload.get("sub"), "user_name": payload.get("name", "Traveller")},
        namespace="/trips",
    )
    return True


@sio.event(namespace="/trips")
async def disconnect(sid: str):
    session = await sio.get_session(sid, namespace="/trips")
    # Announce departure to any room the user is in
    for room in sio.rooms(sid, namespace="/trips"):
        if room != sid:
            await sio.emit(
                "user_left",
                {"user_id": session.get("user_id"), "user_name": session.get("user_name")},
                room=room,
                namespace="/trips",
            )


@sio.event(namespace="/trips")
async def join_trip(sid: str, data: dict):
    """Join the room for a specific trip."""
    trip_id = data.get("trip_id")
    if not trip_id:
        return {"error": "trip_id required"}
    session = await sio.get_session(sid, namespace="/trips")
    await sio.enter_room(sid, trip_id, namespace="/trips")
    # Announce presence
    await sio.emit(
        "user_joined",
        {"user_id": session.get("user_id"), "user_name": session.get("user_name")},
        room=trip_id,
        namespace="/trips",
        skip_sid=sid,
    )
    return {"ok": True, "trip_id": trip_id}


@sio.event(namespace="/trips")
async def leave_trip(sid: str, data: dict):
    trip_id = data.get("trip_id")
    if not trip_id:
        return {"error": "trip_id required"}
    session = await sio.get_session(sid, namespace="/trips")
    await sio.leave_room(sid, trip_id, namespace="/trips")
    await sio.emit(
        "user_left",
        {"user_id": session.get("user_id"), "user_name": session.get("user_name")},
        room=trip_id,
        namespace="/trips",
        skip_sid=sid,
    )
    return {"ok": True}


@sio.event(namespace="/trips")
async def send_comment(sid: str, data: dict):
    """
    data: { trip_id, node_id, text }
    Persists to DB and broadcasts to the trip room.
    """
    trip_id = data.get("trip_id")
    node_id = data.get("node_id")
    text = (data.get("text") or "").strip()

    if not all([trip_id, node_id, text]):
        return {"error": "trip_id, node_id and text are required"}

    session = await sio.get_session(sid, namespace="/trips")
    user_id = session.get("user_id")

    # Persist
    try:
        db = await get_db()
        comment_doc = {
            "trip_id": trip_id,
            "node_id": node_id,
            "user_id": user_id,
            "user_name": session.get("user_name", "Guest"),
            "text": text,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        comment_id = await db.insert_one("comments", comment_doc)
        comment_doc["id"] = comment_id
    except Exception:
        comment_doc = {
            "id": None,
            "trip_id": trip_id,
            "node_id": node_id,
            "user_id": user_id,
            "user_name": session.get("user_name", "Guest"),
            "text": text,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    # Broadcast to trip room (including sender)
    await sio.emit(
        "new_comment",
        comment_doc,
        room=trip_id,
        namespace="/trips",
    )
    return {"ok": True, "comment": comment_doc}


@sio.event(namespace="/trips")
async def node_updated(sid: str, data: dict):
    """
    Broadcast optimistic node updates to other viewers.
    data: { trip_id, node_id, changes }
    """
    trip_id = data.get("trip_id")
    if not trip_id:
        return {"error": "trip_id required"}
    await sio.emit(
        "node_changed",
        data,
        room=trip_id,
        namespace="/trips",
        skip_sid=sid,
    )
    return {"ok": True}
