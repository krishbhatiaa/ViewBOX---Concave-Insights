from datetime import datetime, timedelta

from conftest import make_survey, member_token, signup_member


def test_patch_survey_updates_allowed_fields(client, admin):
    sid = make_survey(client, admin, "Patchable Survey", [
        {"rule_type": "age", "value": "18-60", "strict_or_flexible": "strict"},
    ], quota=10, amount=100)
    deadline = (datetime.utcnow() + timedelta(days=3)).replace(microsecond=0)
    r = client.patch(f"/api/admin/surveys/{sid}", json={
        "status": "closed", "deadline": deadline.isoformat(), "quota": 3, "amount": 250,
    }, headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["id"] == sid and d["status"] == "closed"
    assert d["quota"] == 3 and d["amount"] == 250
    assert d["deadline"] == deadline.date().isoformat()
    row = next(x for x in client.get("/api/admin/surveys", headers=admin).json() if x["id"] == sid)
    assert (row["status"], row["quota"], row["amount"]) == ("closed", 3, 250)


def test_patch_survey_validation_not_found_and_auth(client, admin):
    sid = make_survey(client, admin, "Patch Validation Survey", [])
    assert client.patch("/api/admin/surveys/999999", json={"status": "live"}, headers=admin).status_code == 404
    for body in ({"status": "bogus"}, {"deadline": "2020-01-01T00:00:00"}, {"quota": 0},
                 {"quota": -2}, {"amount": -1}, {"title": "Renamed"}, {"description": "changed"}):
        r = client.patch(f"/api/admin/surveys/{sid}", json=body, headers=admin)
        assert r.status_code == 422, (body, r.text)
    assert client.patch(f"/api/admin/surveys/{sid}", json={"status": "draft"}).status_code == 401


def test_closing_survey_makes_member_rejected(client, admin):
    from app.eligibility import evaluate
    from app.models import Member, SessionLocal, Survey

    sid = make_survey(client, admin, "Closable Survey", [], quota=5)
    phone = "9920000201"
    assert signup_member(client, phone, name="Close Case", dob="1995-01-01").status_code == 200
    before = next(x for x in client.get("/api/surveys", headers=member_token(client, phone)).json()
                  if x["id"] == sid)
    assert before["result"] == "Approved", before

    r = client.patch(f"/api/admin/surveys/{sid}", json={"status": "closed"}, headers=admin)
    assert r.status_code == 200, r.text
    rows = client.get("/api/admin/members", params={"survey_id": sid, "q": "Close Case"}, headers=admin).json()
    row = next(x for x in rows if x["name"] == "Close Case")
    assert row["eligibility"]["result"] == "Rejected"
    assert "not open" in row["eligibility"]["reason"]

    db = SessionLocal()
    try:
        m = db.query(Member).filter_by(phone=phone).first()
        res, why = evaluate(db, m, db.get(Survey, sid))
        assert res == "Rejected" and "not open" in why
    finally:
        db.close()
