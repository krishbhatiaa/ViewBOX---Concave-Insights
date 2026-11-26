import hashlib
import hmac
import json

SECRET = "meta-webhook-test-secret"


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def payload(lead_id: str, phone: str = "9811111111") -> bytes:
    return json.dumps({"lead_id": lead_id, "form_id": "form-1",
                       "fields": {"name": "Sec Three", "phone": phone}},
                      separators=(",", ":")).encode()


def test_valid_signature_passes(client, monkeypatch):
    monkeypatch.setenv("META_WEBHOOK_SECRET", SECRET)
    body = payload("sec3-valid")
    r = client.post("/api/meta/lead", content=body,
                    headers={"content-type": "application/json", "x-hub-signature-256": sign(body)})
    assert r.status_code == 200, r.text


def test_tampered_body_fails(client, monkeypatch):
    monkeypatch.setenv("META_WEBHOOK_SECRET", SECRET)
    body = payload("sec3-tampered")
    r = client.post("/api/meta/lead", content=body,
                    headers={"content-type": "application/json", "x-hub-signature-256": sign(payload("sec3-original"))})
    assert r.status_code == 403


def test_missing_signature_fails_when_secret_set(client, monkeypatch):
    monkeypatch.setenv("META_WEBHOOK_SECRET", SECRET)
    r = client.post("/api/meta/lead", content=payload("sec3-nosig"),
                    headers={"content-type": "application/json"})
    assert r.status_code == 403


def test_token_header_alone_is_not_enough(client, monkeypatch):
    monkeypatch.setenv("META_WEBHOOK_SECRET", SECRET)
    r = client.post("/api/meta/lead", content=payload("sec3-token"),
                    headers={"content-type": "application/json", "x-webhook-token": SECRET})
    assert r.status_code == 403


def test_unsigned_path_open_when_secret_unset(client, monkeypatch):
    monkeypatch.delenv("META_WEBHOOK_SECRET", raising=False)
    r = client.post("/api/meta/lead", content=payload("sec3-devmode"),
                    headers={"content-type": "application/json"})
    assert r.status_code == 200, r.text
