import os
import tempfile

# Must be set before any app module is imported (models.py reads it at import time).
TEST_DB = os.path.join(tempfile.gettempdir(), "viewbox_pytest.db")
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

import pytest
from fastapi.testclient import TestClient


def admin_headers(c):
    r = c.post("/api/admin/login", json={"email": "admin@viewbox.test", "password": "admin123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def signup_member(c, phone, name="Test Person", dob="1995-01-01", gender="Female",
                  city="Mumbai", income="5-10L", interests=None, headers=None, **extra):
    otp = c.post("/api/otp/request", json={"phone": phone}).json()["otp"]
    payload = {"phone": phone, "otp": otp, "name": name, "dob": dob, "gender": gender,
               "city": city, "income_range": income, "interests": interests if interests is not None else ["food"]}
    payload.update(extra)
    return c.post("/api/signup", json=payload, headers=headers or {})


def member_token(c, phone):
    otp = c.post("/api/otp/request", json={"phone": phone}).json()["otp"]
    r = c.post("/api/login", json={"phone": phone, "otp": otp})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def make_survey(c, headers, title, rules, amount=100, quota=None, deadline="2027-06-30T00:00:00"):
    r = c.post("/api/admin/surveys", json={"title": title, "description": "test survey",
                                           "deadline": deadline, "quota": quota, "amount": amount,
                                           "rules": rules}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture(scope="session")
def client():
    from app.main import app
    from app.models import AdminUser, SessionLocal, Source
    from app import security as sec
    db = SessionLocal()
    if not db.query(AdminUser).filter_by(email="admin@viewbox.test").first():
        db.add(AdminUser(email="admin@viewbox.test", password_hash=sec.hash_pw("admin123456")))
    # baseline sources (the demo seed provides these in the real app)
    for n, t in [("WhatsApp - Mumbai Group", "whatsapp"), ("Staff - Priya", "staff"),
                 ("Instagram", "instagram"), ("Facebook", "facebook"), ("Website", "website"),
                 ("Referral", "referral"), ("LinkedIn", "linkedin"), ("Meta Ads", "meta_ads")]:
        if not db.query(Source).filter_by(name=n).first():
            db.add(Source(name=n, type=t, unique_slug=n.lower().replace(" - ", "-").replace(" ", "-")))
    db.commit()
    db.close()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin(client):
    return admin_headers(client)
