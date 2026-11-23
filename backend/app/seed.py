from datetime import datetime, timedelta, date
from .models import *
from . import security as sec

def seed():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine); db = SessionLocal()
    db.add(AdminUser(email="admin@concave.test", password_hash=sec.hash_pw("admin123")))
    for n, t in [("WhatsApp - Mumbai Group", "whatsapp"), ("Staff - Priya", "staff"), ("Instagram", "instagram"), ("Facebook", "facebook"),
                 ("Website", "website"), ("Referral", "referral"), ("LinkedIn", "linkedin"), ("Meta Ads", "meta_ads")]:
        db.add(Source(name=n, type=t, unique_slug=n.lower().replace(" - ", "-").replace(" ", "-")))
    db.flush(); S = {s.name: s.id for s in db.query(Source)}
    def mem(i, name, dob, g, city, inc, ints, src, ref=None, stage="Lead", why=None):
        m = Member(phone=f"900000000{i}", name=name, dob=dob, gender=g, city=city, income_range=inc, interests=ints, source_id=S[src], first_touch_source_id=S[src], referrer_id=ref)
        db.add(m); db.flush(); db.add(Referral(referrer_id=ref, referred_member_id=m.id, stage=stage, failure_reason=why)); return m
    p = mem(1, "Priya Shah", date(1995, 4, 12), "Female", "Mumbai", "10L+", "food,fashion", "Website")
    mem(2, "Rohan Mehta", date(1998, 1, 5), "Male", "Pune", "5-10L", "tech", "Referral", p.id)
    mem(3, "Sneha Iyer", date(1992, 9, 30), "Female", "Mumbai", "5-10L", "food", "Referral", p.id, "Fit")
    k = mem(4, "Karan Verma", date(1990, 6, 21), "Male", "Delhi", "10L+", "finance", "Referral", p.id, "Completed")
    mem(5, "Meera Nair", date(1988, 2, 2), "Female", "Chennai", "<5L", "travel", "Instagram")
    mem(6, "Anita Rao", date(date.today().year - 17, 1, 1), "Female", "Mumbai", "<5L", "food", "WhatsApp - Mumbai Group")
    mem(7, "Vikram Singh", date(1985, 8, 8), "Male", "Delhi", "10L+", "finance,tech", "LinkedIn", p.id, "Failed", "Did not match profile criteria")
    now = datetime.utcnow()
    z = Survey(title="Zomato Dining Habits", description="food dining delivery", deadline=now + timedelta(days=10), quota=50, amount=300)
    z.rules = [SurveyRule(rule_type="age", operator="between", value="18-35", strict_or_flexible="strict"), SurveyRule(rule_type="city", operator="in", value="Mumbai,Pune,Delhi", strict_or_flexible="flexible")]
    t = Survey(title="Titan Watch Preferences", description="watches fashion lifestyle", deadline=now + timedelta(days=12), quota=40, amount=400)
    t.rules = [SurveyRule(rule_type="age", operator="between", value="25-45", strict_or_flexible="strict"), SurveyRule(rule_type="income", operator="in", value="5-10L,10L+", strict_or_flexible="flexible")]
    i = Survey(title="ICICI Life Insurance Needs", description="finance insurance planning", deadline=now + timedelta(days=14), quota=30, amount=500)
    i.rules = [SurveyRule(rule_type="age", operator="between", value="30-60", strict_or_flexible="strict")]
    db.add_all([z, t, i]); db.flush()
    db.add(Completion(member_id=k.id, survey_id=z.id, completed_at=now - timedelta(days=20), quality_check_passed=True))
    kr = db.query(Referral).filter_by(referred_member_id=k.id).first()
    db.add_all([Payout(member_id=k.id, survey_id=z.id, amount=300, status="Paid"), Payout(member_id=p.id, survey_id=z.id, referral_id=kr.id, amount=100, status="Pending")]); db.commit(); db.close()
    print("Seeded. Admin: admin@concave.test / admin123 | Members: phones 9000000001..9000000007")

if __name__ == "__main__": seed()
