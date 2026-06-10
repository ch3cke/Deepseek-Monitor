# Feishu Bitable Storage

`FeishuBitableStorage` mirrors the same four logical datasets used by the Cloudflare/D1 backend:

- `managed_users`
- `api_keys`
- `usage_records`
- `events`

## Required Secrets

Add these GitHub Actions secrets when using `STORAGE_BACKEND=feishu_bitable`:

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_BITABLE_APP_TOKEN`
- `FEISHU_BITABLE_USERS_TABLE_ID`
- `FEISHU_BITABLE_API_KEYS_TABLE_ID`
- `FEISHU_BITABLE_USAGE_TABLE_ID`
- `FEISHU_BITABLE_EVENTS_TABLE_ID`

## Required Feishu Permissions

The current implementation uses the following official Feishu APIs:

- `POST /open-apis/auth/v3/tenant_access_token/internal`
- `GET /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records`
- `POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/batch_create`
- `POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/batch_update`

Grant at least these permissions to the self-built app:

- `bitable:app` or equivalent record read/write permissions
- `base:record:create`
- `base:record:update`

The app must also be added to the target Base as a document application or collaborator with sufficient edit permissions.

## Table Schema

Create four tables in the target Base and use the exact field names below.

### managed_users

- `name`
- `budget_limit`
- `warning_threshold`
- `status`
- `created_at`
- `updated_at`

### api_keys

- `api_key_identity`
- `user_name`
- `sensitive_id`
- `redacted_key`
- `platform_created_at`
- `status`
- `first_seen_at`
- `last_seen_at`
- `deleted_at`
- `final_cost`
- `final_tokens`
- `final_requests`

### usage_records

- `recorded_at`
- `month`
- `year`
- `user_name`
- `cost`
- `tokens`
- `requests`
- `models_info`
- `api_keys_info`
- `active_key_identities`
- `status`

### events

- `event_key`
- `created_at`
- `month`
- `year`
- `period_key`
- `user_name`
- `api_key_identity`
- `event_type`
- `reason`
- `cost`
- `tokens`
- `requests`
- `payload`

## Field Type Recommendations

Recommended field types:

- identifiers, timestamps, statuses, JSON payloads: single-line text
- `budget_limit`, `warning_threshold`, `cost`, `final_cost`: number
- `month`, `year`, `tokens`, `requests`, `final_tokens`, `final_requests`: number

`models_info`, `api_keys_info`, `active_key_identities`, and `payload` are stored as JSON strings.

## Behavior Notes

- `managed_users`, `api_keys`, and `events` are upserted by unique logical keys.
- `usage_records` is append-only.
- In `STORAGE_BACKEND=auto`, Cloudflare takes precedence, then Supabase, then Feishu Bitable.
- For large datasets, Bitable write concurrency should remain low; the implementation writes in batches and avoids concurrent writes to the same table.
