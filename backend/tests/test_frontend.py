import re
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


def test_refresh_errors_surface_as_inline_banners():
    banner = _read("pages/RefreshBanner.jsx")
    assert "Couldn't refresh — showing cached data." in banner
    assert "Retry" in banner and "setDismissed" in banner

    pages = [
        "pages/admin/GridPage.jsx",
        "pages/admin/SurveysPage.jsx",
        "pages/admin/SourcesPage.jsx",
        "pages/admin/StatsPage.jsx",
        "pages/admin/PayoutsPage.jsx",
        "pages/admin/FraudPage.jsx",
        "pages/admin/MetaLeadsPage.jsx",
        "pages/member/HomePage.jsx",
        "pages/member/ReferralsPage.jsx",
    ]
    for page in pages:
        text = _read(page)
        assert "RefreshBanner" in text, page
        assert "ErrorState" in text, page
        assert re.search(r"error && !(rows|flags|leads|data)\s+\?", text) is None, page


def test_grid_filter_fetch_errors_are_not_swallowed():
    grid = _read("pages/admin/GridPage.jsx")
    assert ".catch(() => {})" not in grid
    assert "filterError" in grid and "setFilterRetry" in grid
    assert "Failed to load filters" in grid


def test_money_renders_two_decimal_places():
    assert "export function money(value)" in _read("api.js")
    for page in ("pages/admin/PayoutsPage.jsx", "pages/admin/SurveysPage.jsx",
                 "pages/member/HomePage.jsx", "pages/member/ReferralsPage.jsx"):
        assert "money(" in _read(page), page


def test_layout_redirects_run_in_effect_not_during_render():
    cases = (("pages/member/MemberLayout.jsx", '"/login"'), ("pages/admin/AdminLayout.jsx", '"/admin"'))
    for page, route in cases:
        text = _read(page)
        assert "useEffect(() => {" in text
        assert f"if (!token) navigate({route}, {{ replace: true }});" in text
        assert "if (!token) return null;" in text
        assert "if (!tokens.get(" not in text, page


def test_dead_code_and_unused_theme_tokens_removed():
    stages = _read("lib/stages.js")
    assert "STAGE_TONE" not in stages and "toneForStage" not in stages
    assert "clearAll" not in _read("api.js")

    home = _read("pages/member/HomePage.jsx")
    assert "if (!data) return null;" not in home
    assert "error && data ?" not in home
    assert 'stage === "Approved" || stage === "Approved by ops"' not in _read("components/ui.jsx")

    css = _read("index.css")
    for token in ("--color-accent", "--color-ink:", "--color-surface:", "--radius-card", "--spacing-card"):
        assert token not in css


def test_theme_toggle_is_persisted_and_mounted_in_both_layouts():
    toggle = _read("components/ThemeToggle.jsx")
    assert 'CHOICES = ["system", "light", "dark"]' in toggle
    assert 'localStorage.getItem("vb_theme")' in toggle
    assert 'localStorage.setItem("vb_theme"' in toggle
    assert "document.documentElement.dataset.theme" in toggle
    assert "applyTheme" in _read("App.jsx")
    for layout in ("pages/member/MemberLayout.jsx", "pages/admin/AdminLayout.jsx"):
        assert "ThemeToggle" in _read(layout), layout
    css = _read("index.css")
    assert '@custom-variant dark' in css
    assert '[data-theme="dark"]' in css


def test_sheets_status_card_has_sync_button_and_toasts():
    api = _read("api.js")
    assert '"/api/admin/sheets/status"' in api
    assert '"/api/admin/sheets/push"' in api

    stats = _read("pages/admin/StatsPage.jsx")
    assert "sheetsStatus()" in stats and "sheetsPush(filters)" in stats
    assert "last synced" in stats and "rows" in stats
    assert "✅" in stats and "❌" in stats
    assert "Sync now" in stats
    assert "toast(`Synced" in stats and "toast(`Sync failed" in stats
    assert 'sessionStorage.getItem("vb_grid_filters")' in stats
    assert 'sessionStorage.setItem("vb_grid_filters"' in _read("pages/admin/GridPage.jsx")


def test_meta_simulator_page_is_routed_and_linked():
    page = _read("pages/MetaSimulator.jsx")
    for label in ("Valid lead", "Duplicate lead", "Missing phone", "Send webhook"):
        assert label in page
    assert 'fetch("/api/meta/lead"' in page
    assert "Status: ${result.status}" in page
    assert "Graph API" in page
    assert 'path="/admin/meta-simulator"' in _read("App.jsx")
    assert 'to: "/admin/meta-simulator"' in _read("pages/admin/AdminLayout.jsx")


def test_referrals_page_has_qr_download():
    page = _read("pages/member/ReferralsPage.jsx")
    assert "Download QR" in page
    assert '"/api/me/referral-qr"' in page
    assert "downloadBlob(blob" in page
    assert "raw: true" in page
