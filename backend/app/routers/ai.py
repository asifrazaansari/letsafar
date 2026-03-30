"""
AI router — endpoints for LangGraph-powered trip enhancement.
Streams responses via Server-Sent Events (SSE).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.models.user import UserOut

router = APIRouter(prefix="/ai", tags=["ai"])


class EnhanceRequest(BaseModel):
    trip_id: str
    goal: str = "Enhance my trip with cultural insights, prayer times, logistics, and cost estimates"
    history: list[dict] | None = None


class ChatRequest(BaseModel):
    trip_id: str
    message: str
    history: list[dict] | None = None


@router.post("/enhance")
async def enhance_trip(
    body: EnhanceRequest,
    current_user: UserOut = Depends(get_current_user),
):
    """
    Run the full 6-agent LangGraph pipeline over a trip.
    Returns Server-Sent Events stream.
    """
    from app.ai.agent_graph import stream_enhancement

    async def event_generator():
        async for chunk in stream_enhancement(
            trip_id=body.trip_id,
            user_goal=body.goal,
            history=body.history,
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat")
async def ai_chat(
    body: ChatRequest,
    current_user: UserOut = Depends(get_current_user),
):
    """
    Single-turn chat with the Writer agent for quick questions.
    Returns SSE stream.
    """
    from app.ai.agent_graph import stream_enhancement

    async def event_generator():
        async for chunk in stream_enhancement(
            trip_id=body.trip_id,
            user_goal=body.message,
            history=body.history,
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
