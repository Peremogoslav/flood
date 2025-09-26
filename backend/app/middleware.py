import ipaddress
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import IpRange
from .settings import settings


class IpOrPasswordMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # allow health and auth/user routes unconditionally
        if request.url.path.startswith("/health") or request.url.path.startswith("/users"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        allowed = False
        try:
            ip = ipaddress.ip_address(client_ip)
        except ValueError:
            ip = None

        if ip:
            # check prefixes in DB
            db: Session = SessionLocal()
            try:
                ranges = [r.prefix for r in db.query(IpRange).all()]
            finally:
                db.close()
            for pref in ranges:
                if client_ip.startswith(pref):
                    allowed = True
                    break

        if not allowed:
            # check header X-Access-Password
            if request.headers.get("X-Access-Password") == settings.default_access_password:
                allowed = True

        if not allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"detail": "Access denied: IP not allowed"})

        return await call_next(request)

