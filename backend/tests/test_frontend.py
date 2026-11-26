from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _read(rel):
    return (SRC / rel).read_text(encoding="utf-8")


def test_401_on_authenticated_request_shows_toast_and_redirects():
    api = _read("api.js")
    toast = _read("components/Toast.jsx")
    assert "if (res.status === 401 && role)" in api
    assert 'tokens.set(role === "member", null)' in api
    assert 'sessionStorage.setItem("vb_session_expired", "1")' in api
    assert 'role === "member" ? "/login" : "/admin"' in api
    assert "window.location.assign(target)" in api
    assert "notifySessionExpired" in api
    assert "notifySessionExpired" in toast
    assert "Session expired, please log in again" in toast
    assert "sessionStorage.getItem(SESSION_EXPIRED_KEY)" in toast

    assert "role:" not in _read("pages/member/PhonePage.jsx")
    assert "role:" not in _read("pages/admin/AdminLoginPage.jsx")
