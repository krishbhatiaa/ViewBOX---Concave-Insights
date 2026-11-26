"""Append-only audit trail for ops actions (no update or delete endpoint)."""
import json

from sqlalchemy.orm import Session

from ..models import AuditEvent


def log(db: Session, action: str, resource_type: str, resource_id: int | None = None,
        actor=None, details=None, ip: str | None = None) -> AuditEvent:
    actor_id = None
    role = "system"
    if isinstance(actor, dict):
        role = actor.get("role") or "admin"
        raw_id = actor.get("sub")
        if str(raw_id).isdigit():
            actor_id = int(raw_id)
    event = AuditEvent(
        actor_id=actor_id,
        actor_role=role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details_json=json.dumps(details) if details is not None else None,
        ip=ip,
    )
    db.add(event)
    return event
