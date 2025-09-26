from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User
from ..security import hash_password, verify_password, create_access_token
from ..settings import settings
import logging

logger = logging.getLogger("app")


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=256)


class LoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=1, max_length=256)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_admin: bool = False


router = APIRouter()


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(username=payload.username).first()
    if existing:
        logger.warning("register_conflict username=%s", payload.username)
        raise HTTPException(status_code=409, detail="Username already registered")
    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("register_success user_id=%s username=%s", user.id, user.username)
    token = create_access_token({"sub": str(user.id), "username": user.username, "is_admin": bool(user.is_admin)}, settings.jwt_secret)
    return TokenOut(access_token=token, is_admin=bool(user.is_admin))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=payload.username).first()
    if not user:
        logger.warning("login_invalid username=%s reason=no_user", payload.username)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # надеемся на безопасную проверку без утечки деталей
    if not verify_password(payload.password, user.password_hash):
        logger.warning("login_invalid username=%s reason=bad_password", payload.username)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    logger.info("login_success user_id=%s username=%s", user.id, user.username)
    token = create_access_token({"sub": str(user.id), "username": user.username, "is_admin": bool(user.is_admin)}, settings.jwt_secret)
    return TokenOut(access_token=token, is_admin=bool(user.is_admin))

