from conftest import make_survey, member_token, signup_member


def test_failed_quality_completion_does_not_consume_quota_or_start_cooloff(client, admin):
    from app.models import Completion, Member, SessionLocal

    sid = make_survey(client, admin, "Quality Only Quota", [], quota=1)
    phone = "9930000301"
    assert signup_member(client, phone, name="Failed Quality Person", dob="1995-01-01").status_code == 200

    db = SessionLocal()
    try:
        m = db.query(Member).filter_by(phone=phone).first()
        db.add(Completion(member_id=m.id, survey_id=sid, quality_check_passed=False))
        db.commit()
    finally:
        db.close()

    mh = member_token(client, phone)
    assert client.get("/api/me", headers=mh).json()["next_eligible_date"] is None
    mine = next(x for x in client.get("/api/surveys", headers=mh).json() if x["id"] == sid)
    assert mine["result"] == "Approved", mine

    other = "9930000302"
    assert signup_member(client, other, name="Next In Line", dob="1995-01-01").status_code == 200
    theirs = next(x for x in client.get("/api/surveys", headers=member_token(client, other)).json()
                  if x["id"] == sid)
    assert theirs["result"] == "Approved", theirs
