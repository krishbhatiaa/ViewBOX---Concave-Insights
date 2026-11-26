from datetime import datetime, date, timedelta
from .models import Completion, AdminOverride, EligibilityResult

COOL_OFF_DAYS = 90  # ~3 months

def age_of(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def record_result(db, member_id, survey_id, result, reason):
    """Persist a computed eligibility result: one row per member+survey, updated in place."""
    row = db.query(EligibilityResult).filter_by(member_id=member_id, survey_id=survey_id).first()
    if row is None:
        db.add(EligibilityResult(member_id=member_id, survey_id=survey_id, result=result, reason_text=reason))
    else:
        row.result, row.reason_text, row.computed_at = result, reason, datetime.utcnow()
    return result, reason

def _check(rule, m, today):
    v = rule.value
    if rule.rule_type == "age":
        if not m.dob: return False, "age unknown"
        lo, hi = [int(x) for x in v.split("-")]; a = age_of(m.dob, today)
        return lo <= a <= hi, f"age {a}, this survey needs {lo} to {hi}"
    field = {"city": m.city, "gender": m.gender, "income": m.income_range}[rule.rule_type]
    allowed = [x.strip().lower() for x in v.split(",")]
    if not field:  # imported rows can miss a field: say so in plain words instead of 'None'
        return False, f"{rule.rule_type} unknown, this survey needs one of {', '.join(x.strip() for x in v.split(','))}"
    return (field.lower() in allowed, f"{rule.rule_type} '{field}', this survey is for {', '.join(x.strip() for x in v.split(','))}")

def next_eligible_date(db, m, now=None):
    now = now or datetime.utcnow()
    last = db.query(Completion).filter(Completion.member_id == m.id, Completion.quality_check_passed == True)\
        .order_by(Completion.completed_at.desc()).first()
    if last and now < last.completed_at + timedelta(days=COOL_OFF_DAYS):
        return (last.completed_at + timedelta(days=COOL_OFF_DAYS)).date()
    return None

def evaluate(db, m, s, now=None):
    now = now or datetime.utcnow()
    if db.query(AdminOverride).filter_by(member_id=m.id, survey_id=s.id).first():
        return "Approved", "Approved by the ops team after manual review."
    d = next_eligible_date(db, m, now)
    if d: return "Rejected", f"Not eligible: you completed a survey recently. You can join again on {d:%d %b %Y}."
    if s.status != "live": return "Rejected", "Not eligible: this survey is not open."
    if s.deadline and now > s.deadline: return "Rejected", f"Not eligible: this survey closed on {s.deadline:%d %b %Y}."
    if s.quota and db.query(Completion).filter_by(survey_id=s.id, quality_check_passed=True).count() >= s.quota:
        return "Rejected", "Not eligible: this survey has reached its quota."
    soft = []
    for r in s.rules:
        ok, msg = _check(r, m, now.date())
        if not ok:
            if r.strict_or_flexible == "strict": return "Rejected", f"Not eligible: {msg}."
            soft.append(msg)
    if soft: return "Waitlisted", "Waitlisted: " + "; ".join(soft) + ". Ops may still approve you."
    return "Approved", "You meet all the requirements."
