import hashlib
import hmac
import json
from datetime import datetime, timedelta
from io import BytesIO

from openpyxl import load_workbook

from app.models import GoogleFormLead, Member, Referral, SessionLocal, Source, Survey
from app.services import google_forms


def _create_survey(client, admin, title):
    r = client.post("/api/admin/surveys", headers=admin, json={
        "title": title, "description": "collected through Google Forms",
        "deadline": (datetime.utcnow() + timedelta(days=10)).isoformat(),
        "quota": 20, "amount": 150,
        "rules": [{"rule_type": "city", "value": "Mumbai,Pune", "strict_or_flexible": "flexible"}],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _form_for(client, admin, sid):
    return next(s for s in client.get("/api/admin/surveys", headers=admin).json() if s["id"] == sid)


class FakeWorksheet:
    def __init__(self, records):
        self.records = records

    def get_all_records(self):
        return self.records


class FakeSpreadsheet:
    def __init__(self, records):
        self.records = records

    def worksheet(self, name):
        return FakeWorksheet(self.records)

    @property
    def sheet1(self):
        return FakeWorksheet(self.records)


def test_survey_creation_makes_a_google_form_link(client, admin):
    sid = _create_survey(client, admin, "Google Form Survey One")
    created = client.post("/api/admin/surveys", headers=admin, json={
        "title": "Google Form Survey Link", "description": "second form",
        "rules": [],
    })
    assert created.status_code == 201, created.text
    form = created.json()["google_form"]
    assert form["mode"] == "mock" and form["url"].startswith("https://docs.google.com/forms/")
    assert form["questions"] >= 2

    row = _form_for(client, admin, created.json()["id"])
    assert row["google_form_id"] == form["form_id"]
    assert row["google_form_url"] == form["url"]
    db = SessionLocal()
    try:
        saved = db.get(Survey, sid)
        assert saved.google_form_id and saved.google_form_url
    finally:
        db.close()


def test_form_response_becomes_google_form_lead_in_dashboard_and_xlsx(client, admin):
    sid = _create_survey(client, admin, "Google Form Survey Two")
    form = _form_for(client, admin, sid)
    payload = {"response_id": "gf-response-1001", "form_id": form["google_form_id"],
               "fields": {"Full name": "Google Form Person", "Phone number": "+91 98600 10001",
                          "City": "Pune", "Email Address": "form.person@example.com"}}
    r = client.post("/api/google-forms/lead", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "created" and data["source"] == "Google Form"

    db = SessionLocal()
    try:
        lead = db.query(GoogleFormLead).filter_by(response_id="gf-response-1001").one()
        member = db.get(Member, lead.member_id)
        assert lead.status == "Lead" and lead.survey_id == sid
        assert member.name == "Google Form Person" and member.phone == "9860010001"
        assert member.source.name == "Google Form"
        assert db.query(Referral).filter_by(referred_member_id=member.id).one().stage == "Lead"
    finally:
        db.close()

    listed = client.get("/api/admin/google-form-leads", headers=admin).json()
    assert any(x["response_id"] == "gf-response-1001" and x["source"] == "Google Form" for x in listed)
    grid = client.get("/api/admin/members", params={"q": "Google Form Person"}, headers=admin).json()
    assert grid and grid[0]["source"] == "Google Form"

    xlsx = client.get("/api/admin/google-form-leads/export", headers=admin)
    assert xlsx.status_code == 200 and "google_form_leads.xlsx" in xlsx.headers["content-disposition"]
    ws = load_workbook(BytesIO(xlsx.content)).active
    values = list(ws.iter_rows(values_only=True))
    assert values[0][0] == "id" and "response_id" in values[0]
    assert any("gf-response-1001" in row for row in values)

    again = client.post("/api/google-forms/lead", json=payload)
    assert again.status_code == 200 and again.json()["status"] == "duplicate"
    db = SessionLocal()
    try:
        assert db.query(GoogleFormLead).filter_by(response_id="gf-response-1001").count() == 1
    finally:
        db.close()


def test_google_forms_sheet_sync_and_webhook_signature(client, admin, monkeypatch):
    sid = _create_survey(client, admin, "Google Form Sheet Sync Survey")
    form = _form_for(client, admin, sid)
    records = [{"Timestamp": "2026-11-26 10:00:00", "Full name": "Sheet Sync Person",
                "Phone number": "9860010002", "City": "Mumbai", "form_id": form["google_form_id"]}]
    monkeypatch.setattr(google_forms, "_open_responses_sheet", lambda: FakeSpreadsheet(records))
    r = client.post("/api/admin/google-forms/sync", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["synced"] == 1
    assert any(x["name"] == "Sheet Sync Person" for x in
               client.get("/api/admin/google-form-leads", headers=admin).json())

    monkeypatch.setenv("GOOGLE_FORMS_WEBHOOK_SECRET", "secret-for-test")
    payload = {"response_id": "gf-response-1003", "survey_id": sid,
               "fields": {"name": "Signed Person", "phone": "9860010003"}}
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"secret-for-test", body, hashlib.sha256).hexdigest()
    assert client.post("/api/google-forms/lead", content=body).status_code == 403
    signed = client.post("/api/google-forms/lead", content=body,
                         headers={"X-Google-Forms-Signature-256": signature, "Content-Type": "application/json"})
    assert signed.status_code == 200, signed.text
    assert signed.json()["status"] == "created"


def test_google_forms_sync_falls_back_to_local_responses(client, admin, monkeypatch, tmp_path):
    sid = _create_survey(client, admin, "Local Fallback Survey")
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_FORM_RESPONSES_SHEET_ID", raising=False)
    monkeypatch.delenv("SPREADSHEET_ID", raising=False)
    csv_path = tmp_path / "responses.csv"
    csv_path.write_text(
        "response_id,survey_id,Full name,Phone number,City\n"
        f"gf-local-1004,{sid},Local Fallback Person,9860010011,Pune\n",
        encoding="utf-8")
    monkeypatch.setenv("GOOGLE_FORM_RESPONSES_LOCAL_PATH", str(csv_path))

    r = client.post("/api/admin/google-forms/sync", headers=admin)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mode"] == "local" and data["synced"] == 1 and data["duplicates"] == 0

    db = SessionLocal()
    try:
        lead = db.query(GoogleFormLead).filter_by(response_id="gf-local-1004").one()
        assert lead.survey_id == sid and lead.status == "Lead"
    finally:
        db.close()

    again = client.post("/api/admin/google-forms/sync", headers=admin)
    assert again.status_code == 200, again.text
    assert again.json()["synced"] == 0 and again.json()["duplicates"] == 1

    monkeypatch.delenv("GOOGLE_FORM_RESPONSES_LOCAL_PATH")
    bundled = google_forms._read_local_responses(google_forms._local_responses_path())
    assert len(bundled) >= 2 and bundled[0]["response_id"]


def test_google_forms_sync_surfaces_real_sheet_errors(client, admin, monkeypatch):
    def boom():
        raise google_forms.FormsError("Google Sheets refused the request: permission denied")

    monkeypatch.setattr(google_forms, "_open_responses_sheet", boom)
    r = client.post("/api/admin/google-forms/sync", headers=admin)
    assert r.status_code == 502
    assert "permission denied" in r.json()["detail"]


class FakeResponse:
    def raise_for_status(self):
        return None


class FakeShareClient:
    def __init__(self):
        self.calls = []

    def post(self, url, headers=None, params=None, json=None):
        self.calls.append((url, params, json))
        return FakeResponse()


def test_google_forms_sharing_uses_configured_emails(monkeypatch):
    monkeypatch.setenv("GOOGLE_FORM_SHARE_WITH", "one@example.com, two@example.com")
    client = FakeShareClient()
    google_forms._share_form(client, {"Authorization": "Bearer token"}, "form-123")
    assert len(client.calls) == 2
    assert client.calls[0][2] == {"type": "user", "role": "reader", "emailAddress": "one@example.com"}
    assert client.calls[1][2]["emailAddress"] == "two@example.com"
    assert "https://www.googleapis.com/auth/drive.file" in google_forms.FORM_SCOPES
