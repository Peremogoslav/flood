from fastapi import FastAPI
from sqlalchemy.orm import Session
from .db import Base, engine, SessionLocal
from .models import IpRange
from .routers import accounts, config, admin, auth, folders, users

DEFAULT_IP_PREFIXES = [
    "10.244.102.",
    "10.244.112.",
    "10.241.119.",
    "10.244.82."
]

app = FastAPI(title="Telegram Manager API")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        existing = {r.prefix for r in db.query(IpRange).all()}
        for prefix in DEFAULT_IP_PREFIXES:
            if prefix not in existing:
                db.add(IpRange(prefix=prefix))
        db.commit()
    finally:
        db.close()


app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
app.include_router(config.router, prefix="/config", tags=["config"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(folders.router, prefix="/folders", tags=["folders"])
app.include_router(users.router, prefix="/users", tags=["users"])

