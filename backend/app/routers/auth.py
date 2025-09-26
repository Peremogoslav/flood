from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from telethon import TelegramClient
from telethon.errors import PhoneNumberInvalidError, PhoneCodeInvalidError, SessionPasswordNeededError
from ..settings import settings
from ..db import SessionLocal
from ..models import SessionAccount, AuthFlow
from ..security import bearer_auth, get_current_user_id
import os


class StartAuthIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)


class VerifyAuthIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    code: str | None = Field(default=None, min_length=2, max_length=10)
    password: str | None = Field(default=None, max_length=256)


router = APIRouter(dependencies=[Depends(bearer_auth(settings.jwt_secret))])


def _session_path_for_phone(phone: str) -> str:
    os.makedirs(settings.sessions_dir, exist_ok=True)
    safe_phone = phone.replace(" ", "")
    return os.path.join(settings.sessions_dir, f"{safe_phone}.session")


@router.post("/start")
async def start_auth(payload: StartAuthIn):
    if not payload.phone or not payload.phone.startswith("+"):
        raise HTTPException(status_code=400, detail="Phone must start with + and include country code")

    # normalize phone (remove spaces); duplicates allowed (re-auth)
    norm_phone = payload.phone.replace(" ", "")
    session_path = _session_path_for_phone(norm_phone)

    client = TelegramClient(session_path, settings.api_id, settings.api_hash)
    await client.connect()
    try:
        sent = await client.send_code_request(norm_phone)
    except PhoneNumberInvalidError:
        await client.disconnect()
        raise HTTPException(status_code=404, detail="Phone not found or invalid in Telegram")
    except Exception as e:
        await client.disconnect()
        raise HTTPException(status_code=500, detail=f"Failed to start auth: {e}")
    finally:
        # do not keep connection open
        if client.is_connected():
            await client.disconnect()

    # save phone_code_hash
    db = SessionLocal()
    try:
        rec = db.query(AuthFlow).filter_by(phone=norm_phone).first()
        if rec:
            rec.phone_code_hash = sent.phone_code_hash
        else:
            rec = AuthFlow(phone=norm_phone, phone_code_hash=sent.phone_code_hash)
            db.add(rec)
        db.commit()
    finally:
        db.close()

    return {"status": "code_sent"}


@router.post("/verify")
async def verify_auth(payload: VerifyAuthIn, current_user_id: int = Depends(get_current_user_id(settings.jwt_secret))):
    if not payload.phone:
        raise HTTPException(status_code=400, detail="phone is required")

    norm_phone = payload.phone.replace(" ", "")
    session_path = _session_path_for_phone(norm_phone)
    client = TelegramClient(session_path, settings.api_id, settings.api_hash)
    await client.connect()

    try:
        # fetch stored phone_code_hash
        db = SessionLocal()
        try:
            flow = db.query(AuthFlow).filter_by(phone=norm_phone).first()
            phone_code_hash = flow.phone_code_hash if flow else None
        finally:
            db.close()

        if not payload.code:
            raise HTTPException(status_code=400, detail="code is required")

        try:
            await client.sign_in(norm_phone, payload.code, phone_code_hash=phone_code_hash)
        except PhoneCodeInvalidError:
            raise HTTPException(status_code=400, detail="Invalid code")
        except SessionPasswordNeededError:
            if not payload.password:
                raise HTTPException(status_code=428, detail="Password required (2FA enabled)")
            await client.sign_in(password=payload.password)

        # ensure authorized
        if not await client.is_user_authorized():
            raise HTTPException(status_code=401, detail="Authorization failed")

        # persist in DB and cleanup flow (store local session file path)
        db = SessionLocal()
        try:
            existing = db.query(SessionAccount).filter_by(phone=norm_phone).first()
            if not existing:
                rec = SessionAccount(phone=norm_phone, session_file=session_path, session_string=None, user_id=current_user_id)
                db.add(rec)
            else:
                if existing.user_id and existing.user_id != current_user_id:
                    raise HTTPException(status_code=409, detail="Account belongs to another user")
                existing.session_file = session_path
                existing.session_string = None
                if not existing.user_id:
                    existing.user_id = current_user_id
            if db.query(AuthFlow).filter_by(phone=norm_phone).first():
                db.query(AuthFlow).filter_by(phone=norm_phone).delete()
            db.commit()
        finally:
            db.close()

        return {"status": "authorized"}
    finally:
        if client.is_connected():
            await client.disconnect()

