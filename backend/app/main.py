from contextlib import asynccontextmanager
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.redis import close_redis
from app.core.socketio import sio
from app.db.mongo import get_db

from app.routers import auth, users, trips, nodes, share, comments, costs, explore, ai


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — tolerate DB being unavailable during dev
    import logging
    try:
        await get_db()
        logging.info(f"CORS Allowed Origins: {settings.ALLOWED_ORIGINS}")
    except Exception as exc:
        logging.warning(f"DB startup warning (non-fatal): {exc}")
    yield
    # Shutdown
    await close_redis()


_fastapi = FastAPI(
    title="Rihla API",
    description="Sacred Travel Intelligence Platform — Backend API",
    version="1.0.0",
    lifespan=lifespan,
)

_fastapi.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_fastapi.include_router(auth.router)
_fastapi.include_router(users.router)
_fastapi.include_router(trips.router)
_fastapi.include_router(nodes.router)
_fastapi.include_router(share.router)
_fastapi.include_router(comments.router)
_fastapi.include_router(costs.router)
_fastapi.include_router(explore.router)
_fastapi.include_router(ai.router)


@_fastapi.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


# Mount Socket.IO as an ASGI sub-app at /ws
app = socketio.ASGIApp(sio, other_asgi_app=_fastapi, socketio_path="/ws")
