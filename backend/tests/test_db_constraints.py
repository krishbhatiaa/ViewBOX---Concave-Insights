import pytest
from sqlalchemy.exc import IntegrityError

from app.models import AdminOverride, EligibilityResult, Member, SessionLocal, Survey


def test_duplicate_eligibility_and_override_pairs_blocked_at_db_level():
    db = SessionLocal()
    created = {"members": [], "surveys": [], "elig": [], "override": []}
    try:
        m = Member(phone="9550000001", name="Constraint Person", city="Mumbai")
        s = Survey(title="Constraint Survey", description="test", amount=0)
        db.add_all([m, s])
        db.commit()
        created["members"].append(m.id)
        created["surveys"].append(s.id)

        e = EligibilityResult(member_id=m.id, survey_id=s.id, result="Approved", reason_text="ok")
        db.add(e)
        db.commit()
        created["elig"].append(e.id)
        db.add(EligibilityResult(member_id=m.id, survey_id=s.id, result="Rejected", reason_text="duplicate"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        o = AdminOverride(member_id=m.id, survey_id=s.id, overridden_by="admin@viewbox.test", reason="manual")
        db.add(o)
        db.commit()
        created["override"].append(o.id)
        db.add(AdminOverride(member_id=m.id, survey_id=s.id, overridden_by="admin@viewbox.test", reason="duplicate"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        for model, key in ((EligibilityResult, "elig"), (AdminOverride, "override"),
                           (Member, "members"), (Survey, "surveys")):
            for row_id in created[key]:
                db.query(model).filter_by(id=row_id).delete()
        db.commit()
        db.close()
