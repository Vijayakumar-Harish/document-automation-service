from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
from bson import ObjectId

from app.db import get_db
from app.utils import now
from app.config import settings
from app.schemas import UserClaims
from app.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict, expires_minutes: int = 60 * 24):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    token = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGO)
    return token


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/signup")
async def signup(payload: SignupRequest, db=Depends(get_db)):
    existing = await db.users.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = pwd_context.hash(payload.password)
    user = {
        "email": payload.email,
        "password": hashed_pw,
        "role": "user",  # default role
        "createdAt": now(),
    }
    res = await db.users.insert_one(user)
    return {"message": "Signup successful", "user_id": str(res.inserted_id)}


@router.post("/login")
async def login(payload: LoginRequest, db=Depends(get_db)):
    user = await db.users.find_one({"email": payload.email})
    if not user or not pwd_context.verify(payload.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token_data = {
        "sub": str(user["_id"]),
        "email": user["email"],
        "role": user.get("role", "user"),
    }
    token = create_access_token(token_data)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def me(user: UserClaims = Depends(get_current_user)):
    return {
        "sub": user.sub,
        "email": user.email,
        "role": user.role,
    }
