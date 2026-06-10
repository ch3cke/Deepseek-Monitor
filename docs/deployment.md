# Deployment

## 1. Fork Or Clone

Create your own repository or fork this project.

## 2. Configure Secrets

Add these GitHub Actions Secrets:

### Required

- `AUTH`
- `MONITORED_USERS`
- `DEFAULT_BUDGET_LIMIT`
- `DEFAULT_WARNING_THRESHOLD`
- `DEEPSEEK_INTERCOM_DEVICE_ID`
- `DEEPSEEK_HWWAFSESID`
- `DEEPSEEK_HWWAFSESTIME`

### Optional Email

- `SMTP_SERVER`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SENDER_EMAIL`
- `RECEIVER_EMAIL`

### Optional Feishu

- `FEISHU_BOT_WEBHOOK_URL`
- `FEISHU_BOT_SECRET`
- `FEISHU_BOT_KEYWORD`
- `FEISHU_BOT_MESSAGE_TYPE`

### Optional Cloudflare Storage

- `STORAGE_BACKEND`
- `CLOUDFLARE_INGEST_URL`
- `INGEST_TOKEN`

### Optional Feishu Bitable Storage

- `STORAGE_BACKEND=feishu_bitable` or `auto`
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_BITABLE_APP_TOKEN`
- `FEISHU_BITABLE_USERS_TABLE_ID`
- `FEISHU_BITABLE_API_KEYS_TABLE_ID`
- `FEISHU_BITABLE_USAGE_TABLE_ID`
- `FEISHU_BITABLE_EVENTS_TABLE_ID`

### Optional Supabase Storage

- `STORAGE_BACKEND=supabase` or `auto`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_MANAGED_USERS_TABLE` (optional)
- `SUPABASE_API_KEYS_TABLE` (optional)
- `SUPABASE_USAGE_RECORDS_TABLE` (optional)
- `SUPABASE_EVENTS_TABLE` (optional)

## 3. Deploy Cloudflare Worker

This section is only required when `STORAGE_BACKEND=auto` with Cloudflare secrets present, or when `STORAGE_BACKEND=cloudflare`.

1. Create a D1 database.
2. Apply [cloudflare/schema.sql](/Users/ch3cke/Desktop/project/Deepseek-Monitor/cloudflare/schema.sql:1).
3. Deploy [cloudflare/worker.js](/Users/ch3cke/Desktop/project/Deepseek-Monitor/cloudflare/worker.js:1).
4. Bind the D1 database as `DB`.
5. Set Worker secret `INGEST_TOKEN`.

## 4. Enable GitHub Actions

- `monitor.yml` runs the governance monitor every 10 minutes.
- `summary.yml` sends a daily summary.

You can also trigger both manually from the Actions tab.

## 5. Verify Deployment

### Python

```bash
python -m unittest discover -s tests
python -m compileall app
```

### Worker

```bash
node --check cloudflare/worker.js
```

### Runtime

After the first successful workflow run:

- check `/api/users`
- check `/api/summary`
- check `/api/events`

All API requests must include:

```text
Authorization: Bearer <INGEST_TOKEN>
```

## 6. Configure Feishu Bitable Storage

This section is only required when `STORAGE_BACKEND=feishu_bitable`, or when `STORAGE_BACKEND=auto` and you want Bitable to be the fallback storage backend.

1. Create a Feishu self-built app and grant it Bitable record read/write permissions.
2. Add the app as a document application or collaborator to the target Base.
3. Create the four logical tables used by the monitor.
4. Fill in the corresponding `FEISHU_BITABLE_*` secrets.
5. Use the exact field names described in [docs/feishu-bitable-storage.md](/Users/ch3cke/Desktop/project/Deepseek-Monitor/docs/feishu-bitable-storage.md:1).

## 7. Configure Supabase Storage

This section is only required when `STORAGE_BACKEND=supabase`, or when `STORAGE_BACKEND=auto` and you want Supabase to be the fallback storage backend.

1. Create a Supabase project.
2. Apply [supabase/schema.sql](/Users/ch3cke/Desktop/project/Deepseek-Monitor/supabase/schema.sql:1) in the SQL editor.
3. Create a service role key for server-side writes.
4. Fill in the corresponding `SUPABASE_*` secrets.
5. Keep the unique constraints on `managed_users.name`, `api_keys.api_key_identity`, and `events.event_key` for upsert behavior.

## 8. Common Deployment Choices

### Email Only

Set `STORAGE_BACKEND=none` if you do not want persistence, configure SMTP secrets, and leave Feishu secrets empty.

### Feishu Only

Configure `FEISHU_BOT_WEBHOOK_URL` and leave SMTP secrets empty.

### Email And Feishu

Configure both. The monitor sends the same warning and summary content to both channels.

### Cloudflare Persistence

Set `STORAGE_BACKEND=cloudflare` or keep `auto`, then provide both `CLOUDFLARE_INGEST_URL` and `INGEST_TOKEN`.

### Feishu Bitable Persistence

Set `STORAGE_BACKEND=feishu_bitable` or keep `auto`, then provide all `FEISHU_APP_*` and `FEISHU_BITABLE_*` secrets.

### Supabase Persistence

Set `STORAGE_BACKEND=supabase` or keep `auto`, then provide all `SUPABASE_*` secrets.
