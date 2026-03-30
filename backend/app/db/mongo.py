from typing import Any, Optional
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorClient
from app.db.base import BaseDB
from app.core.config import settings


def _serialize(doc: dict | None) -> dict | None:
    """Convert ObjectId fields to strings recursively."""
    if doc is None:
        return None
    result = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, dict):
            result[k] = _serialize(v)
        elif isinstance(v, list):
            result[k] = [_serialize(i) if isinstance(i, dict) else (str(i) if isinstance(i, ObjectId) else i) for i in v]
        else:
            result[k] = v
    return result


def _to_object_id(id_str: str) -> ObjectId | None:
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        return None


class MongoDB(BaseDB):
    def __init__(self):
        self._client: AsyncIOMotorClient | None = None
        self._db = None

    async def connect(self):
        self._client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,  # fail fast if DB is down
        )
        self._db = self._client[settings.MONGODB_DB_NAME]

    async def disconnect(self):
        if self._client:
            self._client.close()

    def _collection(self, name: str):
        return self._db[name]

    async def find_one(self, collection: str, query: dict) -> Optional[dict]:
        # Convert string _id to ObjectId in query
        if "_id" in query and isinstance(query["_id"], str):
            query = {**query, "_id": _to_object_id(query["_id"])}
        doc = await self._collection(collection).find_one(query)
        return _serialize(doc)

    async def find_many(
        self,
        collection: str,
        query: dict,
        skip: int = 0,
        limit: int = 50,
        sort: Optional[list] = None,
    ) -> list[dict]:
        cursor = self._collection(collection).find(query).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        return [_serialize(doc) async for doc in cursor]

    async def insert_one(self, collection: str, document: dict) -> str:
        result = await self._collection(collection).insert_one(document)
        return str(result.inserted_id)

    async def update_one(self, collection: str, query: dict, update: dict) -> bool:
        if "_id" in query and isinstance(query["_id"], str):
            query = {**query, "_id": _to_object_id(query["_id"])}
        result = await self._collection(collection).update_one(query, {"$set": update})
        return result.modified_count > 0

    async def delete_one(self, collection: str, query: dict) -> bool:
        if "_id" in query and isinstance(query["_id"], str):
            query = {**query, "_id": _to_object_id(query["_id"])}
        result = await self._collection(collection).delete_one(query)
        return result.deleted_count > 0

    async def delete_many(self, collection: str, query: dict) -> int:
        result = await self._collection(collection).delete_many(query)
        return result.deleted_count

    async def count(self, collection: str, query: dict) -> int:
        return await self._collection(collection).count_documents(query)

    async def create_indexes(self):
        """Create required indexes on startup."""
        try:
            await self._db["users"].drop_index("google_id_1")
        except:
            pass
        await self._db["users"].create_index("google_id", unique=True, sparse=True)
        await self._db["users"].create_index("email", unique=True)
        await self._db["trips"].create_index("owner_id")
        await self._db["trips"].create_index("visibility")
        await self._db["nodes"].create_index("trip_id")
        await self._db["nodes"].create_index("parent_id")
        await self._db["comments"].create_index("node_id")


# Singleton
_db_instance: MongoDB | None = None


async def get_db() -> MongoDB:
    global _db_instance
    if _db_instance is None:
        _db_instance = MongoDB()
        await _db_instance.connect()
        await _db_instance.create_indexes()
    return _db_instance
