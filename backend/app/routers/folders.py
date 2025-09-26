from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.tl.functions.chatlists import CheckChatlistInviteRequest, JoinChatlistInviteRequest
from ..settings import settings
from ..db import get_db
from ..models import SessionAccount


class AddListIn(BaseModel):
    phone_ids: list[int]
    link: str


router = APIRouter()


@router.post("/addlist")
async def addlist_join(payload: AddListIn, db: Session = Depends(get_db)):
    if "addlist/" not in payload.link:
        raise HTTPException(status_code=400, detail="Not an addlist link")
    accounts = db.query(SessionAccount).filter(SessionAccount.id.in_(payload.phone_ids)).all()
    if not accounts:
        raise HTTPException(status_code=404, detail="Accounts not found")

    slug = payload.link.split("addlist/")[-1]
    results: list[dict] = []

    for acc in accounts:
        client = TelegramClient(acc.session_file, settings.api_id, settings.api_hash)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                results.append({"phone": acc.phone, "status": "unauthorized"})
                continue
            r = await client(CheckChatlistInviteRequest(slug=slug))
            await client(JoinChatlistInviteRequest(slug=slug, peers=r.peers))
            results.append({"phone": acc.phone, "status": "joined"})
        except Exception as e:
            results.append({"phone": acc.phone, "status": "error", "detail": str(e)})
        finally:
            await client.disconnect()

    return {"results": results}

