from app.models import Member, Referral, SessionLocal
from conftest import member_token, signup_member


def test_signup_with_channel_stores_it_on_referral_and_source_stats(client, admin):
    assert signup_member(client, "9830000001", name="Channel Referrer").status_code == 200
    mh = member_token(client, "9830000001")
    link = client.get("/api/me", headers=mh).json()["referral_link"]
    assert link.endswith("&ch=direct")
    ref = link.split("ref=")[1].split("&")[0]

    r = signup_member(client, "9830000002", name="Channel Friend", ref=ref, ch="whatsapp")
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        row = db.query(Referral).join(Member, Member.id == Referral.referred_member_id) \
                .filter(Member.phone == "9830000002").first()
        assert row.channel == "whatsapp"
    finally:
        db.close()

    stats = client.get("/api/admin/source-stats", headers=admin).json()
    assert any(b["channel"] == "whatsapp" for source in stats for b in source["by_channel"])


def test_referral_qr_returns_png(client):
    assert signup_member(client, "9830000003", name="QR Referrer").status_code == 200
    mh = member_token(client, "9830000003")
    r = client.get("/api/me/referral-qr", params={"ch": "whatsapp"}, headers=mh)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png"
    assert r.content.startswith(b"\x89PNG\r\n\x1a\n")
