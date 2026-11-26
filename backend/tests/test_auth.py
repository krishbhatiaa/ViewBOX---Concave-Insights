from app import security as sec
from conftest import member_token, signup_member


def test_otp_success_on_fifth_attempt_clears_lockout(client):
    phone = "9910000101"
    assert signup_member(client, phone, name="Fifth Try Person").status_code == 200

    otp = client.post("/api/otp/request", json={"phone": phone}).json()["otp"]
    wrong = "000001" if otp != "000001" else "000002"
    for _ in range(4):
        r = client.post("/api/login", json={"phone": phone, "otp": wrong})
        assert r.status_code == 400, r.text

    r = client.post("/api/login", json={"phone": phone, "otp": otp})
    assert r.status_code == 200, r.text

    next_otp = client.post("/api/otp/request", json={"phone": phone}).json()["otp"]
    r = client.post("/api/login", json={"phone": phone, "otp": next_otp})
    assert r.status_code == 200, r.text


def test_member_facing_responses_never_contain_raw_phone(client):
    phones = ["9821111111", "9822222222", "9823333333"]
    for phone in phones[:2]:
        assert signup_member(client, phone, name=f"Masked {phone[-2:]}").status_code == 200
    headers = member_token(client, phones[1])
    member_id = client.get("/api/me", headers=headers).json()["id"]
    assert signup_member(client, phones[2], name="Masked Friend",
                         ref=sec.sign_link("ref", str(member_id))).status_code == 200

    bodies = {}
    for path in ("/api/me", "/api/me/referral-qr", "/api/surveys", "/api/me/status", "/api/me/referrals"):
        r = client.get(path, headers=headers)
        assert r.status_code == 200, (path, r.text)
        bodies[path] = r.content.decode("utf-8", errors="ignore")
        for phone in phones:
            assert phone not in bodies[path], path

    assert '"phone":"98XXXXXX22"' in bodies["/api/me"]
    assert '"phone":"98XXXXXX33"' in bodies["/api/me/referrals"]

