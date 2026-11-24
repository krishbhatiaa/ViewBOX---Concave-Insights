import io

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
