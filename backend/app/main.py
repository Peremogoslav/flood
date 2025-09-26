from fastapi import FastAPI
from sqlalchemy.orm import Session
from .db import Base, engine, SessionLocal
from .models import IpRange
from .routers import accounts, config, admin, auth, folders, users
from sqlalchemy import inspect as sa_inspect, text
from .handlers import validation_exception_handler, integrity_exception_handler, generic_exception_handler
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

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

    # lightweight migration: ensure users.username exists and legacy email does not block inserts
    try:
        inspector = sa_inspect(engine)
        if 'users' in inspector.get_table_names():
            col_names = {c['name'] for c in inspector.get_columns('users')}
            if 'username' not in col_names:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR"))
                    conn.execute(text("UPDATE users SET username = email WHERE (username IS NULL OR username = '') AND email IS NOT NULL"))
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username ON users (username)"))
                    try:
                        conn.execute(text("ALTER TABLE users ALTER COLUMN username SET NOT NULL"))
                    except Exception:
                        pass
            # drop legacy email constraints/column if present
            if 'email' in col_names:
                with engine.begin() as conn:
                    try:
                        conn.execute(text("DROP INDEX IF EXISTS uq_users_email"))
                    except Exception:
                        pass
                    try:
                        conn.execute(text("ALTER TABLE users DROP COLUMN email"))
                    except Exception:
                        try:
                            conn.execute(text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL"))
                        except Exception:
                            pass
    except Exception:
        # best-effort migration; ignore if not applicable
        pass


app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
app.include_router(config.router, prefix="/config", tags=["config"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(folders.router, prefix="/folders", tags=["folders"])
app.include_router(users.router, prefix="/users", tags=["users"])

# exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

