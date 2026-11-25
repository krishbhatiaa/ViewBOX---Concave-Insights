import io
import os
from datetime import date, timedelta

from conftest import admin_headers, make_survey, member_token, signup_member

# ---------- auth & signup ----------

def test_otp_login_and_me(client):
    h = signup_member(client, "9810000001", name="Otp User")
    assert h.status_code == 200, h.text
    mh = member_token(client, "9810000001")
    r = client.get("/api/me", headers=mh)
    assert r.status_code == 200
    assert r.json()["name"] == "Otp User"
    assert "XXXXXX" in r.json()["phone"]  # masked


def test_auth_required(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/admin/members").status_code == 401


def test_signup_with_signed_source_link(client, admin):
    s = client.post("/api/admin/sources", json={"name": "Test Channel A", "type": "whatsapp"}, headers=admin)
    assert s.status_code == 201, s.text
    link = s.json()["link"]
    src_token = link.split("src=")[1]
    h = signup_member(client, "9810000002", name="Linked Person", src=src_token)
    assert h.status_code == 200, h.text
    rows = client.get("/api/admin/members?q=Linked Person", headers=admin).json()
    assert rows and rows[0]["source"] == "Test Channel A"


def test_signup_fallback_how_heard(client, admin):
    sources = client.get("/api/admin/sources", headers=admin).json()
    website = next(x for x in sources if x["name"] == "Website")
    h = signup_member(client, "9810000003", name="Fallback Person", how_heard_source_id=website["id"])
    assert h.status_code == 200, h.text
    rows = client.get("/api/admin/members?q=Fallback Person", headers=admin).json()
    assert rows and rows[0]["source"] == "Website"


def test_signup_duplicate_phone_is_flagged(client, admin):
    assert signup_member(client, "9810000004", name="Dupe Target").status_code == 200
    # second attempt with the same phone (fresh OTP) must 409 and raise a flag
    otp = client.post("/api/otp/request", json={"phone": "9810000004"}).json()["otp"]
    r = client.post("/api/signup", json={"phone": "9810000004", "otp": otp, "name": "Dupe Target 2",
                                         "dob": "1995-01-01", "gender": "Male", "city": "Pune",
                                         "income_range": "5-10L", "interests": []})
    assert r.status_code == 409
    flags = client.get("/api/admin/fraud-flags?status=open", headers=admin).json()
    assert any(f["flag_type"] == "duplicate_signup" and f["phone"] == "9810000004" for f in flags)
    flagged = client.get("/api/admin/members?status=flagged", headers=admin).json()
    assert any(x["phone"] == "9810000004" for x in flagged)


def test_referral_link_and_masked_view(client, admin):
    h = signup_member(client, "9810000005", name="Referrer Person")
    assert h.status_code == 200
    mh = member_token(client, "9810000005")
    link = client.get("/api/me", headers=mh).json()["referral_link"]
    ref_token = link.split("ref=")[1]
    h2 = signup_member(client, "9810000006", name="Friend Person", ref=ref_token)
    assert h2.status_code == 200, h2.text
    refs = client.get("/api/me/referrals", headers=mh).json()
    assert refs and refs[0]["friend"] == "Friend Person"
    assert "XXXXXX" in refs[0]["phone"]
    assert refs[0]["stage"] == "Lead"


# ---------- eligibility ----------

def _zomato(client, admin):
    return make_survey(client, admin, "Zomato Dining Habits", [
        {"rule_type": "age", "value": "18-35", "strict_or_flexible": "strict"},
        {"rule_type": "city", "value": "Mumbai,Pune,Delhi", "strict_or_flexible": "flexible"},
    ], amount=300, quota=50)


def test_eligibility_approved_rejected_waitlisted(client, admin):
    sid = _zomato(client, admin)
    # under-age -> Rejected with plain reason
    signup_member(client, "9810000007", name="Minor Person", dob="2009-06-01")
    r = client.get("/api/surveys", headers=member_token(client, "9810000007")).json()
    z = next(x for x in r if x["id"] == sid)
    assert z["result"] == "Rejected"
    assert "age" in z["reason"] and "18 to 35" in z["reason"]
    # in range + matching city -> Approved
    signup_member(client, "9810000008", name="Good Person", dob="1995-01-01", city="Mumbai")
    r = client.get("/api/surveys", headers=member_token(client, "9810000008")).json()
    z = next(x for x in r if x["id"] == sid)
    assert z["result"] == "Approved"
    # flexible city rule fails -> Waitlisted
    signup_member(client, "9810000009", name="Chennai Person", dob="1995-01-01", city="Chennai")
    r = client.get("/api/surveys", headers=member_token(client, "9810000009")).json()
    z = next(x for x in r if x["id"] == sid)
    assert z["result"] == "Waitlisted"
    assert "city" in z["reason"]


def test_cool_off_blocks_and_shows_date(client, admin):
    sid = _zomato(client, admin)  # same title -> unique? title not unique; ok, creates another
    from app.models import Completion, Member, SessionLocal
    phone = "9810000010"
    signup_member(client, phone, name="Cooloff Person", dob="1995-01-01", city="Mumbai")
    db = SessionLocal()
    m = db.query(Member).filter_by(phone=phone).first()
    db.add(Completion(member_id=m.id, survey_id=sid, quality_check_passed=True))
    db.commit(); db.close()
    mh = member_token(client, phone)
    me = client.get("/api/me", headers=mh).json()
    assert me["next_eligible_date"]  # re-eligibility date surfaced
    r = client.get("/api/surveys", headers=mh).json()
    z = next(x for x in r if x["id"] == sid)
    assert z["result"] == "Rejected"
    assert "can join again" in z["reason"]


def test_admin_manual_override(client, admin):
    sid = _zomato(client, admin)
    phone = "9810000011"
    signup_member(client, phone, name="Override Person", dob="2009-06-01")  # under-age -> Rejected
    mh = member_token(client, phone)
    z = next(x for x in client.get("/api/surveys", headers=mh).json() if x["id"] == sid)
    assert z["result"] == "Rejected"
    member_id = client.get("/api/me", headers=mh).json()["id"]
    r = client.post("/api/admin/overrides", json={"member_id": member_id, "survey_id": sid,
                                                  "reason": "Client asked for this person"},
                    headers=admin)
    assert r.status_code == 201, r.text
    # duplicate override rejected
    r2 = client.post("/api/admin/overrides", json={"member_id": member_id, "survey_id": sid,
                                                   "reason": "again"}, headers=admin)
    assert r2.status_code == 409
    z = next(x for x in client.get("/api/surveys", headers=mh).json() if x["id"] == sid)
    assert z["result"] == "Approved"
    assert "manual review" in z["reason"]
    # remove -> rules apply again
    oid = client.get("/api/admin/overrides", params={"member_id": member_id}, headers=admin).json()[0]["id"]
    assert client.delete(f"/api/admin/overrides/{oid}", headers=admin).status_code == 200
    z = next(x for x in client.get("/api/surveys", headers=mh).json() if x["id"] == sid)
    assert z["result"] == "Rejected"


# ---------- admin: grid, stages, payouts ----------

def test_grid_search_filter_export(client, admin):
    signup_member(client, "9810000012", name="Zebra Person", city="Kolkata")
    rows = client.get("/api/admin/members", params={"q": "zebra"}, headers=admin).json()
    assert rows and rows[0]["name"] == "Zebra Person"
    rows = client.get("/api/admin/members", params={"city": "kolkata"}, headers=admin).json()
    assert any(x["name"] == "Zebra Person" for x in rows)
    r = client.get("/api/admin/members/export", params={"q": "zebra"}, headers=admin)
    assert r.status_code == 200 and "Zebra Person" in r.text and r.text.startswith("id,")


def test_eligibility_results_are_saved(client, admin):
    """Every computed result lands in eligibility_results (one row per member+survey)."""
    from app.models import EligibilityResult, Member, SessionLocal
    sid = _zomato(client, admin)
    signup_member(client, "9810000051", name="Saved Rejected", dob="2009-06-01")
    signup_member(client, "9810000052", name="Saved Approved", dob="1995-01-01", city="Mumbai")
    for phone in ("9810000051", "9810000052"):  # member views the survey list -> results persisted
        assert client.get("/api/surveys", headers=member_token(client, phone)).status_code == 200
    db = SessionLocal()
    m1 = db.query(Member).filter_by(phone="9810000051").first()
    m2 = db.query(Member).filter_by(phone="9810000052").first()
    r1 = db.query(EligibilityResult).filter_by(member_id=m1.id, survey_id=sid).first()
    r2 = db.query(EligibilityResult).filter_by(member_id=m2.id, survey_id=sid).first()
    assert r1 and r1.result == "Rejected" and "age" in r1.reason_text
    assert r2 and r2.result == "Approved" and r2.reason_text
    db.close()
    # recomputing updates the same row instead of appending duplicates
    client.get("/api/surveys", headers=member_token(client, "9810000052"))
    db = SessionLocal()
    assert db.query(EligibilityResult).filter_by(member_id=m2.id, survey_id=sid).count() == 1
    db.close()


def test_grid_filter_by_survey_result(client, admin):
    """Grid can filter by Approved / Rejected / Waitlisted for a chosen survey."""
    sid = _zomato(client, admin)
    signup_member(client, "9810000053", name="Grid Approved Person", dob="1995-01-01", city="Mumbai")
    signup_member(client, "9810000054", name="Grid Rejected Person", dob="2009-06-01")
    signup_member(client, "9810000055", name="Grid Waitlisted Person", dob="1995-01-01", city="Chennai")
    # eligibility status without a survey -> clear 422
    r = client.get("/api/admin/members", params={"status": "Approved"}, headers=admin)
    assert r.status_code == 422 and "survey" in r.json()["detail"].lower()
    # survey selected: every row carries its saved result + plain reason
    rows = client.get("/api/admin/members", params={"survey_id": sid, "q": "Grid "}, headers=admin).json()
    by_name = {x["name"]: x["eligibility"] for x in rows}
    assert by_name["Grid Approved Person"]["result"] == "Approved"
    assert by_name["Grid Rejected Person"]["result"] == "Rejected" and "age" in by_name["Grid Rejected Person"]["reason"]
    assert by_name["Grid Waitlisted Person"]["result"] == "Waitlisted"
    # filtered views keep only the matching result
    rows = client.get("/api/admin/members", params={"survey_id": sid, "status": "Approved", "q": "Grid "}, headers=admin).json()
    assert [x["name"] for x in rows] == ["Grid Approved Person"]
    rows = client.get("/api/admin/members", params={"survey_id": sid, "status": "Waitlisted", "q": "Grid "}, headers=admin).json()
    assert [x["name"] for x in rows] == ["Grid Waitlisted Person"]
    rows = client.get("/api/admin/members", params={"survey_id": sid, "status": "Rejected", "q": "Grid "}, headers=admin).json()
    assert [x["name"] for x in rows] == ["Grid Rejected Person"]
    # unknown survey -> 404
    assert client.get("/api/admin/members", params={"survey_id": 999999}, headers=admin).status_code == 404


def test_export_excel_and_csv(client, admin):
    """The current grid view downloads as .xlsx as well as .csv."""
    from io import BytesIO
    from openpyxl import load_workbook
    signup_member(client, "9810000056", name="Excel Person", city="Mumbai")
    r = client.get("/api/admin/members/export", params={"q": "Excel Person", "format": "xlsx"}, headers=admin)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")
    assert "members.xlsx" in r.headers["content-disposition"]
    ws = load_workbook(BytesIO(r.content)).active
    grid = list(ws.iter_rows(values_only=True))
    assert grid[0][:3] == ("id", "name", "phone")
    assert any("Excel Person" in row for row in grid)
    # csv stays the default and an unknown format is rejected
    r = client.get("/api/admin/members/export", params={"q": "Excel Person"}, headers=admin)
    assert r.headers["content-type"].startswith("text/csv") and "Excel Person" in r.text
    assert client.get("/api/admin/members/export", params={"format": "pdf"}, headers=admin).status_code == 422
    # with a survey the sheet also carries eligibility + reason columns
    sid = _zomato(client, admin)
    r = client.get("/api/admin/members/export", params={"q": "Excel Person", "survey_id": sid, "format": "xlsx"}, headers=admin)
    ws = load_workbook(BytesIO(r.content)).active
    header = [c.value for c in next(ws.iter_rows(max_row=1))]
    assert "eligibility" in header and "eligibility_reason" in header
    assert any(c.value == "Approved" for row in ws.iter_rows(min_row=2) for c in row)


def test_stage_flow_and_payout_approval_gate(client, admin):
    sid = make_survey(client, admin, "Payout Test Survey", [
        {"rule_type": "age", "value": "18-99", "strict_or_flexible": "strict"},
    ], amount=250)
    signup_member(client, "9810000013", name="Stage Person", dob="1992-01-01")
    rows = client.get("/api/admin/members", params={"q": "Stage Person"}, headers=admin).json()
    rid = rows[0]["referral_id"]
    # Fit
    assert client.post(f"/api/admin/referrals/{rid}/stage", json={"stage": "Fit"}, headers=admin).status_code == 200
    # Completed requires a survey
    r = client.post(f"/api/admin/referrals/{rid}/stage", json={"stage": "Completed"}, headers=admin)
    assert r.status_code == 422
    # Failed requires a reason
    r = client.post(f"/api/admin/referrals/{rid}/stage", json={"stage": "Failed"}, headers=admin)
    assert r.status_code == 422
    # Completed with survey + quality pass creates payouts
    r = client.post(f"/api/admin/referrals/{rid}/stage",
                    json={"stage": "Completed", "survey_id": sid, "quality_check_passed": True}, headers=admin)
    assert r.status_code == 200, r.text
    payouts = client.get("/api/admin/payouts", headers=admin).json()
    p = next(x for x in payouts if x["member"] == "Stage Person")
    assert p["kind"] == "Survey payment" and p["status"] == "Pending" and p["amount"] == 250
    # Paid before Approved is blocked
    r = client.post(f"/api/admin/payouts/{p['id']}/status", json={"status": "Paid"}, headers=admin)
    assert r.status_code == 409
    assert client.post(f"/api/admin/payouts/{p['id']}/status", json={"status": "Approved"}, headers=admin).status_code == 200
    assert client.post(f"/api/admin/payouts/{p['id']}/status", json={"status": "Paid"}, headers=admin).status_code == 200
    # Completed is irreversible
    r = client.post(f"/api/admin/referrals/{rid}/stage", json={"stage": "Fit"}, headers=admin)
    assert r.status_code == 409


def test_source_stats(client, admin):
    stats = client.get("/api/admin/source-stats", headers=admin).json()
    assert any(x["source"] == "Website" and x["signups"] >= 1 for x in stats)


# ---------- Meta leads ----------

def test_meta_lead_create_dedupe_invalid(client):
    lead = {"lead_id": "L-TEST-1", "form_id": "F1", "campaign_id": "C9", "ad_id": "A1",
            "time": "2026-11-20T10:00:00Z",
            "fields": [{"name": "full_name", "values": ["Meta Person"]},
                       {"name": "phone_number", "values": ["+919812345678"]},
                       {"name": "city", "values": ["Pune"]}]}
    r = client.post("/api/meta/lead", json=lead)
    assert r.status_code == 200 and r.json()["status"] == "created"
    r = client.post("/api/meta/lead", json=lead)
    assert r.json()["status"] == "duplicate"
    bad = {"lead_id": "L-TEST-2", "fields": {"name": "X", "phone": "123"}}
    assert client.post("/api/meta/lead", json=bad).status_code == 422


# ---------- CSV import (preview then commit) ----------

def test_import_preview_then_commit(client, admin):
    csv = ("name,phone,dob,gender,city,income,interests\n"
           "Import One,98222 33445,1992-05-05,Male,Pune,5-10L,tech\n"
           "Bad Row,12345,1990-01-01,Male,Delhi,5-10L,tech\n")
    before = len(client.get("/api/admin/members", headers=admin).json())
    files = {"file": ("messy.csv", io.BytesIO(csv.encode()), "text/csv")}
    # preview: nothing saved
    r = client.post("/api/admin/import", params={"dry_run": "true"}, files=files, headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["preview"] is True and d["total_rows"] == 2 and d["imported"] == 1 and d["fixed"] == 1 and d["skipped"] == 1
    assert len(client.get("/api/admin/members", headers=admin).json()) == before
    # confirm: saved
    files = {"file": ("messy.csv", io.BytesIO(csv.encode()), "text/csv")}
    r = client.post("/api/admin/import", files=files, headers=admin)
    d = r.json()
    assert "preview" not in d and d["imported"] == 1
    assert len(client.get("/api/admin/members", headers=admin).json()) == before + 1
    rows = client.get("/api/admin/members", params={"q": "Import One"}, headers=admin).json()
    assert rows and rows[0]["phone"] == "9822233445"  # normalised


def _max_member_id(db):
    from app.models import Member
    row = db.query(Member.id).order_by(Member.id.desc()).first()
    return row[0] if row else 0


def test_import_real_sample_file(client, admin):
    """The real messy export (189 rows, data/viewbox_respondents_sample.csv) must import
    without crashing and keep its dates, sources, referrers and income buckets."""
    from app.models import Completion, Member, SessionLocal, Source
    path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "viewbox_respondents_sample.csv")
    with open(path, "rb") as fh:
        raw = fh.read()
    db = SessionLocal(); max_before = _max_member_id(db); db.close()
    files = lambda: {"file": ("viewbox_respondents_sample.csv", io.BytesIO(raw), "text/csv")}
    # preview: reports, writes nothing
    d = client.post("/api/admin/import", params={"dry_run": "true"}, files=files(), headers=admin).json()
    assert d["preview"] is True and d["total_rows"] == 189
    assert d["imported"] + d["skipped"] == 189 and d["imported"] >= 160 and d["skipped"] >= 20
    assert {x["action"] for x in d["details"]} <= {"fixed", "warned", "skipped"}
    db = SessionLocal(); assert _max_member_id(db) == max_before; db.close()
    # commit
    d = client.post("/api/admin/import", files=files(), headers=admin).json()
    assert "preview" not in d and d["imported"] == d["total_rows"] - d["skipped"]
    db = SessionLocal()
    new = db.query(Member).filter(Member.id > max_before).all()
    assert len(new) == d["imported"]
    by_phone = {m.phone: m for m in new}
    # date_of_birth header is honoured, including 2-digit years
    assert by_phone["9021331114"].dob == date(1989, 2, 25)   # "25/02/1989"
    assert by_phone["8728547667"].dob == date(1984, 3, 1)    # "01-03-84" -> 1984, not 2084
    assert sum(1 for m in new if m.dob) >= len(new) - 2
    # income values are mapped onto the three buckets the profile form offers
    assert {m.income_range for m in new if m.income_range} <= {"<5L", "5-10L", "10L+"}
    assert by_phone["9958519043"].income_range == "<5L"      # "Below 3L"
    # unknown source names become real sources instead of being dropped
    names = {s.name for s in db.query(Source)}
    assert {"WhatsApp Group - Pune", "insta"} <= names
    assert sum(1 for m in new if m.source_id) >= len(new) - 5  # only blank-source rows are unattributed
    # referred_by (legacy member ids) credits the referrer
    assert sum(1 for m in new if m.referrer_id) >= 25
    # last_survey_completed_on becomes a completion, so the 3-month cool-off applies
    comps = db.query(Completion).filter(Completion.survey_id == None, Completion.member_id > max_before).count()
    assert comps >= 70
    # joined_on is honoured instead of stamping everything with today
    assert sum(1 for m in new if m.created_at.date() != date.today()) >= len(new) - 2
    db.close()


def test_import_dates_referrer_and_unknown_source(client, admin):
    """Column-level behaviour: legacy ids link referrers, unknown sources are created,
    messy dates are parsed, and problems are reported as 'warned' not hidden."""
    from app.models import Completion, Member, Referral, SessionLocal, Source
    recent = (date.today() - timedelta(days=10)).strftime("%d/%m/%Y")
    csv = ("member_id,name,phone,gender,date_of_birth,city,income_range,source,referred_by,joined_on,last_survey_completed_on\n"
           "VBX1,Import Referrer,98333 11111,F,01-03-84,Pune,Below 3L,LinkedIn,,01-08-25,\n"
           f"VBX2,Import Friend,9833311112,male,1995-06-10,mumbai,3L-6L,Brand New Channel,VBX1,15/08/2026,{recent}\n"
           "VBX3,Import Orphan,9833311113,f,,Delhi,6L-10L,Website,VB99999,not-a-date,\n")
    files = {"file": ("cols.csv", io.BytesIO(csv.encode()), "text/csv")}
    d = client.post("/api/admin/import", params={"dry_run": "true"}, files=files, headers=admin).json()
    assert d["imported"] == 3 and d["skipped"] == 0
    reasons = {x["row"]: x["reason"] for x in d["details"]}
    assert "not imported" in reasons[4]                    # VB99999 cannot be linked
    assert "could not be read" in reasons[4]               # joined_on is nonsense
    assert "Brand New Channel" in reasons[3]
    r = client.post("/api/admin/import", files=files, headers=admin)
    assert r.status_code == 200, r.text
    db = SessionLocal()
    referrer = db.query(Member).filter_by(phone="9833311111").first()
    friend = db.query(Member).filter_by(phone="9833311112").first()
    orphan = db.query(Member).filter_by(phone="9833311113").first()
    # dates + normalisation
    assert referrer.dob == date(1984, 3, 1) and referrer.gender == "Female"
    assert referrer.income_range == "<5L" and referrer.created_at.date() == date(2025, 8, 1)
    assert friend.city == "Mumbai" and friend.income_range == "5-10L" and friend.gender == "Male"
    # referred_by -> referrer credited, unknown source created
    assert friend.referrer_id == referrer.id
    fr = db.query(Referral).filter_by(referred_member_id=friend.id).first()
    assert fr.referrer_id == referrer.id and fr.stage == "Lead"
    assert db.query(Source).filter_by(name="Brand New Channel").first() is not None
    assert orphan.referrer_id is None and orphan.dob is None and orphan.gender == "Female"
    # legacy completion -> cool-off + status screen shows where it came from
    comp = db.query(Completion).filter_by(member_id=friend.id, survey_id=None).first()
    assert comp is not None and comp.quality_check_passed is True
    mh = member_token(client, "9833311112")
    status = client.get("/api/me/status", headers=mh).json()
    assert status["stage"] == "Lead" and status["completions"][0]["survey"].startswith("Completed before joining")
    assert client.get("/api/me", headers=mh).json()["next_eligible_date"]  # 3-month cool-off active
    db.close()


# ---------- fraud: bursts, scan, review ----------

def test_device_burst_flags_and_review(client, admin):
    dev = {"X-Device-Id": "pytest-device-burst"}
    for i, phone in enumerate(["9810000021", "9810000022", "9810000023"]):
        r = signup_member(client, phone, name=f"Burst Person {i}", headers=dev)
        assert r.status_code == 200, r.text
    flags = client.get("/api/admin/fraud-flags?status=open", headers=admin).json()
    burst = [f for f in flags if f["flag_type"] == "burst_signups" and f["phone"] in
             ("9810000021", "9810000022", "9810000023")]
    assert len(burst) >= 3
    # scan is idempotent while flags stay open
    assert client.post("/api/admin/fraud/scan", headers=admin).json()["flags_created"] == 0
    # clear all three -> member unflagged
    for f in burst:
        r = client.post(f"/api/admin/fraud-flags/{f['id']}/review", json={"status": "Cleared"}, headers=admin)
        assert r.status_code == 200
    flagged = client.get("/api/admin/members?status=flagged", headers=admin).json()
    assert not any(x["phone"] in ("9810000021", "9810000022", "9810000023") for x in flagged)
    # reviewed flags stay visible under their status (never deleted)
    cleared = client.get("/api/admin/fraud-flags?status=Cleared", headers=admin).json()
    assert any(f["phone"] == "9810000021" for f in cleared)


def test_ip_burst_via_forwarded_header(client, admin):
    hdr = {"X-Forwarded-For": "203.0.113.77"}
    for i, phone in enumerate(["9810000031", "9810000032", "9810000033"]):
        r = signup_member(client, phone, name=f"IP Burst {i}", headers=hdr)
        assert r.status_code == 200, r.text
    flags = client.get("/api/admin/fraud-flags?status=open", headers=admin).json()
    assert sum(1 for f in flags if f["flag_type"] == "burst_signups" and f["phone"].startswith("981000003")) == 3


def test_referral_ring_scan(client, admin):
    from app.models import Member, SessionLocal
    signup_member(client, "9810000041", name="Ring A", dob="1990-01-01")
    signup_member(client, "9810000042", name="Ring B", dob="1990-01-01")
    db = SessionLocal()
    a = db.query(Member).filter_by(phone="9810000041").first()
    b = db.query(Member).filter_by(phone="9810000042").first()
    a.referrer_id, b.referrer_id = b.id, a.id  # A refers B and B refers A
    db.commit(); db.close()
    r = client.post("/api/admin/fraud/scan", headers=admin)
    assert r.status_code == 200 and r.json()["flags_created"] >= 2
    flags = client.get("/api/admin/fraud-flags?status=open", headers=admin).json()
    rings = [f for f in flags if f["flag_type"] == "referral_ring"]
    assert {f["phone"] for f in rings} >= {"9810000041", "9810000042"}
    # second scan adds nothing (idempotent)
    assert client.post("/api/admin/fraud/scan", headers=admin).json()["flags_created"] == 0
    # confirming A's only flag unflags A; B stays flagged until reviewed
    f = next(f for f in rings if f["phone"] == "9810000041")
    r = client.post(f"/api/admin/fraud-flags/{f['id']}/review",
                    json={"status": "Confirmed", "note": "checked with ops"}, headers=admin)
    assert r.status_code == 200 and r.json()["member_flagged"] is False
    flagged = client.get("/api/admin/members?status=flagged", headers=admin).json()
    assert any(x["phone"] == "9810000042" for x in flagged)


# ---------- SPA fallback ----------

def test_spa_deep_links_and_api_404(client):
    r = client.get("/admin/members")
    assert r.status_code == 200 and '<div id="root">' in r.text
    r = client.get("/home")
    assert r.status_code == 200 and '<div id="root">' in r.text
    assert client.get("/api/does-not-exist").status_code == 404
