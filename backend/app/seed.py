from datetime import datetime, timedelta, date
from decimal import Decimal
from pathlib import Path
from .models import *
from . import security as sec
from .services.importer import run_import

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SAMPLE_CSV_NAMES = ("viewbox_respondent_sample.csv", "viewbox_respondents_sample.csv")


def sample_csv_path():
    for name in SAMPLE_CSV_NAMES:
        path = DATA_DIR / name
        if path.exists():
            return path
    return None


def import_sample_respondents(db):
    path = sample_csv_path()
    if path is None:
        return None
    text = path.read_text(encoding="utf-8-sig")
    return run_import(db, text, path.name, False)

def seed():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine); db = SessionLocal()
    db.add(AdminUser(email="admin@concave.test", password_hash=sec.hash_pw("admin123")))
    for n, t in [("WhatsApp - Mumbai Group", "whatsapp"), ("Staff - Priya", "staff"), ("Instagram", "instagram"), ("Facebook", "facebook"),
                 ("Website", "website"), ("Referral", "referral"), ("LinkedIn", "linkedin"), ("Meta Ads", "meta_ads")]:
        db.add(Source(name=n, type=t, unique_slug=n.lower().replace(" - ", "-").replace(" ", "-")))
    db.flush(); S = {s.name: s.id for s in db.query(Source)}
    def mem(i, name, dob, g, city, inc, ints, src, ref=None, stage="Lead", why=None, device_id=None):
        m = Member(phone=f"9000000{i:03d}", name=name, dob=dob, gender=g, city=city, income_range=inc, interests=ints, source_id=S[src], first_touch_source_id=S[src], referrer_id=ref, is_flagged=False, device_id=device_id)
        db.add(m); db.flush(); db.add(Referral(referrer_id=ref, referred_member_id=m.id, stage=stage, failure_reason=why)); return m
    p = mem(1, "Priya Shah", date(1995, 4, 12), "Female", "Mumbai", "10L+", "food,fashion", "Website")
    mem(2, "Rohan Mehta", date(1998, 1, 5), "Male", "Pune", "5-10L", "tech", "Referral", p.id)
    mem(3, "Sneha Iyer", date(1992, 9, 30), "Female", "Mumbai", "5-10L", "food", "Referral", p.id, "Fit")
    k = mem(4, "Karan Verma", date(1990, 6, 21), "Male", "Delhi", "10L+", "finance", "Referral", p.id, "Completed")
    mem(5, "Meera Nair", date(1988, 2, 2), "Female", "Chennai", "<5L", "travel", "Instagram")
    mem(6, "Anita Rao", date(date.today().year - 17, 1, 1), "Female", "Mumbai", "<5L", "food", "WhatsApp - Mumbai Group")
    mem(7, "Vikram Singh", date(1985, 8, 8), "Male", "Delhi", "10L+", "finance,tech", "LinkedIn", p.id, "Failed", "Did not match profile criteria")
    ring = [mem(10, "Ring Demo A", date(1991, 3, 1), "Female", "Mumbai", "5-10L", "food", "Referral"),
            mem(11, "Ring Demo B", date(1992, 4, 2), "Male", "Pune", "5-10L", "tech", "Referral"),
            mem(12, "Ring Demo C", date(1993, 5, 3), "Female", "Delhi", "5-10L", "travel", "Referral")]
    for member, referrer in zip(ring, ring[1:] + ring[:1]):
        member.referrer_id = referrer.id
        db.flush()
        db.query(Referral).filter_by(referred_member_id=member.id).update({"referrer_id": referrer.id})
    mem(13, "Device Twin A", date(1994, 6, 4), "Male", "Mumbai", "5-10L", "tech", "Website",
        device_id="demo-shared-device")
    mem(14, "Device Twin B", date(1995, 7, 5), "Female", "Mumbai", "5-10L", "food", "Website",
        device_id="demo-shared-device")
    now = datetime.utcnow()
    z = Survey(title="Zomato Dining Habits", description="food dining delivery", deadline=now + timedelta(days=10), quota=50, amount=Decimal("300.00"), interests="food,fashion")
    z.rules = [SurveyRule(rule_type="age", operator="between", value="18-35", strict_or_flexible="strict"), SurveyRule(rule_type="city", operator="in", value="Mumbai,Pune,Delhi", strict_or_flexible="flexible")]
    t = Survey(title="Titan Watch Preferences", description="watches fashion lifestyle", deadline=now + timedelta(days=12), quota=40, amount=Decimal("400.00"), interests="tech")
    t.rules = [SurveyRule(rule_type="age", operator="between", value="25-45", strict_or_flexible="strict"), SurveyRule(rule_type="income", operator="in", value="5-10L,10L+", strict_or_flexible="flexible")]
    i = Survey(title="ICICI Life Insurance Needs", description="finance insurance planning", deadline=now + timedelta(days=14), quota=30, amount=Decimal("500.00"), interests="insurance")
    i.rules = [SurveyRule(rule_type="age", operator="between", value="30-60", strict_or_flexible="strict")]
    db.add_all([z, t, i]); db.flush()
    db.add(Completion(member_id=k.id, survey_id=z.id, completed_at=now - timedelta(days=20), quality_check_passed=True))
    kr = db.query(Referral).filter_by(referred_member_id=k.id).first()
    db.add_all([Payout(member_id=k.id, survey_id=z.id, amount=Decimal("300.00"), status="Paid"), Payout(member_id=p.id, survey_id=z.id, referral_id=kr.id, amount=Decimal("100.00"), status="Pending")])
    sample = import_sample_respondents(db)
    db.commit(); db.close()
    print("Seeded. Admin: admin@concave.test / admin123 | Members: 9000000001..9000000007, ring 9000000010..9000000012, device pair 9000000013..9000000014")
    if sample:
        print(f"Bundled sample CSV: {sample['imported']} imported, {sample['fixed']} fixed, "
              f"{sample['warned']} warned, {sample['skipped']} skipped.")

if __name__ == "__main__": seed()
