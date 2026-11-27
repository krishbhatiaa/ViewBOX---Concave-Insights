import os

EXPECTED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "content-security-policy": (
        "default-src 'self'; img-src 'self' data:; font-src 'self' data:; style-src 'self' 'unsafe-inline'"
    ),
}


def test_security_headers_present(client):
    r = client.get("/api/sources/public")
    assert r.status_code == 200, r.text
    for name, value in EXPECTED.items():
        assert r.headers.get(name) == value


def test_cors_allowlist_does_not_echo_disallowed_origin(client):
    allowed = os.getenv("FRONTEND_URL", "http://localhost:8000").strip()
    r = client.options("/api/sources/public", headers={
        "Origin": allowed, "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == allowed
    assert r.headers.get("access-control-allow-credentials") == "true"

    r = client.options("/api/sources/public", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"
    assert r.headers.get("access-control-allow-origin") != "*"
