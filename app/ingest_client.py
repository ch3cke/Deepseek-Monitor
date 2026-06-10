import requests
from urllib.parse import urlencode

from app.config import AppConfig
from app.utils.time import now_iso

REQUEST_TIMEOUT = 60


class IngestClient:
    def __init__(self, config: AppConfig):
        self.config = config

    def request_json(self, path, method="GET", json_body=None):
        response = requests.request(
            method,
            f"{self.config.cloudflare_base_url}{path}",
            headers={
                "Authorization": f"Bearer {self.config.ingest_token}",
                "Content-Type": "application/json",
            },
            json=json_body,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def get_state(self):
        return self.request_json("/api/state", "GET")

    def get_users(self, status=None):
        query = {}
        if status:
            query["status"] = status
        suffix = f"?{urlencode(query)}" if query else ""
        return self.request_json(f"/api/users{suffix}", "GET")

    def get_usage(self, user, limit=100, month=None, year=None):
        query = {"user": user, "limit": limit}
        if month is not None:
            query["month"] = month
        if year is not None:
            query["year"] = year
        return self.request_json(f"/api/usage?{urlencode(query)}", "GET")

    def get_events(self, limit=100, user=None, event_type=None, month=None, year=None):
        query = {"limit": limit}
        if user:
            query["user"] = user
        if event_type:
            query["event_type"] = event_type
        if month is not None:
            query["month"] = month
        if year is not None:
            query["year"] = year
        return self.request_json(f"/api/events?{urlencode(query)}", "GET")

    def get_api_keys(self, limit=100, user=None, status=None):
        query = {"limit": limit}
        if user:
            query["user"] = user
        if status:
            query["status"] = status
        return self.request_json(f"/api/api-keys?{urlencode(query)}", "GET")

    def get_summary(self, month=None, year=None):
        query = {}
        if month is not None:
            query["month"] = month
        if year is not None:
            query["year"] = year
        suffix = f"?{urlencode(query)}" if query else ""
        return self.request_json(f"/api/summary{suffix}", "GET")

    def push_snapshot(self, result, month, year, managed_users, api_keys, events):
        response = requests.post(
            self.config.cloudflare_ingest_url,
            headers={
                "Authorization": f"Bearer {self.config.ingest_token}",
                "Content-Type": "application/json",
            },
            json={
                "recorded_at": now_iso(),
                "month": int(month),
                "year": int(year),
                "managed_users": managed_users,
                "api_keys": api_keys,
                "result": result,
                "events": events,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
