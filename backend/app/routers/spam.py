import asyncio
import random
import uuid
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


JOBS: dict[str, dict] = {}
JOBS_LOCK = asyncio.Lock()


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
        # 1) Получаем список адресатов строго последовательно (в отдельной сессии)
        peers = await get_folder_peers(acc.session_file, payload.folder_name, session_string=acc.session_string)
        if not peers:
            return
        if user_rand:
            random.shuffle(peers)

        # 2) Создаём клиент для отправки и подключаемся
        from telethon.sessions import StringSession
        if acc.session_string:
            client = TelegramClient(StringSession(acc.session_string), settings.api_id, settings.api_hash)
            lock = None
            await client.connect()
        else:
            client = TelegramClient(acc.session_file, settings.api_id, settings.api_hash)
            from ..services.telethon_service import session_lock_for
            lock = session_lock_for(acc.session_file or "")
            async with lock:
                await client.connect()

        try:
            if not await client.is_user_authorized():
                return
            for peer in peers:
                msg = random.choice(payload.messages)
                try:
                    await client.send_message(peer, msg, link_preview=False)
                except Exception:
                    pass
                await asyncio.sleep(random.randint(user_min, user_max))
        finally:
            if client.is_connected():
                if lock:
                    async with lock:
                        await client.disconnect()
                else:
                    await client.disconnect()

    async def worker(job_id: str):
        try:
            await asyncio.gather(*[spam_for_account(a) for a in accounts])
            async with JOBS_LOCK:
                JOBS[job_id]["status"] = "completed"
        except Exception as e:
            async with JOBS_LOCK:
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["detail"] = str(e)

    job_id = str(uuid.uuid4())
    async with JOBS_LOCK:
        JOBS[job_id] = {"status": "running"}
    asyncio.create_task(worker(job_id))
    return {"status": "started", "job_id": job_id}


@router.get("/status/{job_id}")
async def spam_status(job_id: str):
    async with JOBS_LOCK:
        if job_id not in JOBS:
            raise HTTPException(status_code=404, detail="job not found")
        return JOBS[job_id]

