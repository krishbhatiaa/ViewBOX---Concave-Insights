def test_admin_list_endpoints_return_404_for_dangling_references(client, admin):
    from sqlalchemy import create_engine, text

    from app.models import AdminOverride, MetaLead, Payout, SessionLocal, engine

    legacy = create_engine(str(engine.url))  # no PRAGMA listener: rows written before FK enforcement
    with legacy.begin() as conn:
        payout_id = conn.execute(text(
            "INSERT INTO payouts (member_id, amount, status) VALUES (999999, 10, 'Pending')"
        )).lastrowid
        lead_id = conn.execute(text(
            "INSERT INTO meta_leads (lead_id, member_id) VALUES ('dangling-lead-1', 999999)"
        )).lastrowid
        override_id = conn.execute(text(
            "INSERT INTO admin_overrides (member_id, survey_id, reason) VALUES (999999, 999999, 'dangling reference')"
        )).lastrowid
    created = ((Payout, payout_id), (MetaLead, lead_id), (AdminOverride, override_id))
    try:
        for path in ("/api/admin/payouts", "/api/admin/meta-leads", "/api/admin/overrides"):
            r = client.get(path, headers=admin)
            assert r.status_code == 404, (path, r.text)
            assert "not found" in r.json()["detail"]
    finally:
        db = SessionLocal()
        try:
            for model, pk in created:
                row = db.get(model, pk)
                if row:
                    db.delete(row)
            db.commit()
        finally:
            db.close()


def test_meta_webhook_creates_one_meta_ads_source_by_slug(client):
    from app.models import Member, SessionLocal, Source

    db = SessionLocal()
    existing = db.query(Source).filter_by(unique_slug="meta-ads").first()
    if existing:
        db.delete(existing)
        db.commit()
    db.close()

    phones = ("9940000401", "9940000402")
    for i, phone in enumerate(phones, 1):
        r = client.post("/api/meta/lead", json={
            "lead_id": f"slug-lead-{i}",
            "fields": {"name": f"Slug Person {i}", "phone": phone, "city": "Pune"},
        })
        assert r.status_code == 200, r.text
        assert r.json()["source"] == "Meta Ads"

    db = SessionLocal()
    try:
        sources = db.query(Source).filter_by(unique_slug="meta-ads").all()
        assert len(sources) == 1
        source = sources[0]
        assert source.name == "Meta Ads"
        for phone in phones:
            m = db.query(Member).filter_by(phone=phone).first()
            assert m and m.source_id == source.id
    finally:
        db.close()
