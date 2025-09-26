from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import PhoneNumberInvalidError, PhoneCodeInvalidError, SessionPasswordNeededError
from ..settings import settings
from ..db import SessionLocal
from ..models import SessionAccount
import os


class StartAuthIn(BaseModel):
    phone: str


class VerifyAuthIn(BaseModel):
    phone: str
    code: str | None = None
    password: str | None = None


router = APIRouter()


def _session_path_for_phone(phone: str) -> str:
    os.makedirs(settings.sessions_dir, exist_ok=True)
    safe_phone = phone.replace(" ", "")
    return os.path.join(settings.sessions_dir, f"{safe_phone}.session")


@router.post("/start")
async def start_auth(payload: StartAuthIn):
    if not payload.phone or not payload.phone.startswith("+"):
        raise HTTPException(status_code=400, detail="Phone must start with + and include country code")

    # prevent duplicate accounts
    db = SessionLocal()
    try:
        if db.query(SessionAccount).filter_by(phone=payload.phone).first():
            raise HTTPException(status_code=409, detail="Account already exists")
    finally:
        db.close()

    session_path = _session_path_for_phone(payload.phone)

    client = TelegramClient(session_path, settings.api_id, settings.api_hash)
    await client.connect()
    try:
        await client.send_code_request(payload.phone)
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

    return {"status": "code_sent"}


@router.post("/verify")
async def verify_auth(payload: VerifyAuthIn):
    if not payload.phone:
        raise HTTPException(status_code=400, detail="phone is required")

    session_path = _session_path_for_phone(payload.phone)
    client = TelegramClient(session_path, settings.api_id, settings.api_hash)
    await client.connect()

    try:
        if payload.code:
            try:
                await client.sign_in(payload.phone, payload.code)
            except PhoneCodeInvalidError:
                raise HTTPException(status_code=400, detail="Invalid code")
            except SessionPasswordNeededError:
                # require password in another branch
                if not payload.password:
                    raise HTTPException(status_code=428, detail="Password required (2FA enabled)")
        if payload.password and (not payload.code):
            # attempt password-only sign in (after previous code attempt)
            try:
                await client.sign_in(password=payload.password)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid 2FA password: {e}")

        # ensure authorized
        if not await client.is_user_authorized():
            raise HTTPException(status_code=401, detail="Authorization failed")

        # persist in DB
        db = SessionLocal()
        try:
            existing = db.query(SessionAccount).filter_by(phone=payload.phone).first()
            if not existing:
                rec = SessionAccount(phone=payload.phone, session_file=session_path)
                db.add(rec)
                db.commit()
        finally:
            db.close()

        return {"status": "authorized"}
    finally:
        if client.is_connected():
            await client.disconnect()

