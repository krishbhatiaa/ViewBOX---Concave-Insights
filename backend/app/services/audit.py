"""Append-only audit trail for ops actions (no update or delete endpoint)."""
import json

from sqlalchemy.orm import Session

from ..models import AuditEvent, SessionLocal


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
            actor_role=role or "system",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details_json=json.dumps(details) if details is not None else None,
            ip=ip,
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
