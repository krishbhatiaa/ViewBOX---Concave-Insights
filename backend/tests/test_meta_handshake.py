import json

from app.services import meta_graph


def wrapped_lead(lead_id):
    return {
        "object": "page",
        "entry": [{
            "changes": [{
                "field": "leadgen",
                "value": {"leadgen_id": lead_id, "form_id": "form-wrapped", "ad_id": "ad-wrapped"},
            }],
        }],
    }


def test_meta_verify_handshake(client, monkeypatch):
    monkeypatch.setenv("META_VERIFY_TOKEN", "verify-123")
    params = {"hub.mode": "subscribe", "hub.verify_token": "verify-123", "hub.challenge": "abc-999"}

    ok = client.get("/webhooks/meta", params=params)
    assert ok.status_code == 200
    assert ok.text == "abc-999"

    wrong = client.get("/webhooks/meta", params={**params, "hub.verify_token": "nope"})
    assert wrong.status_code == 403

    wrong_mode = client.get("/webhooks/meta", params={**params, "hub.mode": "unsubscribe"})
    assert wrong_mode.status_code == 403

    monkeypatch.delenv("META_VERIFY_TOKEN", raising=False)
    assert client.get("/webhooks/meta", params=params).status_code == 403


def test_wrapped_envelope_uses_mock_fetcher_by_default(client, monkeypatch):
    monkeypatch.delenv("META_PAGE_ACCESS_TOKEN", raising=False)
    payload = wrapped_lead("wrapped-1234567")

    r = client.post("/api/meta/lead", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "created"
    assert body["source"] == "Meta Ads"

    repeat = client.post("/api/meta/lead", json=payload)
    assert repeat.json()["status"] == "duplicate"

    empty = client.post("/api/meta/lead", json={"object": "page", "entry": [{"changes": []}]})
    assert empty.status_code == 422


def test_mock_fetcher_produces_flat_fields():
    fields = meta_graph.MockLeadFetcher().fetch("lead-987654321")
    assert len(fields["phone"]) == 10
    assert fields["name"].startswith("Graph Lead")
    assert fields["city"] == "Mumbai"


def test_graph_fetcher_reads_field_data(client, monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"field_data": [
                {"name": "full_name", "values": ["Asha Rao"]},
                {"name": "phone_number", "values": ["+919822233344"]},
            ]}).encode()

    def fake_urlopen(url, timeout):
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr(meta_graph.urllib.request, "urlopen", fake_urlopen)
    fetcher = meta_graph.GraphLeadFetcher("secret-token")
    fields = fetcher.fetch("lead-abc")
    assert fields["full_name"] == "Asha Rao"
    assert "access_token=secret-token" in captured["url"]
