from app.services import sheets


class FakeWorksheet:
    def __init__(self, title="sheet1", records=None):
        self.title = title
        self.rows = []
        self._records = records or []

    def append(self, values):
        self.rows.append(values)

    def get_all_records(self):
        return self._records


class FakeSpreadsheet:
    def __init__(self, records=None):
        self.url = "https://docs.google.com/spreadsheets/d/fake"
        self.created = []
        self.sheet1 = FakeWorksheet("sheet1", records)

    def add_worksheet(self, title, rows, cols):
        ws = FakeWorksheet(title)
        self.created.append(ws)
        return ws

    def worksheet(self, name):
        return FakeWorksheet(name, self.sheet1.get_all_records())


def test_sheets_push_creates_worksheet_and_logs(client, admin, monkeypatch):
    fake = FakeSpreadsheet()
    monkeypatch.setattr(sheets, "_open_sheet", lambda: fake)

    r = client.post("/api/admin/sheets/push", json={"q": ""}, headers=admin)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["sheet"].startswith("Export_") and data["url"].endswith("/fake")
    ws = fake.created[0]
    assert ws.rows[0][0] == "id"

    status = client.get("/api/admin/sheets/status", headers=admin).json()
    assert status["last_push"] and status["status"] == "ok"


def test_sheets_pull_reuses_import_validation_and_logs(client, admin, monkeypatch):
    records = [{"phone": "9960000501", "name": "Sheet Person", "dob": "1995-01-01",
                "gender": "Female", "city": "Mumbai", "income": "5-10L", "source": "Instagram"}]
    fake = FakeSpreadsheet(records)
    monkeypatch.setattr(sheets, "_open_sheet", lambda: fake)

    r = client.post("/api/admin/sheets/pull", headers=admin)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 1 and data["imported"] == 1
    assert set(data) == {"total", "imported", "fixed", "skipped", "details"}

    status = client.get("/api/admin/sheets/status", headers=admin).json()
    assert status["last_pull"] and status["status"] == "ok" and status["row_count"] == 1


def test_sheets_api_errors_are_502_with_human_message(client, admin, monkeypatch):
    def boom():
        raise sheets.SheetSyncError("Google Sheets is not configured.")

    monkeypatch.setattr(sheets, "_open_sheet", boom)
    r = client.post("/api/admin/sheets/push", json={}, headers=admin)
    assert r.status_code == 502
    assert "not configured" in r.json()["detail"]
