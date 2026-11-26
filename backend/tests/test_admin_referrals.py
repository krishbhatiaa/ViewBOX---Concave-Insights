from datetime import datetime, timedelta

from conftest import member_token, signup_member


def make_referral(client, referrer_phone, friend_phone, friend_name, ref_token):
    r = signup_member(client, friend_phone, name=friend_name, ref=ref_token)
    assert r.status_code == 200, r.text


def ref_token_for(client, phone):
    link = client.get("/api/me", headers=member_token(client, phone)).json()["referral_link"]
    return link.split("ref=")[1].split("&")[0]


def list_referrals(client, admin, **params):
    return client.get("/api/admin/referrals", params=params, headers=admin)


def test_admin_referrals_requires_auth(client):
    assert client.get("/api/admin/referrals").status_code == 401


def test_admin_referrals_list_filters_and_validation(client, admin):
    phone = "9822000001"
    signup_member(client, phone, name="Queue Referrer")
    token = ref_token_for(client, phone)
    make_referral(client, phone, "9822000002", "Queue Friend One", token)
    make_referral(client, phone, "9822000003", "Queue Friend Two", token)

    rows = list_referrals(client, admin).json()
    friends = {r["member"]: r for r in rows if r["member"] in {"Queue Friend One", "Queue Friend Two"}}
    assert len(friends) == 2
    assert friends["Queue Friend One"]["referrer"] == "Queue Referrer"
    assert friends["Queue Friend One"]["stage"] == "Lead"
    assert friends["Queue Friend One"]["updated_at"]

    lead_rows = list_referrals(client, admin, stage="Lead").json()
    assert all(r["stage"] == "Lead" for r in lead_rows)
    search = list_referrals(client, admin, q="Queue Friend One").json()
    assert [r["member"] for r in search] == ["Queue Friend One"]
    page = list_referrals(client, admin, limit=1, offset=1).json()
    assert len(page) == 1

    assert list_referrals(client, admin, stage="Nope").status_code == 422
    assert list_referrals(client, admin, limit=0).status_code == 422
    assert list_referrals(client, admin, q="x" * 101).status_code == 422


def test_admin_referrals_full_stage_flow(client, admin):
    phone = "9822000010"
    signup_member(client, phone, name="Flow Referrer")
    token = ref_token_for(client, phone)
    make_referral(client, phone, "9822000011", "Flow Friend", token)
    row = next(r for r in list_referrals(client, admin, q="Flow Friend").json()
               if r["member"] == "Flow Friend")
    rid = row["id"]
    assert row["stage"] == "Lead"

    survey = client.post("/api/admin/surveys", json={
        "title": "Flow Completion Survey",
        "description": "stage flow test",
        "deadline": (datetime.utcnow() + timedelta(days=10)).isoformat(),
        "amount": 250,
        "interests": [],
        "rules": [],
    }, headers=admin)
    assert survey.status_code == 201, survey.text

    fit = client.post(f"/api/admin/referrals/{rid}/stage", json={"stage": "Fit"}, headers=admin)
    assert fit.status_code == 200, fit.text
    assert next(r for r in list_referrals(client, admin, q="Flow Friend").json()
                if r["id"] == rid)["stage"] == "Fit"

    completed = client.post(f"/api/admin/referrals/{rid}/stage", json={
        "stage": "Completed", "survey_id": survey.json()["id"], "quality_check_passed": True,
    }, headers=admin)
    assert completed.status_code == 200, completed.text
    finished = next(r for r in list_referrals(client, admin, q="Flow Friend").json() if r["id"] == rid)
    assert finished["stage"] == "Completed"

    referrer_view = client.get("/api/me/referrals", headers=member_token(client, phone)).json()
    assert any(r["friend"] == "Flow Friend" and r["stage"] == "Completed" for r in referrer_view)


def test_admin_referrals_failed_reason_reaches_member(client, admin):
    phone = "9822000020"
    signup_member(client, phone, name="Reason Referrer")
    token = ref_token_for(client, phone)
    make_referral(client, phone, "9822000021", "Reason Friend", token)
    rid = next(r for r in list_referrals(client, admin, q="Reason Friend").json()
               if r["member"] == "Reason Friend")["id"]
    r = client.post(f"/api/admin/referrals/{rid}/stage", json={
        "stage": "Failed", "failure_reason": "Did not match profile criteria",
    }, headers=admin)
    assert r.status_code == 200, r.text
    assert next(x for x in list_referrals(client, admin, q="Reason Friend").json()
                if x["id"] == rid)["failure_reason"] == "Did not match profile criteria"
    referrer_view = client.get("/api/me/referrals", headers=member_token(client, phone)).json()
    assert any(x["friend"] == "Reason Friend" and x["failure_reason"] == "Did not match profile criteria"
               for x in referrer_view)
