from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..db import get_db
from ..models import IpRange


class IpRangeIn(BaseModel):
    prefix: str


class IpRangeOut(BaseModel):
    id: int
    prefix: str

    class Config:
        from_attributes = True


router = APIRouter()


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

