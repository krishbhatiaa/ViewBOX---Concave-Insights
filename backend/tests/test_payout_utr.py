from conftest import make_survey, member_token, signup_member


def test_payout_utrs_are_generated_and_shown_only_to_their_owner(client, admin):
    sid = make_survey(client, admin, "UTR Visible Survey", [
        {"rule_type": "age", "value": "18-99", "strict_or_flexible": "strict"},
    ], amount=310)
    assert signup_member(client, "9850000001", name="UTR Referrer", dob="1990-01-01").status_code == 200
    assert signup_member(client, "9850000002", name="UTR Friend", dob="1992-01-01",
                         referrer_phone="9850000001").status_code == 200
    rows = client.get("/api/admin/members", params={"q": "UTR Friend"}, headers=admin).json()
    rid = rows[0]["referral_id"]
    r = client.post(f"/api/admin/referrals/{rid}/stage",
                    json={"stage": "Completed", "survey_id": sid, "quality_check_passed": True},
                    headers=admin)
    assert r.status_code == 200, r.text

    payouts = client.get("/api/admin/payouts", headers=admin).json()
    friend_payout = next(p for p in payouts if p["member"] == "UTR Friend")
    referrer_payout = next(p for p in payouts if p["member"] == "UTR Referrer")
    assert friend_payout["utr"].startswith("UTR-") and referrer_payout["utr"].startswith("UTR-")
    assert friend_payout["utr"] != referrer_payout["utr"]

    friend_status = client.get("/api/me/status", headers=member_token(client, "9850000002")).json()
    assert [p["utr"] for p in friend_status["payouts"]] == [friend_payout["utr"]]
    referrer_status = client.get("/api/me/status", headers=member_token(client, "9850000001")).json()
    assert [p["utr"] for p in referrer_status["payouts"]] == [referrer_payout["utr"]]
    referrals = client.get("/api/me/referrals", headers=member_token(client, "9850000001")).json()
    assert referrals[0]["bonus"]["utr"] == referrer_payout["utr"]
