from collections import defaultdict

import requests

from app.config import AppConfig

DEEPSEEK_API_BASE = "https://platform.deepseek.com/api/v0"
REQUEST_TIMEOUT = 60
EXPORT_TIMEOUT = 120


class PlatformClient:
    def __init__(self, config: AppConfig):
        self.config = config

    def request_json(self, method, url, **kwargs):
        response = requests.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
        response.raise_for_status()
        try:
            return response.json()
        except Exception as exc:
            raise RuntimeError(f"Expected JSON response but got: {response.text[:500]}") from exc

    def list_api_keys_by_name(self):
        data = self.request_json(
            "GET",
            f"{DEEPSEEK_API_BASE}/users/get_api_keys",
            headers=self.config.headers,
        )

        grouped = defaultdict()
        api_keys = (
            data.get("data", {})
            .get("biz_data", {})
            .get("api_keys", [])
        )
        monitored_users = set(self.config.monitored_users)

        for api_key in api_keys:
            name = api_key.get("name")
            if name and name in monitored_users:
                grouped[name] = api_key

        return {name: keys for name, keys in grouped.items()}

    def request_usage_export(self, month, year):
        response = requests.get(
            f"{DEEPSEEK_API_BASE}/usage/export",
            params={"month": month, "year": year},
            headers=self.config.headers,
            timeout=EXPORT_TIMEOUT,
        )
        response.raise_for_status()
        return response

    def delete_api_key(self, api_key):
        response = requests.post(
            f"{DEEPSEEK_API_BASE}/users/edit_api_keys",
            headers=self.config.headers,
            json={
                "action": "delete",
                "name": None,
                "redacted_key": str(api_key.get("sensitive_id") or ""),
                "created_at": api_key.get("created_at") or api_key.get("platform_created_at"),
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
