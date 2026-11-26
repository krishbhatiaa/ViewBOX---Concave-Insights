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


def test_error_boundary_and_complete_stage_explanations():
    boundary = _read("components/ErrorBoundary.jsx")
    assert "class ErrorBoundary extends Component" in boundary
    assert "componentDidCatch" in boundary
    assert "Something went wrong." in boundary and "Reload" in boundary
    app = _read("App.jsx")
    assert "<ErrorBoundary>" in app and "<ToastProvider>" in app

    map_body = _read("lib/stages.js").split("STAGE_EXPLANATION = {", 1)[1].split("}", 1)[0]
    for stage in ("Waitlisted", "Pending", "Approved", "Rejected"):
        assert f"{stage}: " in map_body
    referrals = _read("pages/member/ReferralsPage.jsx")
    assert "STAGE_EXPLANATION[r.stage] && <p>" in referrals
