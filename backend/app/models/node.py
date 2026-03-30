from datetime import datetime, timezone
from typing import Optional
from enum import Enum
from pydantic import BaseModel


class NodeType(str, Enum):
    city = "city"
    place = "place"
    activity = "activity"
    stay = "stay"
    transit = "transit"


class NodeStatus(str, Enum):
    pending = "pending"
    done = "done"
    skipped = "skipped"


class SplitType(str, Enum):
    equal = "equal"
    custom = "custom"
    percent = "percent"


class SplitEntry(BaseModel):
    user_id: Optional[str] = None
    name: str
    share: float = 0.0
    paid: bool = False


class SplitConfig(BaseModel):
    type: SplitType = SplitType.equal
    travelers: list[SplitEntry] = []


class GeoPoint(BaseModel):
    lat: float
    lng: float
    address: Optional[str] = None


class NodeCreate(BaseModel):
    trip_id: str
    parent_id: Optional[str] = None
    name: str
    location: Optional[GeoPoint] = None
    node_type: NodeType = NodeType.place
    arrival: Optional[datetime] = None
    departure: Optional[datetime] = None
    duration_hrs: Optional[float] = None
    cost: Optional[float] = None
    cost_split: Optional[SplitConfig] = None
    notes: Optional[str] = None
    order: int = 0


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[GeoPoint] = None
    node_type: Optional[NodeType] = None
    arrival: Optional[datetime] = None
    departure: Optional[datetime] = None
    duration_hrs: Optional[float] = None
    cost: Optional[float] = None
    cost_split: Optional[SplitConfig] = None
    notes: Optional[str] = None
    status: Optional[NodeStatus] = None
    order: Optional[int] = None


class NodeMoveRequest(BaseModel):
    new_parent_id: Optional[str] = None
    new_order: int = 0


class NodeOut(BaseModel):
    id: str
    trip_id: str
    parent_id: Optional[str] = None
    children: list["NodeOut"] = []
    name: str
    location: Optional[GeoPoint] = None
    node_type: NodeType
    arrival: Optional[datetime] = None
    departure: Optional[datetime] = None
    duration_hrs: Optional[float] = None
    cost: Optional[float] = None
    cost_split: Optional[SplitConfig] = None
    notes: Optional[str] = None
    status: NodeStatus = NodeStatus.pending
    ai_summary: Optional[str] = None
    order: int = 0
    created_at: datetime

    @classmethod
    def from_doc(cls, doc: dict, children: list["NodeOut"] = None) -> "NodeOut":
        loc = doc.get("location")
        split = doc.get("cost_split")
        return cls(
            id=doc["_id"],
            trip_id=doc["trip_id"],
            parent_id=doc.get("parent_id"),
            children=children or [],
            name=doc["name"],
            location=GeoPoint(**loc) if loc else None,
            node_type=doc.get("node_type", NodeType.place),
            arrival=doc.get("arrival"),
            departure=doc.get("departure"),
            duration_hrs=doc.get("duration_hrs"),
            cost=doc.get("cost"),
            cost_split=SplitConfig(**split) if split else None,
            notes=doc.get("notes"),
            status=doc.get("status", NodeStatus.pending),
            ai_summary=doc.get("ai_summary"),
            order=doc.get("order", 0),
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
        )


NodeOut.model_rebuild()
