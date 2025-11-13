from bson import ObjectId
from pydantic import BaseModel, Field, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from typing import Optional, Any, Dict
import datetime

# --- Pydantic v2-compatible ObjectId type ---
class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic v2."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any, info: Any) -> ObjectId:
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError(f"Invalid ObjectId: {v}")

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: JsonSchemaValue, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string", "example": "64b7b8f3f08d6c1c9f6a7c2b"}

class MongoModel(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class DocumentModel(MongoModel):
    ownerId: str
    filename: str
    mime: str
    gridfsId: Optional[PyObjectId] = None
    textContent: Optional[str] = None
    createdAt: datetime.datetime

    class Config:
        extra = "allow"



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

