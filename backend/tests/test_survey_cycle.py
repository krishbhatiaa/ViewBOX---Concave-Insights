from datetime import datetime, timedelta

from conftest import make_survey


def deadline_in(days):
    return (datetime.utcnow() + timedelta(days=days)).isoformat()


def test_survey_post_rejects_past_and_long_deadlines(client, admin):
    payload = {"title": "Cycle Validation Survey", "amount": 100, "rules": []}

    past = client.post("/api/admin/surveys", headers=admin,
                       json={**payload, "deadline": deadline_in(-1)})
    assert past.status_code == 422, past.text
    assert "future" in past.text

    long = client.post("/api/admin/surveys", headers=admin,
                       json={**payload, "deadline": deadline_in(16)})
    assert long.status_code == 422, long.text
    assert "15 days of launch" in long.text

    boundary = client.post("/api/admin/surveys", headers=admin,
                           json={**payload, "deadline": deadline_in(15)})
    assert boundary.status_code == 201, boundary.text


def test_survey_patch_validates_deadline_from_created_at(client, admin):
    sid = make_survey(client, admin, "Patch Cycle Survey", [], deadline=deadline_in(10))

    long = client.patch(f"/api/admin/surveys/{sid}", headers=admin,
                        json={"deadline": deadline_in(20)})
    assert long.status_code == 422, long.text
    assert "15 days of launch" in long.text

    allowed = client.patch(f"/api/admin/surveys/{sid}", headers=admin,
                           json={"deadline": deadline_in(12)})
    assert allowed.status_code == 200, allowed.text

    status_only = client.patch(f"/api/admin/surveys/{sid}", headers=admin,
                               json={"status": "live"})
    assert status_only.status_code == 200, status_only.text
