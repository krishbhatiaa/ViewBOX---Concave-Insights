from app.models import Member, SessionLocal


def test_formula_injection_is_neutralized_on_import_and_export(client, admin):
    csv_text = ("phone,name,city,source,referred_by\n"
                "9870000021,=cmd|'/C calc'!A0,=1+1,=HYPERLINK(\"x\"),=2+2\n")
    r = client.post("/api/admin/import?dry_run=false", files={"file": ("formula.csv", csv_text, "text/csv")},
                    headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1

    db = SessionLocal()
    try:
        member = db.query(Member).filter_by(phone="9870000021").first()
        assert member is not None
        assert member.name == "'=cmd|'/C calc'!A0"
        assert member.city == "'=1+1"
        assert member.source.name == "'=HYPERLINK(\"x\")"
        assert member.referrer_id is None
    finally:
        db.close()

    exported = client.get("/api/admin/members/export?format=csv", headers=admin)
    assert exported.status_code == 200, exported.text
    assert "'=cmd|'/C calc'!A0" in exported.text
    assert "\n=cmd" not in exported.text
