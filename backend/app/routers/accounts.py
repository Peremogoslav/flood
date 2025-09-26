from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..db import get_db
from ..models import SessionAccount
from ..settings import settings
from ..security import bearer_auth, get_current_user_id
import logging

logger = logging.getLogger("app")


class AccountCreate(BaseModel):
    phone: str
    session_file: str


class AccountOut(BaseModel):
    id: int
    phone: str
    session_file: str | None = None

    class Config:
        from_attributes = True


router = APIRouter(dependencies=[Depends(bearer_auth(settings.jwt_secret))])


@router.get("/", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id(settings.jwt_secret))):
    logger.info("accounts_list user_id=%s", current_user_id)
    return db.query(SessionAccount).filter_by(user_id=current_user_id).all()


@router.post("/", response_model=AccountOut)
def create_account(payload: AccountCreate, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id(settings.jwt_secret))):
    existing = db.query(SessionAccount).filter_by(phone=payload.phone).first()
    if existing:
        logger.warning("account_conflict user_id=%s phone=%s", current_user_id, payload.phone)
        raise HTTPException(status_code=409, detail="Account already exists")
    acc = SessionAccount(phone=payload.phone, session_file=payload.session_file, user_id=current_user_id)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    logger.info("account_created user_id=%s account_id=%s phone=%s", current_user_id, acc.id, acc.phone)
    return acc


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id(settings.jwt_secret))):
    acc = db.query(SessionAccount).get(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Not found")
    if acc.user_id and acc.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    db.delete(acc)
    db.commit()
    logger.info("account_deleted user_id=%s account_id=%s phone=%s", current_user_id, account_id, getattr(acc, 'phone', '?'))
    return None

