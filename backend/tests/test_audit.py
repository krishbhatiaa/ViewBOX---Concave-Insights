from pathlib import Path

from app.models import AuditEvent, FraudFlag, Member, Payout, SessionLocal
from app.services import audit
from conftest import make_survey, signup_member

APP = Path(__file__).resolve().parents[1] / "app"


def _rows(client, admin, limit=500):
    r = client.get("/api/admin/audit", params={"limit": limit}, headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


def _count(rows, action):
    return sum(1 for row in rows if row["action"] == action)


def test_audit_log_helper_uses_explicit_actor_and_role():
    event_id = audit.log(7, "admin", "unit_test", "thing", 42, {"k": "v"}, "127.0.0.1")
    db = SessionLocal()
    try:
        row = db.get(AuditEvent, event_id)
        assert row.actor_id == 7 and row.actor_role == "admin"
        assert row.action == "unit_test" and row.resource_type == "thing" and row.resource_id == 42
        assert '"k": "v"' in row.details_json and row.ip == "127.0.0.1"
        db.delete(row)
        db.commit()
    finally:
        db.close()


def test_each_ops_action_creates_exactly_one_audit_row(client, admin):
    sid = make_survey(client, admin, "Audit Test Survey", [
        {"rule_type": "age", "value": "18-99", "strict_or_flexible": "strict"},
    ], amount=100)
    phone = "9820000001"
    assert signup_member(client, phone, name="Audit Person", dob="1990-01-01").status_code == 200

    db = SessionLocal()
    member_id = db.query(Member).filter_by(phone=phone).first().id
    payout = Payout(member_id=member_id, survey_id=sid, amount=100)
    flag = FraudFlag(member_id=member_id, flag_type="manual_test", details="test")
    db.add_all([payout, flag])
    db.commit()
    pid, fid = payout.id, flag.id
    db.close()

    rid = client.get("/api/admin/members", params={"q": "Audit Person"}, headers=admin).json()[0]["referral_id"]

    def check(action, call):
        before = _count(_rows(client, admin), action)
        r = call()
        assert r.status_code in (200, 201), r.text
        assert _count(_rows(client, admin), action) == before + 1

    check("referral_stage_changed",
          lambda: client.post(f"/api/admin/referrals/{rid}/stage", json={"stage": "Fit"}, headers=admin))
    check("payout_status_changed",
          lambda: client.post(f"/api/admin/payouts/{pid}/status", json={"status": "Approved"}, headers=admin))
    check("override_created", lambda: client.post("/api/admin/overrides", json={
        "member_id": member_id, "survey_id": sid, "reason": "audit test"}, headers=admin))
    oid = client.get("/api/admin/overrides", params={"member_id": member_id}, headers=admin).json()[0]["id"]
    check("override_deleted", lambda: client.delete(f"/api/admin/overrides/{oid}", headers=admin))
    check("fraud_flag_reviewed",
          lambda: client.post(f"/api/admin/fraud-flags/{fid}/review", json={"status": "Cleared"}, headers=admin))


def test_audit_endpoint_is_admin_only_newest_first_and_paginated(client, admin):
    assert client.get("/api/admin/audit").status_code in (401, 403)
    rows = _rows(client, admin)
    assert [r["id"] for r in rows] == sorted((r["id"] for r in rows), reverse=True)
    assert all({"actor_id", "actor_role", "action", "resource_type", "resource_id",
                "details", "ip", "created_at"} <= set(r) for r in rows)
    if len(rows) > 1:
        assert _rows(client, admin, limit=1)[0]["id"] == rows[0]["id"]
        assert _rows(client, admin, limit=1)[0]["id"] != rows[1]["id"]


def test_no_delete_route_and_all_ops_actions_are_wired():
    admin_src = (APP / "routers" / "admin.py").read_text(encoding="utf-8")
    referral_src = (APP / "services" / "referral.py").read_text(encoding="utf-8")
    assert '@router.delete("/api/admin/audit' not in admin_src
    assert '@router.get("/api/admin/audit"' in admin_src
    for action in ("payout_status_changed", "override_created", "override_deleted", "fraud_flag_reviewed"):
        assert action in admin_src
    assert "referral_stage_changed" in referral_src
    assert "audit_events" in (APP / "main.py").read_text(encoding="utf-8")
