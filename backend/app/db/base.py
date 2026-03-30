"""Abstract DB interface — all DB implementations must conform to this."""
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseDB(ABC):

    @abstractmethod
    async def connect(self): ...

    @abstractmethod
    async def disconnect(self): ...

    # ── Generic CRUD ───────────────────────────────────────────────────────────
    @abstractmethod
    async def find_one(self, collection: str, query: dict) -> Optional[dict]: ...

    @abstractmethod
    async def find_many(
        self,
        collection: str,
        query: dict,
        skip: int = 0,
        limit: int = 50,
        sort: Optional[list] = None,
    ) -> list[dict]: ...

    @abstractmethod
    async def insert_one(self, collection: str, document: dict) -> str: ...

    @abstractmethod
    async def update_one(self, collection: str, query: dict, update: dict) -> bool: ...

    @abstractmethod
    async def delete_one(self, collection: str, query: dict) -> bool: ...

    @abstractmethod
    async def delete_many(self, collection: str, query: dict) -> int: ...

    @abstractmethod
    async def count(self, collection: str, query: dict) -> int: ...
