def test_admin_list_endpoints_return_404_for_dangling_references(client, admin):
    from app.models import AdminOverride, MetaLead, Payout, SessionLocal

    db = SessionLocal()
    payout = Payout(member_id=999999, amount=10, status="Pending")
    lead = MetaLead(lead_id="dangling-lead-1", member_id=999999)
    override = AdminOverride(member_id=999999, survey_id=999999, reason="dangling reference")
    db.add_all([payout, lead, override])
    db.commit()
    created = ((Payout, payout.id), (MetaLead, lead.id), (AdminOverride, override.id))
    db.close()
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
