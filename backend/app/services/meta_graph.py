import json
import os
import urllib.parse
import urllib.request


def flatten_fields(value):
    if isinstance(value, dict) and "field_data" in value:
        value = value["field_data"]
    if isinstance(value, list):
        return {
            str(item.get("name")): (item.get("values") or [""])[0]
            for item in value
            if isinstance(item, dict) and item.get("name")
        }
    return value if isinstance(value, dict) else {}


class LeadFetcher:
    def fetch(self, leadgen_id):
        raise NotImplementedError


class MockLeadFetcher(LeadFetcher):
    def fetch(self, leadgen_id):
        if "missing-phone" in leadgen_id.lower():
            return {"name": "Graph Lead Missing Phone", "city": "Mumbai"}
        digits = "".join(ch for ch in leadgen_id if ch.isdigit())[-9:]
        phone = ("9" + digits).ljust(10, "0")[-10:]
        return {"name": "Graph Lead " + leadgen_id[-6:], "phone": phone, "city": "Mumbai"}


class GraphLeadFetcher(LeadFetcher):
    def __init__(self, access_token, api_version="v21.0"):
        self.access_token = access_token
        self.api_version = api_version

    def fetch(self, leadgen_id):
        if not self.access_token:
            raise RuntimeError("META_PAGE_ACCESS_TOKEN is not configured.")
        params = urllib.parse.urlencode({
            "fields": "field_data",
            "access_token": self.access_token,
        })
        url = (f"https://graph.facebook.com/{self.api_version}/"
               f"{urllib.parse.quote(leadgen_id, safe='')}?{params}")
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.load(response)
        return flatten_fields(data.get("field_data", []))


def get_fetcher():
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    return GraphLeadFetcher(token) if token else MockLeadFetcher()
