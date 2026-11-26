from decimal import Decimal

from app.models import Member, Payout, SessionLocal, Survey


def test_money_stores_exact_two_decimal_places():
    db = SessionLocal()
    try:
        m = Member(phone="9550000003", name="Money Person", city="Mumbai")
        s = Survey(title="Money Survey", description="test", amount=Decimal("300.005"))
        db.add_all([m, s])
        db.flush()
        p = Payout(member_id=m.id, survey_id=s.id, amount=Decimal("300.005"), status="Pending")
        db.add(p)
        db.commit()
        db.refresh(s)
        db.refresh(p)

        assert s.amount == Decimal("300.00")
        assert p.amount == Decimal("300.00")

        db.delete(p)
        db.flush()
        db.delete(s)
        db.flush()
        db.delete(m)
        db.commit()
    finally:
        db.close()
