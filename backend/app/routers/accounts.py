from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..db import get_db
from ..models import SessionAccount
from ..settings import settings
from ..security import bearer_auth


class AccountCreate(BaseModel):
    phone: str
    session_file: str


class AccountOut(BaseModel):
    id: int
    phone: str
    session_file: str

    class Config:
        from_attributes = True


router = APIRouter(dependencies=[Depends(bearer_auth(settings.jwt_secret))])


@router.get("/", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return db.query(SessionAccount).all()


@router.post("/", response_model=AccountOut)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    existing = db.query(SessionAccount).filter_by(phone=payload.phone).first()
    if existing:
        raise HTTPException(status_code=409, detail="Account already exists")
    acc = SessionAccount(phone=payload.phone, session_file=payload.session_file)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(SessionAccount).get(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(acc)
    db.commit()
    return None

