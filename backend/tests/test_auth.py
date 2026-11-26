from conftest import signup_member


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
