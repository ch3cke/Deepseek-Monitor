import json
import uuid

from datetime import datetime, timezone
import requests

from app.storage.base import StorageBackend
from app.utils.time import now_iso

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
REQUEST_TIMEOUT = 60
PAGE_SIZE = 500
BATCH_SIZE = 1000

MANAGED_USERS_FIELDS = [
    "name",
    "budget_limit",
    "warning_threshold",
    "status",
    "created_at",
    "updated_at",
]
API_KEYS_FIELDS = [
    "api_key_identity",
    "user_name",
    "sensitive_id",
    "redacted_key",
    "platform_created_at",
    "status",
    "first_seen_at",
    "last_seen_at",
    "deleted_at",
    "final_cost",
    "final_tokens",
    "final_requests",
]
USAGE_RECORD_FIELDS = [
    "recorded_at",
    "month",
    "year",
    "user_name",
    "cost",
    "tokens",
    "requests",
    "models_info",
    "api_keys_info",
    "active_key_identities",
    "status",
]
EVENT_FIELDS = [
    "event_key",
    "created_at",
    "month",
    "year",
    "period_key",
    "user_name",
    "api_key_identity",
    "event_type",
    "reason",
    "cost",
    "tokens",
    "requests",
    "payload",
]


class FeishuBitableStorage(StorageBackend):
    name = "feishu_bitable"

    def __init__(self, config):
        self.config = config
        self._tenant_access_token = None

    def startup_message(self):
        return "Feishu Bitable storage enabled."

    def get_state(self):
        users = {}
        for record in self._list_all_records(
            self.config.feishu_bitable_tables["managed_users"],
            MANAGED_USERS_FIELDS,
        ):
            fields = record.get("fields", {})
            name = self._text_value(fields.get("name"))
            if not name:
                continue
            users[name] = {
                "budget_limit": self._float_value(fields.get("budget_limit")),
                "warning_threshold": self._float_value(fields.get("warning_threshold")),
                "status": self._text_value(fields.get("status")) or "active",
            }

        events = []
        for record in self._list_all_records(
            self.config.feishu_bitable_tables["events"],
            EVENT_FIELDS,
        ):
            fields = record.get("fields", {})
            event_key = self._text_value(fields.get("event_key"))
            if not event_key:
                continue
            events.append({
                "event_key": event_key,
                "user_name": self._text_value(fields.get("user_name")),
                "api_key_identity": self._text_value(fields.get("api_key_identity")),
                "event_type": self._text_value(fields.get("event_type")),
                "month": self._int_value(fields.get("month")),
                "year": self._int_value(fields.get("year")),
                "period_key": self._text_value(fields.get("period_key")),
            })

        return {"users": users, "events": events}

    def push_snapshot(self, result, month, year, managed_users, api_keys, events):
        recorded_at = now_iso()
        self._upsert_managed_users(managed_users, recorded_at)
        self._upsert_api_keys(api_keys, result, recorded_at)
        usage_count = self._append_usage_records(result, month, year, recorded_at)
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
        existing = self._record_index(
            self.config.feishu_bitable_tables["managed_users"],
            "name",
            MANAGED_USERS_FIELDS,
        )
        create_records = []
        update_records = []

        for user in managed_users:
            key = user.get("name")
            if not key:
                continue
            fields = {
                "name": key,
                "budget_limit": float(user.get("budget_limit", 100)),
                "warning_threshold": float(user.get("warning_threshold", 80)),
                "status": user.get("status") or "active",
                "updated_at": recorded_at,
            }
            current = existing.get(key)
            if current:
                update_records.append({
                    "record_id": current["record_id"],
                    "fields": fields,
                })
            else:
                fields["created_at"] = recorded_at
                create_records.append({"fields": fields})

        self._batch_create_records(self.config.feishu_bitable_tables["managed_users"], create_records)
        self._batch_update_records(self.config.feishu_bitable_tables["managed_users"], update_records)

    def _upsert_api_keys(self, api_keys,result, recorded_at):
        existing = self._record_index(
            self.config.feishu_bitable_tables["api_keys"],
            "api_key_identity",
            API_KEYS_FIELDS,
        )
        create_records = []
        update_records = []

        tables = dict()
        users = result.get("users", {})
        for name, info in users.items():
            tables[info.get("active_api_key", {}).get("api_key_identity")] = info

        for api_key in api_keys:
            key = api_key.get("api_key_identity")
            if not key:
                continue
            current = existing.get(key)
            current_fields = current.get("fields", {}) if current else {}
            fields = {
                "api_key_identity": key,
                "user_name": api_key.get("user_name") or "",
                "sensitive_id": api_key.get("sensitive_id") or "",
                "redacted_key": api_key.get("redacted_key") or "",
                "platform_created_at": api_key.get("platform_created_at") or "",
                "status": api_key.get("status") or "active",
                "last_seen_at": recorded_at,
                "deleted_at": api_key.get("deleted_at") or self._text_value(current_fields.get("deleted_at")),
                "final_cost": tables.get(key,{}).get("cost") or 0.0,
                "final_tokens": tables.get(key,{}).get("tokens") or 0,
                "final_requests": int(tables.get(key,{}).get("requests") or 0),
            }
            if current:
                update_records.append({
                    "record_id": current["record_id"],
                    "fields": fields,
                })
            else:
                fields["first_seen_at"] = recorded_at
                create_records.append({"fields": fields})

        self._batch_create_records(self.config.feishu_bitable_tables["api_keys"], create_records)
        self._batch_update_records(self.config.feishu_bitable_tables["api_keys"], update_records)

    def _append_usage_records(self, result, month, year, recorded_at):
        records = []
        for user_name, info in (result.get("users") or {}).items():
            active_key_identities = info.get("active_api_key", {}).get("api_key_identity","")

            records.append({
                "fields": {
                    "recorded_at": to_feishu_datetime_ms(recorded_at),
                    "month": int(month),
                    "year": int(year),
                    "user_name": user_name,
                    "cost": float(info.get("cost", 0)),
                    "tokens": int(info.get("tokens", 0)),
                    "requests": int(info.get("requests", 0)),
                    "models_info": self._json_dump(info.get("models", {})),
                    "api_keys_info": self._json_dump(info.get("api_keys", [])),
                    "active_key_identities": active_key_identities,
                    "status": "observed",
                }
            })

        self._batch_create_records(self.config.feishu_bitable_tables["usage_records"], records)
        return len(records)

    def _upsert_events(self, events):
        existing = self._record_index(
            self.config.feishu_bitable_tables["events"],
            "event_key",
            EVENT_FIELDS,
        )
        create_records = []
        update_records = []

        for event in events:
            key = event.get("event_key")
            if not key:
                continue
            fields = {
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
            }
            current = existing.get(key)
            if current:
                update_records.append({
                    "record_id": current["record_id"],
                    "fields": fields,
                })
            else:
                create_records.append({"fields": fields})

        self._batch_create_records(self.config.feishu_bitable_tables["events"], create_records)
        self._batch_update_records(self.config.feishu_bitable_tables["events"], update_records)
        return len(create_records) + len(update_records)

    def _record_index(self, table_id, key_field, field_names):
        index = {}
        for record in self._list_all_records(table_id, field_names):
            fields = record.get("fields", {})
            key = self._text_value(fields.get(key_field))
            if key:
                index[key] = {
                    "record_id": record.get("record_id") or record.get("id"),
                    "fields": fields,
                }
        return index

    def _list_all_records(self, table_id, field_names):
        items = []
        page_token = None

        while True:
            params = {
                "page_size": PAGE_SIZE,
                "field_names": self._json_dump(field_names),
            }
            if page_token:
                params["page_token"] = page_token
            data = self._request_json(
                "GET",
                f"/bitable/v1/apps/{self.config.feishu_bitable_app_token}/tables/{table_id}/records",
                params=params,
            ).get("data", {})
            items.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break

        return items

    def _batch_create_records(self, table_id, records):
        for chunk in self._chunks(records, BATCH_SIZE):
            if not chunk:
                continue
            self._request_json(
                "POST",
                f"/bitable/v1/apps/{self.config.feishu_bitable_app_token}/tables/{table_id}/records/batch_create",
                json_body={
                    "records": chunk,
                },
                params={
                    "client_token": str(uuid.uuid4()),
                },
            )

    def _batch_update_records(self, table_id, records):
        for chunk in self._chunks(records, BATCH_SIZE):
            if not chunk:
                continue
            self._request_json(
                "POST",
                f"/bitable/v1/apps/{self.config.feishu_bitable_app_token}/tables/{table_id}/records/batch_update",
                json_body={
                    "records": chunk,
                },
            )

    def _request_json(self, method, path, params=None, json_body=None):
        response = requests.request(
            method,
            f"{FEISHU_API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {self._tenant_access_token_value()}",
                "Content-Type": "application/json; charset=utf-8",
            },
            params=params,
            json=json_body,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") not in (0, None):
            raise RuntimeError(
                f"Feishu Bitable API error: code={data.get('code')} msg={data.get('msg')}"
            )
        return data

    def _tenant_access_token_value(self):
        if self._tenant_access_token:
            return self._tenant_access_token

        response = requests.post(
            f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            headers={
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "app_id": self.config.feishu_app_id,
                "app_secret": self.config.feishu_app_secret,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") not in (0, None) or not data.get("tenant_access_token"):
            raise RuntimeError(
                f"Failed to obtain Feishu tenant_access_token: code={data.get('code')} msg={data.get('msg')}"
            )
        self._tenant_access_token = data["tenant_access_token"]
        return self._tenant_access_token

    def _json_dump(self, value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def _text_value(self, value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return self._json_dump(value)

    def _float_value(self, value):
        if value in (None, ""):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _int_value(self, value):
        if value in (None, ""):
            return 0
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    def _chunks(self, items, size):
        if not items:
            return []
        return [items[index:index + size] for index in range(0, len(items), size)]

def to_feishu_datetime_ms(value):
    if value is None:
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)

    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)

    raise TypeError(f"Unsupported datetime value: {value!r}")