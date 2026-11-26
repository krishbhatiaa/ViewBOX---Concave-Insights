import base64
import json
import time

from app import security as sec


def signed(payload):
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"{p}.{sec._sig(p)}"


def test_make_token_declares_hs256():
    token = sec.make_token(1, "member")
    p = token.rsplit(".", 1)[0]
    payload = json.loads(base64.urlsafe_b64decode(p))
    assert payload["alg"] == "HS256"
    assert sec.read_token(token)["sub"] == 1


def test_forged_alg_none_variants_are_rejected(client):
    for alg in ("none", "None", "noNE"):
        token = signed({"alg": alg, "sub": 1, "role": "admin", "exp": time.time() + 600})
        assert sec.read_token(token) is None
        r = client.get("/api/surveys", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_expired_token_is_rejected(client):
    token = signed({"alg": "HS256", "sub": 1, "role": "member", "exp": time.time() - 60})
    assert sec.read_token(token) is None
    r = client.get("/api/surveys", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_unknown_role_and_missing_claims_are_rejected(client):
    for payload in ({"alg": "HS256", "sub": 1, "role": "superadmin", "exp": time.time() + 600},
                    {"alg": "HS256", "role": "member", "exp": time.time() + 600},
                    {"alg": "HS256", "sub": 1, "exp": time.time() + 600}):
        token = signed(payload)
        assert sec.read_token(token) is None
        r = client.get("/api/surveys", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
