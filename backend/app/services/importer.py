"""Messy CSV import: parse/plan rows, report fixes and skips, then commit.

The file is planned entirely in memory first (so a dry-run writes nothing), then
committed member by member. Bad rows are skipped with a human reason - never crash.
"""
import csv
import io
import json
import logging
from datetime import date, datetime

from ..deps import norm_phone, slugify
from ..models import Completion, ImportLog, Member, Referral, Source

log = logging.getLogger("viewbox.import")

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y",
                "%d/%m/%y", "%d-%m-%y", "%d.%m.%y", "%Y/%m/%d", "%m/%d/%Y")
FORMULA_PREFIXES = ("=", "+", "-", "@")
VALIDATED_FIELDS = {"phone", "mobile", "dob", "date_of_birth", "joined_on", "last_survey_completed_on"}


def safe_text(v):
    s = str(v or "").strip()
    return "'" + s if s.startswith(FORMULA_PREFIXES) else s


def norm_cell(key, value):
    key = (key or "").strip().lower()
    s = str(value or "").strip()
    return s if key in VALIDATED_FIELDS else safe_text(s)


def parse_date(v, floor=1920):
    """Read the date formats seen in messy exports (ISO, dd/mm/yyyy, dd-mm-yy, ...).

    Two-digit years pivot around today ('68' -> 1968, '25' -> 2025); impossible or future
    dates return None so the caller reports the row instead of guessing.
    """
    s = str(v or "").strip()
    if not s:
        return None
    today = date.today()
    for f in DATE_FORMATS:
        try:
            d = datetime.strptime(s, f).date()
        except ValueError:
            continue
        if "%y" in f and d.year > today.year:
            d = d.replace(year=d.year - 100)
        if floor < d.year <= today.year:
            return d
    return None


INCOME_BUCKETS = {  # messy export values -> the three buckets the profile form offers
    "below 3l": "<5L", "below 5l": "<5L", "<5l": "<5L", "0-5l": "<5L", "under 5l": "<5L",
    "3l-6l": "5-10L", "3-6l": "5-10L", "5-10l": "5-10L", "6l-10l": "5-10L", "5 lakh": "5-10L",
    "10l-20l": "10L+", "10l+": "10L+", "above 10l": "10L+", "above 20l": "10L+", "20l+": "10L+",
}


def norm_income(v):
    """-> (value, note, level): level 'fix' when we mapped it, 'warn' when we could not."""
    s = str(v or "").strip()
    if not s:
        return None, "no income in this row", "warn"
    hit = INCOME_BUCKETS.get(s.lower())
    if hit:
        return (hit, None, "fix") if hit.lower() == s.lower() else (hit, f"income '{s}' mapped to '{hit}'", "fix")
    return s, f"income '{s}' kept as written (profile options are <5L, 5-10L, 10L+)", "warn"


def plan_row(raw, srcs, seen):
    """Validate + normalise one CSV row without touching the database.

    Returns (plan, fixes, warns). Raises ValueError with a human reason to skip the row.
    """
    r = {(k or "").strip().lower(): norm_cell(k, v) for k, v in raw.items()}
    fixes, warns = [], []
    phone = norm_phone(r.get("phone") or r.get("mobile"))
    if not phone:
        raise ValueError("invalid or missing phone")
    if phone in seen:
        raise ValueError("duplicate phone")
    name = " ".join((r.get("name") or "").split())
    name = name if name.startswith("'") else name.title()
    if len(name) < 2:
        raise ValueError("missing name")
    raw_dob = r.get("dob") or r.get("date_of_birth") or ""
    dob = parse_date(raw_dob)
    if raw_dob and not dob:
        warns.append(f"date of birth '{raw_dob}' could not be read")
    g_raw = r.get("gender") or ""
    g = {"m": "Male", "male": "Male", "f": "Female", "female": "Female"}.get(g_raw.lower()) or ("Other" if g_raw else None)
    if g_raw and g != g_raw:
        fixes.append(f"gender '{g_raw}' -> {g}")
    if not g_raw:
        warns.append("no gender in this row")
    if (r.get("phone") or "") != phone:
        fixes.append("phone normalised")
    city_raw = r.get("city") or ""
    city = (city_raw.title() if city_raw and (city_raw.islower() or city_raw.isupper()) else city_raw) \
        if not city_raw.startswith("'") else city_raw
    if city != city_raw:
        fixes.append(f"city '{city_raw}' -> {city}")
    income, note, level = norm_income(r.get("income") or r.get("income_range"))
    if note:
        (fixes if level == "fix" else warns).append(note)
    src_name = r.get("source") or ""
    if "source" in r and not src_name:
        warns.append("no source in this row - the member will show as Unknown")
    elif src_name and not srcs.get(src_name.lower()):
        warns.append(f"source '{src_name}' is not set up yet - it will be created")
    raw_joined = r.get("joined_on") or ""
    joined = parse_date(raw_joined)
    if raw_joined and not joined:
        warns.append(f"join date '{raw_joined}' could not be read - using today")
    raw_done = r.get("last_survey_completed_on") or ""
    done = parse_date(raw_done)
    if raw_done and not done:
        warns.append(f"last survey date '{raw_done}' could not be read - no cool-off recorded")
    plan = {"phone": phone, "name": name, "dob": dob, "gender": g, "city": city or None,
            "income_range": income, "interests": r.get("interests", "").replace(";", ","),
            "source": srcs.get(src_name.lower()), "source_name": src_name,
            "legacy_id": (r.get("member_id") or "").strip().upper() or None,
            "ref_by": (r.get("referred_by") or "").strip().upper() or None,
            "joined": joined, "completed": done}
    return plan, fixes, warns


