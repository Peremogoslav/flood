from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.tl.functions.chatlists import CheckChatlistInviteRequest, JoinChatlistInviteRequest
from ..settings import settings
from ..db import get_db
from ..models import SessionAccount
from ..security import bearer_auth
from ..services.telethon_service import list_folders


class AddListIn(BaseModel):
    phone_ids: list[int] = Field(min_length=1)
    link: str = Field(min_length=10, max_length=256)


router = APIRouter(dependencies=[Depends(bearer_auth(settings.jwt_secret))])


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


@router.get("/by_accounts")
async def folders_by_accounts(account_ids: list[int] = Field(default_factory=list), db: Session = Depends(get_db)):
    if not account_ids:
        raise HTTPException(status_code=400, detail="account_ids required")
    accounts = db.query(SessionAccount).filter(SessionAccount.id.in_(account_ids)).all()
    if not accounts:
        raise HTTPException(status_code=404, detail="Accounts not found")
    out = {}
    for acc in accounts:
        out[str(acc.id)] = await list_folders(acc.session_file)
    return out

