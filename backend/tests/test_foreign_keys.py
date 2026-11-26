from sqlalchemy import text

from app.models import Completion, Member, Referral, SessionLocal, Survey, SurveyRule, engine


def test_sqlite_foreign_keys_pragma_is_enabled():
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_deleting_survey_with_rules_cascades():
    db = SessionLocal()
    try:
        s = Survey(title="Foreign Key Survey", description="test", amount=0)
        s.rules = [SurveyRule(rule_type="city", operator="in", value="Mumbai", strict_or_flexible="strict")]
        db.add(s)
        db.commit()
        survey_id, rule_id = s.id, s.rules[0].id

        db.delete(s)
        db.commit()

        assert db.get(Survey, survey_id) is None
        assert db.get(SurveyRule, rule_id) is None
    finally:
        db.close()


def test_deleting_member_cascades_completions_and_referrals_at_db_level():
    db = SessionLocal()
    try:
        m = Member(phone="9550000004", name="Cascade Person", city="Mumbai")
        db.add(m)
        db.flush()
        completion = Completion(member_id=m.id, survey_id=None, quality_check_passed=True)
        referral = Referral(referrer_id=None, referred_member_id=m.id, stage="Lead")
        db.add_all([completion, referral])
        db.commit()
        member_id, completion_id, referral_id = m.id, completion.id, referral.id

        with engine.begin() as conn:  # raw DELETE proves the ON DELETE rules, not ORM cascades
            conn.execute(text("DELETE FROM members WHERE id = :id"), {"id": member_id})

        db.expire_all()
        assert db.get(Completion, completion_id) is None
        assert db.get(Referral, referral_id) is None
    finally:
        db.close()
