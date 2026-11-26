from conftest import member_token, signup_member


def test_profile_complete_flag_for_new_member(client):
    signup_member(client, "9823000001", name="Complete Profile")
    me = client.get("/api/me", headers=member_token(client, "9823000001")).json()
    assert me["profile_complete"] is True


def test_incomplete_profile_can_be_completed_with_patch(client):
    phone = "9823000002"
    signup_member(client, phone, name="Incomplete Profile")

    from app.models import Member, SessionLocal
    db = SessionLocal()
    member = db.query(Member).filter_by(phone=phone).first()
    member.dob = None
    member.gender = None
    member.income_range = None
    member.interests = None
    db.commit()
    db.close()

    headers = member_token(client, phone)
    assert client.get("/api/me", headers=headers).json()["profile_complete"] is False

    r = client.patch("/api/me", headers=headers, json={
        "name": "Incomplete Profile",
        "dob": "1995-01-01",
        "gender": "Female",
        "city": "Mumbai",
        "income_range": "5-10L",
        "interests": ["food", "tech"],
    })
    assert r.status_code == 200, r.text
    me = client.get("/api/me", headers=headers).json()
    assert me["profile_complete"] is True
    assert me["interests"] == ["food", "tech"]


def test_patch_profile_validates_required_fields(client):
    phone = "9823000003"
    signup_member(client, phone, name="Patch Validation")
    headers = member_token(client, phone)
    r = client.patch("/api/me", headers=headers, json={"name": "X", "gender": "Unknown"})
    assert r.status_code == 422
