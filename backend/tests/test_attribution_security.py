from app import security as sec
from conftest import signup_member


def test_sanitize_param_strips_crlf_semicolon_nul_and_caps_length():
    raw = "a\r\nb;c\x00d" * 20
    assert sec.sanitize_param(raw) == "abcd" * 16


def test_sign_link_signs_sanitized_value_and_rejects_forgery():
    token = sec.sign_link("src", "abc\r\n;x")
    assert token.startswith("abcx.")
    assert sec.verify_link("src", token) == "abcx"
    assert sec.verify_link("src", "abcx.forged") is None


def test_links_sign_endpoint_returns_signed_sanitized_values(client):
    r = client.get("/api/links/sign", params={"src": "wa\r\n;group", "ref": "12\x0034"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert sec.verify_link("src", data["src"]) == "wagroup"
    assert sec.verify_link("ref", data["ref"]) == "1234"


def test_signup_ignores_forged_source_with_note(client):
    r = signup_member(client, "9870000001", src="whatsapp.forged")
    assert r.status_code == 200, r.text
    assert any("Source link could not be verified" in n for n in r.json()["notes"])
