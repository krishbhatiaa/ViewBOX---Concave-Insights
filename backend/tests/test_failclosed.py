from app import eligibility
from app.models import Member, SessionLocal, Survey
from conftest import make_survey, signup_member


def test_rule_exception_is_fail_closed(client, admin, monkeypatch):
    sid = make_survey(client, admin, "Fail Closed Survey", [
        {"rule_type": "age", "value": "18-99", "strict_or_flexible": "strict"},
    ], amount=100)
    assert signup_member(client, "9831111111", name="Fail Closed Person").status_code == 200

    def boom(*args, **kwargs):
        raise RuntimeError("rule checker crashed")

    monkeypatch.setattr(eligibility, "_check", boom)
    db = SessionLocal()
    try:
        member = db.query(Member).filter_by(phone="9831111111").first()
        survey = db.get(Survey, sid)
        result, reason = eligibility.evaluate(db, member, survey)
    finally:
        db.close()
    assert result == "Rejected"
    assert reason == "System error — please retry"
