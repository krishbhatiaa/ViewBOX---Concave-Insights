"""Append-only audit trail for ops actions (no update or delete endpoint)."""
import json
import re

from sqlalchemy.orm import Session

from ..models import AuditEvent, SessionLocal

PHONE_RE = re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)")
SENSITIVE_KEYS = {"phone", "otp", "token", "password", "authorization", "body", "request_body"}


def one_line(value) -> str:
    """Keep untrusted values on a single log line."""
    return str(value if value is not None else "").replace("\r", "").replace("\n", "")


def _scrub(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return {one_line(k): ("[redacted]" if one_line(k).lower() in SENSITIVE_KEYS else _scrub(v))
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    if isinstance(value, str):
        return PHONE_RE.sub("[redacted]", one_line(value))
    return value


def identity(actor) -> tuple[int | None, str]:
    """Turn an auth payload into the audit actor columns."""
    if isinstance(actor, dict):
        raw = actor.get("sub")
        actor_id = int(raw) if str(raw).isdigit() else None
        return actor_id, actor.get("role") or "admin"
    return None, "system"


def log(actor_id, role, action, resource_type, resource_id=None, details=None, ip=None, db=None) -> int:
    own_session = db is None
    session = db or SessionLocal()
    try:
        event = AuditEvent(
            actor_id=actor_id,
            actor_role=one_line(role or "system"),
            action=one_line(action),
            resource_type=one_line(resource_type),
            resource_id=resource_id,
            details_json=json.dumps(_scrub(details), default=str) if details is not None else None,
            ip=one_line(ip),
        )
        session.add(event)
        if own_session:
            session.commit()
        else:
            session.flush()
        return event.id
    finally:
        if own_session:
            session.close()
