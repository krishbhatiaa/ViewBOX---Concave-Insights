"""Google Sheets sync helpers and logging (endpoints live in routers/admin.py)."""
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import SheetSyncLog


class SheetSyncError(Exception):
    """Human-readable Google API failure surface as a 502 by the router."""


def log_sync(db: Session, entity_type: str, direction: str, status: str,
             error: str | None = None) -> SheetSyncLog:
    row = SheetSyncLog(entity_type=entity_type, direction=direction, status=status,
                       error_text=error, synced_at=datetime.utcnow())
    db.add(row)
    db.commit()
    return row


def last_sync(db: Session, entity_type: str = "members") -> dict:
    """Last push/pull summary used by the admin status card."""
    rows = db.query(SheetSyncLog).filter_by(entity_type=entity_type).order_by(SheetSyncLog.id.desc()).all()
    last = rows[0] if rows else None
    return {
        "last_push": next((r.synced_at.isoformat() for r in rows if r.direction == "push"), None),
        "last_pull": next((r.synced_at.isoformat() for r in rows if r.direction == "pull"), None),
        "status": last.status if last else "never",
        "error": last.error_text if last else None,
    }
