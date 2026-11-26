from pathlib import Path

from app.models import AuditEvent, SessionLocal
from app.services import audit

APP = Path(__file__).resolve().parents[1] / "app"


def test_audit_log_appends_actor_action_and_details():
    db = SessionLocal()
    try:
        before = db.query(AuditEvent).count()
        event = audit.log(db, "unit_test", "thing", 42, actor={"sub": "admin@viewbox.test", "role": "admin"},
                          details={"k": "v"}, ip="127.0.0.1")
        db.commit()
        row = db.get(AuditEvent, event.id)
        assert row.action == "unit_test" and row.resource_type == "thing" and row.resource_id == 42
        assert row.actor_role == "admin" and row.actor_id is None
        assert '"k": "v"' in row.details_json and row.ip == "127.0.0.1"
        assert db.query(AuditEvent).count() == before + 1

        db.delete(row)
        db.commit()
    finally:
        db.close()


def test_audit_events_have_no_delete_endpoint_and_ops_actions_are_wired():
    source = (APP / "routers" / "admin.py").read_text(encoding="utf-8")
    for action in ("payout_status_changed", "referral_stage_changed", "override_created",
                   "override_deleted", "fraud_flag_reviewed"):
        assert action in source
    assert '@router.delete("/api/admin/audit' not in source

    bootstrap = (APP / "main.py").read_text(encoding="utf-8")
    assert "audit_events" in bootstrap and "sheet_sync_log" in bootstrap
