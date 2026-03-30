from datetime import datetime, timezone
from typing import Optional
from enum import Enum
from pydantic import BaseModel


class TripStatus(str, Enum):
    dream = "dream"
    planned = "planned"
    active = "active"
    done = "done"


class TripVisibility(str, Enum):
    private = "private"
    shared = "shared"
    public = "public"


class TripCreate(BaseModel):
    title: str
    description: Optional[str] = None
    visibility: TripVisibility = TripVisibility.private
    total_budget: Optional[float] = None
    currency: str = "INR"
    tags: list[str] = []
    status: TripStatus = TripStatus.dream


class TripUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[TripVisibility] = None
    total_budget: Optional[float] = None
    currency: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[TripStatus] = None


class CollaboratorOut(BaseModel):
    user_id: str
    role: str
    invited_at: datetime
    accepted: bool
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class TripOut(BaseModel):
    id: str
    owner_id: str
    title: str
    description: Optional[str] = None
    root_node_id: Optional[str] = None
    visibility: TripVisibility
    collaborators: list[CollaboratorOut] = []
    total_budget: Optional[float] = None
    currency: str = "INR"
    tags: list[str] = []
    status: TripStatus
    ai_enhanced: bool = False
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: dict) -> "TripOut":
        return cls(
            id=doc["_id"],
            owner_id=doc["owner_id"],
            title=doc["title"],
            description=doc.get("description"),
            root_node_id=doc.get("root_node_id"),
            visibility=doc.get("visibility", TripVisibility.private),
            collaborators=doc.get("collaborators", []),
            total_budget=doc.get("total_budget"),
            currency=doc.get("currency", "INR"),
            tags=doc.get("tags", []),
            status=doc.get("status", TripStatus.dream),
            ai_enhanced=doc.get("ai_enhanced", False),
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
            updated_at=doc.get("updated_at", datetime.now(timezone.utc)),
        )
