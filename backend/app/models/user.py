from datetime import datetime, timezone
from typing import Optional
from enum import Enum
from pydantic import BaseModel, EmailStr, Field


class ThemeEnum(str, Enum):
    sacred = "sacred"
    desert = "desert"
    glacier = "glacier"


class AIModelEnum(str, Enum):
    openai = "openai"
    claude = "claude"
    gemini = "gemini"
    grok = "grok"


class UserCreate(BaseModel):
    google_id: Optional[str] = None
    email: EmailStr
    name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class UserRegister(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    theme: Optional[ThemeEnum] = None
    ai_model: Optional[AIModelEnum] = None


class UserOut(BaseModel):
    id: str
    google_id: Optional[str] = None
    email: str
    name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    theme: ThemeEnum = ThemeEnum.sacred
    ai_model: AIModelEnum = AIModelEnum.openai
    created_at: datetime

    @classmethod
    def from_doc(cls, doc: dict) -> "UserOut":
        return cls(
            id=doc["_id"],
            google_id=doc.get("google_id"),
            email=doc["email"],
            name=doc["name"],
            phone=doc.get("phone"),
            avatar_url=doc.get("avatar_url"),
            theme=doc.get("theme", ThemeEnum.sacred),
            ai_model=doc.get("ai_model", AIModelEnum.openai),
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
        )
