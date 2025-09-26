from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from ..db import get_db
from ..models import IpRange
from ..settings import settings
from ..security import bearer_auth, get_current_user_id, decode_access_token
from fastapi import Header
from ..settings import settings


class IpRangeIn(BaseModel):
    prefix: str = Field(pattern=r"^(?:\d{1,3}\.){3}$", description="e.g. 192.168.1.")


class IpRangeOut(BaseModel):
    id: int
    prefix: str

    class Config:
        from_attributes = True


def admin_guard(authorization: str = Header(default="")):
    try:
        token = authorization.split(" ", 1)[1]
    except Exception:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    payload = decode_access_token(token, settings.jwt_secret)
    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return True


router = APIRouter(dependencies=[Depends(admin_guard)])


@router.get("/ip_ranges", response_model=list[IpRangeOut])
def list_ip_ranges(db: Session = Depends(get_db)):
    return db.query(IpRange).order_by(IpRange.id).all()


@router.post("/ip_ranges", response_model=IpRangeOut, status_code=201)
def add_ip_range(item: IpRangeIn, db: Session = Depends(get_db)):
    exists = db.query(IpRange).filter_by(prefix=item.prefix).first()
    if exists:
        raise HTTPException(status_code=409, detail="Prefix already exists")
    rec = IpRange(prefix=item.prefix)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/ip_ranges/{ip_id}", status_code=204)
def delete_ip_range(ip_id: int, db: Session = Depends(get_db)):
    rec = db.query(IpRange).get(ip_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(rec)
    db.commit()
    return None

