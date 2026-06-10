# Supabase Storage

`SupabaseStorage` mirrors the same four logical datasets used by the Cloudflare/D1 backend:

- `managed_users`
- `api_keys`
- `usage_records`
- `events`

## Required Secrets

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_MANAGED_USERS_TABLE` (optional, default `managed_users`)
- `SUPABASE_API_KEYS_TABLE` (optional, default `api_keys`)
- `SUPABASE_USAGE_RECORDS_TABLE` (optional, default `usage_records`)
- `SUPABASE_EVENTS_TABLE` (optional, default `events`)

## Setup

1. Create a Supabase project.
2. Apply [supabase/schema.sql](/Users/ch3cke/Desktop/project/Deepseek-Monitor/supabase/schema.sql:1) in the SQL editor.
3. Use the service role key as `SUPABASE_SERVICE_ROLE_KEY`.
4. Keep Row Level Security disabled for these internal tables, or create policies that allow the service role to read and write them.

## Table Model

The current implementation expects these unique keys:

- `managed_users.name`
- `api_keys.api_key_identity`
- `events.event_key`

`usage_records` is append-only and uses a generated numeric primary key.

## API Model

`SupabaseStorage` uses the hosted PostgREST API:

- `GET /rest/v1/<table>?select=...`
- `POST /rest/v1/<table>` for inserts
- `POST /rest/v1/<table>?on_conflict=<key>` with `Prefer: resolution=merge-duplicates` for upserts

## Notes

- In `STORAGE_BACKEND=auto`, Cloudflare takes precedence, then Supabase, then Feishu Bitable.
- The storage schema mirrors the D1 schema closely so the same business logic can run unchanged.
- JSON-heavy fields such as `models_info` and `payload` are currently stored as text values containing serialized JSON.
