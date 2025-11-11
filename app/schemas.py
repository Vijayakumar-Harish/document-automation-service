from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime

class UserClaims(BaseModel):
    sub: str
    email: EmailStr
    role: str

class DocumentIn(BaseModel):
    filename: str
    mime: str
    primaryTag: str
    secondaryTags: Optional[List[str]] = []
    textContent: Optional[str] = None

class ActionScope(BaseModel):
    type: str
    name: Optional[str] = None
    ids: Optional[List[str]] = None

class ActionRequest(BaseModel):
    scope: ActionScope
    messages: List[dict]
    actions: List[str]

class OCRPayload(BaseModel):
    source: str
    imageId: str
    text: str
    meta: dict = {}
