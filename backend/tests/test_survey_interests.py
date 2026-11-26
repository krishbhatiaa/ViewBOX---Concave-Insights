from datetime import datetime, timedelta

from conftest import member_token, signup_member


def create_survey(client, admin, title, interests, rules=None):
    deadline = (datetime.utcnow() + timedelta(days=10)).isoformat()
    r = client.post("/api/admin/surveys", json={
        "title": title,
        "description": "interest test survey",
        "deadline": deadline,
        "quota": None,
        "amount": 100,
        "interests": interests,
        "rules": rules or [],
    }, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def surveys_for(client, phone):
    return client.get("/api/surveys", headers=member_token(client, phone)).json()


def by_id(rows, sid):
    return next(row for row in rows if row["id"] == sid)


def test_survey_interests_match_case_insensitively(client, admin):
    sid = create_survey(client, admin, "Food and Tech Survey", [" FOOD ", "Tech"])
    signup_member(client, "9821000001", name="Interest Match", interests=["FOOD", "tech"])
    row = by_id(surveys_for(client, "9821000001"), sid)
    assert row["matches_interests"] is True
    assert set(row["matched_interests"]) == {"food", "tech"}
    assert row["result"] in {"Approved", "Waitlisted", "Rejected"}


def test_survey_interests_no_match(client, admin):
    sid = create_survey(client, admin, "Travel Survey", ["travel"])
    signup_member(client, "9821000002", name="Interest No Match", interests=["food"])
    row = by_id(surveys_for(client, "9821000002"), sid)
    assert row["matches_interests"] is False
    assert row["matched_interests"] == []


def test_survey_without_interests_never_matches(client, admin):
    sid = create_survey(client, admin, "Open Survey", [])
    signup_member(client, "9821000003", name="Interest Empty Survey", interests=["food"])
    row = by_id(surveys_for(client, "9821000003"), sid)
    assert row["matches_interests"] is False
    assert row["matched_interests"] == []


def test_matching_surveys_are_sorted_first(client, admin):
    no_match = create_survey(client, admin, "First Non Match Survey", ["travel"])
    match = create_survey(client, admin, "Second Match Survey", ["food"])
    signup_member(client, "9821000004", name="Interest Order", interests=["food"])
    rows = surveys_for(client, "9821000004")
    assert next(i for i, row in enumerate(rows) if row["id"] == match) < next(
        i for i, row in enumerate(rows) if row["id"] == no_match
    )


def test_patch_survey_interests_changes_matching(client, admin):
    sid = create_survey(client, admin, "Patch Interest Survey", ["food"])
    signup_member(client, "9821000005", name="Interest Patch", interests=["food"])
    assert by_id(surveys_for(client, "9821000005"), sid)["matches_interests"] is True

    r = client.patch(f"/api/admin/surveys/{sid}", json={"interests": ["TRAVEL", "travel"]}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["interests"] == ["travel"]
    assert by_id(surveys_for(client, "9821000005"), sid)["matches_interests"] is False


def test_survey_interests_validation(client, admin):
    many = client.post("/api/admin/surveys", json={
        "title": "Too Many Interests", "interests": [f"tag{i}" for i in range(11)],
    }, headers=admin)
    assert many.status_code == 422
    assert "10" in many.text

    long_tag = client.post("/api/admin/surveys", json={
        "title": "Too Long Interest", "interests": ["x" * 41],
    }, headers=admin)
    assert long_tag.status_code == 422
    assert "40" in long_tag.text
