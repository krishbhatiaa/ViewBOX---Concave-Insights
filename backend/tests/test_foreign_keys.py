from app.models import SessionLocal, Survey, SurveyRule, engine


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
