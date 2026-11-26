from decimal import Decimal

from app.models import Member, Payout, SessionLocal
from conftest import make_survey, signup_member


def test_batch_approve_is_partial_and_keeps_paid_gate(client, admin):
    sid = make_survey(client, admin, "Batch Payout Survey", [
        {"rule_type": "age", "value": "18-99", "strict_or_flexible": "strict"},
    ], amount=100)
    assert signup_member(client, "9840000001", name="Batch Person", dob="1990-01-01").status_code == 200

    db = SessionLocal()
    member_id = db.query(Member).filter_by(phone="9840000001").first().id
    pending_a = Payout(member_id=member_id, survey_id=sid, amount=Decimal("100.00"))
    pending_b = Payout(member_id=member_id, survey_id=sid, amount=Decimal("200.00"))
    paid = Payout(member_id=member_id, survey_id=sid, amount=Decimal("300.00"), status="Paid")
    db.add_all([pending_a, pending_b, paid])
    db.commit()
    ids = pending_a.id, pending_b.id, paid.id
    db.close()

    r = client.post("/api/admin/payouts/batch-approve",
                    json={"ids": [ids[0], 999999, ids[1], ids[2]]}, headers=admin)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["approved"] == 2 and data["failed"] == 2
    by_id = {x["id"]: x for x in data["results"]}
    assert by_id[ids[0]]["ok"] and by_id[ids[1]]["ok"]
    assert not by_id[999999]["ok"] and "not found" in by_id[999999]["error"].lower()
    assert not by_id[ids[2]]["ok"] and "paid" in by_id[ids[2]]["error"].lower()

    db = SessionLocal()
    try:
        statuses = {i: db.get(Payout, i).status for i in ids if i != 999999}
        assert statuses == {ids[0]: "Approved", ids[1]: "Approved", ids[2]: "Paid"}
        assert db.get(Payout, 999999) is None
    finally:
        db.close()
