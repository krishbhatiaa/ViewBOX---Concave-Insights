from app.models import SessionLocal, TouchEvent


def _touches():
    db = SessionLocal()
    try:
        return [{"id": t.id, "source_slug": t.source_slug, "ref_slug": t.ref_slug, "ip": t.ip,
                 "user_agent": t.user_agent, "member_id": t.member_id}
                for t in db.query(TouchEvent).order_by(TouchEvent.id.desc()).all()]
    finally:
        db.close()


def test_resolve_logs_src_touch_without_changing_response(client):
    before = len(_touches())
    r = client.get("/api/links/resolve", params={"src": "whatsapp-group"},
                   headers={"User-Agent": "pytest-agent"})
    assert r.status_code == 200, r.text
    assert r.json()["needs_fallback"] is True
    rows = _touches()
    assert len(rows) == before + 1
    assert rows[0]["source_slug"] == "whatsapp-group" and rows[0]["ref_slug"] is None
    assert rows[0]["user_agent"] == "pytest-agent" and rows[0]["member_id"] is None


def test_resolve_logs_ref_touch(client):
    before = len(_touches())
    assert client.get("/api/links/resolve", params={"ref": "ref-code"}).status_code == 200
    rows = _touches()
    assert len(rows) == before + 1
    assert rows[0]["source_slug"] is None and rows[0]["ref_slug"] == "ref-code"


def test_resolve_with_neither_param_still_logs_null_touch(client):
    before = len(_touches())
    assert client.get("/api/links/resolve").status_code == 200
    rows = _touches()
    assert len(rows) == before + 1
    assert rows[0]["source_slug"] is None and rows[0]["ref_slug"] is None


def test_admin_can_list_touches_newest_first(client, admin):
    assert client.get("/api/admin/touches").status_code in (401, 403)
    r = client.get("/api/admin/touches", headers=admin)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [x["id"] for x in rows] == sorted((x["id"] for x in rows), reverse=True)
    assert all({"source_slug", "ref_slug", "ip", "user_agent", "member_id", "created_at"} <= set(x) for x in rows)
    assert client.get("/api/admin/touches", params={"member_id": 987654}, headers=admin).json() == []
