import asyncio
import random
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from telethon import TelegramClient
from ..db import get_db
from ..models import SessionAccount, UserConfig
from ..security import bearer_auth, get_current_user_id
from ..settings import settings
from ..services.telethon_service import get_folder_peers


class SpamStartIn(BaseModel):
    account_ids: list[int] = Field(min_length=1)
    folder_name: str = Field(min_length=1, max_length=128)
    messages: list[str] = Field(min_length=1)
    min_delay: int = Field(ge=1, le=3600)
    max_delay: int = Field(ge=1, le=3600)
    randomize_chats: bool = True


router = APIRouter(dependencies=[Depends(bearer_auth(settings.jwt_secret))])


@router.post("/start")
async def start_spam(payload: SpamStartIn, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id(settings.jwt_secret))):
    if payload.max_delay < payload.min_delay:
        raise HTTPException(status_code=400, detail="max_delay must be >= min_delay")

    accounts = db.query(SessionAccount).filter(SessionAccount.id.in_(payload.account_ids)).all()
    if not accounts:
        raise HTTPException(status_code=404, detail="Accounts not found")

    # user-specific config fallback
    ucfg = db.query(UserConfig).filter_by(user_id=current_user_id).first()
    user_min = ucfg.min_delay if ucfg else payload.min_delay
    user_max = ucfg.max_delay if ucfg else payload.max_delay
    user_rand = bool(ucfg.randomize_chats) if ucfg else payload.randomize_chats

    async def spam_for_account(acc: SessionAccount):
        client = TelegramClient(acc.session_file, settings.api_id, settings.api_hash)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                return
            peers = await get_folder_peers(acc.session_file, payload.folder_name)
            if user_rand:
                random.shuffle(peers)
            for peer in peers:
                msg = random.choice(payload.messages)
                try:
                    await client.send_message(peer, msg, link_preview=False)
                except Exception:
                    pass
                await asyncio.sleep(random.randint(user_min, user_max))
        finally:
            if client.is_connected():
                await client.disconnect()

    await asyncio.gather(*[spam_for_account(a) for a in accounts])
    return {"status": "completed"}

