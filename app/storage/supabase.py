import json

import requests

from app.storage.base import StorageBackend
from app.storage.feishu_bitable import (
    API_KEYS_FIELDS,
)
from app.utils.time import now_iso

REQUEST_TIMEOUT = 60
BATCH_SIZE = 1000


class SupabaseStorage(StorageBackend):
    name = "supabase"

    def __init__(self, config):
        self.config = config

    def startup_message(self):
        return "Supabase storage enabled."

    def get_state(self):
        users = {}
        for row in self._select_rows(
            self.config.supabase_tables["managed_users"],
            ["name", "budget_limit", "warning_threshold", "status"],
        ):
            name = row.get("name")
            if not name:
                continue
            users[name] = {
                "budget_limit": float(row.get("budget_limit") or 0),
                "warning_threshold": float(row.get("warning_threshold") or 0),
                "status": row.get("status") or "active",
            }

        events = []
        for row in self._select_rows(
            self.config.supabase_tables["events"],
            ["event_key", "user_name", "api_key_identity", "event_type", "month", "year", "period_key"],
        ):
            event_key = row.get("event_key")
            if not event_key:
                continue
            events.append({
                "event_key": event_key,
                "user_name": row.get("user_name") or "",
                "api_key_identity": row.get("api_key_identity") or "",
                "event_type": row.get("event_type") or "",
                "month": int(row.get("month") or 0),
                "year": int(row.get("year") or 0),
                "period_key": row.get("period_key") or "",
            })

        return {"users": users, "events": events}

    def push_snapshot(self, result, month, year, managed_users, api_keys, events):
        recorded_at = now_iso()
        self._upsert_managed_users(managed_users, recorded_at)
        self._upsert_api_keys(api_keys, recorded_at)
        usage_count = self._insert_usage_records(result, month, year, recorded_at)
        event_count = self._upsert_events(events)
        return {
            "ok": True,
            "backend": self.name,
            "managed_users": len(managed_users),
            "api_keys": len(api_keys),
            "usage_records": usage_count,
            "events": event_count,
        }

    def _upsert_managed_users(self, managed_users, recorded_at):
        existing = self._row_index(
            self.config.supabase_tables["managed_users"],
            "name",
            ["name", "created_at"],
        )
        rows = []
        for user in managed_users:
            name = user.get("name")
            if not name:
                continue
            current = existing.get(name, {})
            rows.append({
                "name": name,
                "budget_limit": float(user.get("budget_limit", 100)),
                "warning_threshold": float(user.get("warning_threshold", 80)),
                "status": user.get("status") or "active",
                "created_at": current.get("created_at") or recorded_at,
                "updated_at": recorded_at,
            })
        self._upsert_rows(self.config.supabase_tables["managed_users"], rows, "name")

    def _upsert_api_keys(self, api_keys, recorded_at):
        existing = self._row_index(
            self.config.supabase_tables["api_keys"],
            "api_key_identity",
            API_KEYS_FIELDS,
        )
        rows = []
        for api_key in api_keys:
            key = api_key.get("api_key_identity")
            if not key:
                continue
            current = existing.get(key, {})
            rows.append({
                "api_key_identity": key,
                "user_name": api_key.get("user_name") or "",
                "sensitive_id": api_key.get("sensitive_id") or "",
                "redacted_key": api_key.get("redacted_key") or "",
                "platform_created_at": api_key.get("platform_created_at") or "",
                "status": api_key.get("status") or "active",
                "first_seen_at": current.get("first_seen_at") or recorded_at,
                "last_seen_at": recorded_at,
                "deleted_at": api_key.get("deleted_at") or current.get("deleted_at"),
                "final_cost": float(api_key.get("final_cost", current.get("final_cost") or 0)),
                "final_tokens": int(api_key.get("final_tokens", current.get("final_tokens") or 0)),
                "final_requests": int(api_key.get("final_requests", current.get("final_requests") or 0)),
            })
        self._upsert_rows(self.config.supabase_tables["api_keys"], rows, "api_key_identity")

    def _insert_usage_records(self, result, month, year, recorded_at):
        rows = []
        for user_name, info in (result.get("users") or {}).items():
            active_key_identities = [
                api_key.get("api_key_identity")
                for api_key in info.get("active_api_keys", [])
                if api_key.get("api_key_identity")
            ]
            rows.append({
                "recorded_at": recorded_at,
                "month": int(month),
                "year": int(year),
                "user_name": user_name,
                "cost": float(info.get("cost", 0)),
                "tokens": int(info.get("tokens", 0)),
                "requests": int(info.get("requests", 0)),
                "models_info": self._json_dump(info.get("models", {})),
                "api_keys_info": self._json_dump(info.get("api_keys", [])),
                "active_key_identities": self._json_dump(active_key_identities),
                "status": "observed",
            })
        self._insert_rows(self.config.supabase_tables["usage_records"], rows)
        return len(rows)

    def _upsert_events(self, events):
        rows = []
        for event in events:
            key = event.get("event_key")
            if not key:
                continue
            rows.append({
                "event_key": key,
                "created_at": event.get("created_at") or now_iso(),
                "month": int(event.get("month", 0)),
                "year": int(event.get("year", 0)),
                "period_key": event.get("period_key") or "",
                "user_name": event.get("user_name") or "",
                "api_key_identity": event.get("api_key_identity") or "",
                "event_type": event.get("event_type") or "",
                "reason": event.get("reason") or "",
                "cost": float(event.get("cost", 0)),
                "tokens": int(event.get("tokens", 0)),
                "requests": int(event.get("requests", 0)),
                "payload": self._json_dump(event.get("payload", {})),
            })
        self._upsert_rows(self.config.supabase_tables["events"], rows, "event_key")
        return len(rows)

    def _row_index(self, table_name, key_field, columns):
        index = {}
        for row in self._select_rows(table_name, columns):
            key = row.get(key_field)
            if key:
                index[key] = row
        return index

    def _select_rows(self, table_name, columns):
        response = requests.get(
            f"{self.config.supabase_base_url}/{table_name}",
            headers=self._headers(),
            params={
                "select": ",".join(columns),
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _insert_rows(self, table_name, rows):
        for chunk in self._chunks(rows, BATCH_SIZE):
            if not chunk:
                continue
            response = requests.post(
                f"{self.config.supabase_base_url}/{table_name}",
                headers={
                    **self._headers(),
                    "Prefer": "return=minimal",
                },
                json=chunk,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

    def _upsert_rows(self, table_name, rows, conflict_field):
        for chunk in self._chunks(rows, BATCH_SIZE):
            if not chunk:
                continue
            response = requests.post(
                f"{self.config.supabase_base_url}/{table_name}",
                headers={
                    **self._headers(),
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                params={
                    "on_conflict": conflict_field,
                },
                json=chunk,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

    def _headers(self):
        return {
            "apikey": self.config.supabase_service_role_key,
            "Authorization": f"Bearer {self.config.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    def _json_dump(self, value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def _chunks(self, items, size):
        if not items:
            return []
        return [items[index:index + size] for index in range(0, len(items), size)]
