from bson import ObjectId
from typing import Any, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime

try:
    #  For Pydantic ≥ 2.3
    from pydantic import core_schema
except ImportError:
    # For early Pydantic 2.0–2.1 compatibility
    from pydantic_core import core_schema


class PyObjectId(ObjectId):
    """
    Custom ObjectId type for Pydantic v2+
    Works across all recent releases.
    """

    @classmethod
    def validate(cls, value: Any) -> "PyObjectId":
        if isinstance(value, ObjectId):
            return cls(value)
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid ObjectId format")
        return cls(value)

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_plain_validator_function(cls.validate),
            python_schema=core_schema.no_info_plain_validator_function(cls.validate),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema_, handler):
        json_schema = handler(core_schema_)
        json_schema.update(type="string", examples=["656d9c18b19a82d6a8b1e41b"])
        return json_schema


class MongoModel(BaseModel):
    """
    Base Mongo model using ObjectId for `_id`.
    """
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class DocumentModel(MongoModel):
    ownerId: str
    filename: str
    mime: str
    gridfsId: PyObjectId
    textContent: Optional[str] = None
    createdAt: datetime

class TagModel(MongoModel):
    name: str
    ownerId: str
    createdAt: datetime


class DocumentTagModel(MongoModel):
    documentId: PyObjectId
    tagId: PyObjectId
    isPrimary: bool = False

class TaskModel(MongoModel):
    userId: str
    sender: str
    status: str = "pending"
    channel: str
    target: Optional[str] = None
    payload: Dict[str, Any]
    createdAt: datetime

class AuditLogModel(MongoModel):
    userId: str
    action: str
    entityType: str
    entityId: str
    metadata: Dict[str, Any]
    at: datetime


class RateLimitModel(MongoModel):
    key: str
    count: int = 1
    createdAt: datetime

