"""Shared FastAPI dependencies and small URL helpers used by every router."""
import re

from fastapi import Header, HTTPException, Request

from . import security as sec
from .models import Member, SessionLocal


def db_dep():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def auth(role):
    """Factory for the two route guards: member tokens and admin tokens."""

    def dep(authorization: str = Header(None)):
        t = sec.read_token((authorization or "").replace("Bearer ", ""))
        if not t or t["role"] != role:
            raise HTTPException(401, "Please log in again.")
        return t

    return dep


member_auth, admin_auth = auth("member"), auth("admin")


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm_phone(p):
    """-> valid 10-digit Indian mobile, else None (accepts +91, spaces, dashes)."""
    d = re.sub(r"\D", "", str(p or ""))[-10:]
    return d if re.fullmatch(r"[6-9]\d{9}", d) else None


def base_url(request: Request) -> str:
    """Origin the caller actually used (works behind Vite proxy and in production)."""
    return str(request.base_url).rstrip("/")


def link_for(src, request: Request) -> str:
    return f"{base_url(request)}/signup?src={sec.sign_link('src', src.unique_slug)}"


def me(t, db) -> Member:
    m = db.get(Member, t["sub"])
    if not m:
        raise HTTPException(401, "Please log in again.")
    return m


def client_ip(request: Request) -> str | None:
    """Caller IP, honouring X-Forwarded-For when a proxy sets it."""
    return ((request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
            or (request.client.host if request.client else None))