def run_import(db, text: str, filename: str, dry_run: bool):
    """Plan the whole file, report what happened, commit unless dry_run.

    Returns the summary dict the UI shows (total_rows/imported/fixed/warned/skipped/details).
    """
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return None  # caller turns this into a 422
    srcs = {s.name.lower(): s for s in db.query(Source)}
    seen = {m.phone for m in db.query(Member.phone)}
    entries, planned = {}, []
    for i, raw in enumerate(rows, start=2):
        try:
            plan, fixes, warns = plan_row(raw, srcs, seen)
            seen.add(plan["phone"])
            planned.append((i, plan, fixes, warns))
        except Exception as e:
            entries[i] = {"row": i, "action": "skipped", "reason": str(e)[:120]}
    # referred_by carries legacy ids (VB10002): link referrers once every row is planned
    by_legacy, by_phone = {}, {}
    for _, plan, _, _ in planned:
        if plan["legacy_id"]:
            by_legacy.setdefault(plan["legacy_id"], plan)
        by_phone.setdefault(plan["phone"], plan)
    for _, plan, _, warns in planned:
        if not plan["ref_by"]:
            continue
        target = by_legacy.get(plan["ref_by"]) or by_phone.get(plan["ref_by"])
        if target is plan:
            warns.append("self-referral ignored")
        elif not target:
            warns.append(f"referrer '{plan['ref_by']}' was not imported - no referral credited")
        else:
            plan["referrer"] = target
    fixed = warned = 0
    for i, plan, fixes, warns in planned:
        if warns:
            warned += 1
            entries[i] = {"row": i, "action": "warned", "reason": "; ".join(fixes + warns)[:400]}
        elif fixes:
            fixed += 1
            entries[i] = {"row": i, "action": "fixed", "reason": "; ".join(fixes)[:400]}
    detail = [entries[k] for k in sorted(entries)]
    added = len(planned)
    skipped = len(rows) - added
    summary = {"total_rows": len(rows), "imported": added, "fixed": fixed, "warned": warned,
               "skipped": skipped, "details": detail}
    log.info("import %s: %d rows -> %d imported, %d fixed, %d warned, %d skipped",
             filename, len(rows), added, fixed, warned, skipped)
    for d in detail:  # one log line per problem row so support can trace it
        log.warning("import %s row %s %s: %s", filename, d["row"], d["action"], d["reason"])
    if dry_run:
        return {"preview": True, **summary}  # nothing has been written - validation only
    for i, plan, fixes, warns in planned:
        s = plan["source"]
        if s is None and plan["source_name"]:  # sources are data: unknown names become real sources
            key = plan["source_name"].lower()
            s = srcs.get(key)
            if s is None:
                base = slugify(plan["source_name"]) or "source"
                slug, n = base, 2
                while db.query(Source).filter_by(unique_slug=slug).first():
                    slug, n = f"{base}-{n}", n + 1
                s = Source(name=plan["source_name"], type="imported", unique_slug=slug)
                db.add(s)
                db.flush()
                srcs[key] = s
        m = Member(phone=plan["phone"], name=plan["name"], dob=plan["dob"], gender=plan["gender"],
                   city=plan["city"], income_range=plan["income_range"], interests=plan["interests"],
                   source_id=s and s.id, first_touch_source_id=s and s.id)
        if plan["joined"]:
            m.created_at = datetime.combine(plan["joined"], datetime.min.time())
        db.add(m)
        db.flush()
        plan["_member"] = m
    for i, plan, fixes, warns in planned:
        m = plan["_member"]
        ref = plan.get("referrer")
        ref_id = ref["_member"].id if ref is not None else None
        if ref_id and ref_id != m.id:
            m.referrer_id = ref_id
        db.add(Referral(referrer_id=ref_id if ref_id and ref_id != m.id else None, referred_member_id=m.id))
        if plan["completed"]:  # legacy completion history -> starts the 3-month cool-off
            db.add(Completion(member_id=m.id, survey_id=None,
                              completed_at=datetime.combine(plan["completed"], datetime.min.time()),
                              quality_check_passed=True))
    db.add(ImportLog(filename=filename, total_rows=len(rows), fixed_count=fixed, skipped_count=skipped,
                     error_details_json=json.dumps(detail)))
    db.commit()
    return summary
