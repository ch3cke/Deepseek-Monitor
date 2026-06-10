# DeepSeek Monitor

[![Monitor Workflow](https://github.com/ch3cke/Deepseek-Monitor/actions/workflows/monitor.yml/badge.svg)](https://github.com/ch3cke/Deepseek-Monitor/actions/workflows/monitor.yml)
[![Summary Workflow](https://github.com/ch3cke/Deepseek-Monitor/actions/workflows/summary.yml/badge.svg)](https://github.com/ch3cke/Deepseek-Monitor/actions/workflows/summary.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/ch3cke/Deepseek-Monitor/blob/main/LICENSE)

This repository runs a scheduled DeepSeek usage monitor on GitHub Actions.

The workflow is:

```text
GitHub Actions (every 10 minutes)
  -> Python downloads DeepSeek usage export
  -> Aggregate usage by monitored api_key name
  -> Send email warning at 80
  -> Delete active API key at 100
  -> Optionally persist lifecycle logs in Cloudflare D1
  -> Optionally mark deleted keys as used instead of removing them from history
```

## What It Does

- `MONITORED_USERS` is a comma-separated list of `api_key.name` values to monitor.
- When a monitored user reaches `DEFAULT_WARNING_THRESHOLD` the job sends one warning email per billing month and active key scope.
- When a monitored user reaches `DEFAULT_BUDGET_LIMIT` the job deletes the currently active DeepSeek API key.
- If Cloudflare storage is enabled, the deleted key is also recorded as `used` in D1 and historical logs are kept.

## Files

```text
.github/workflows/
  monitor.yml
  summary.yml
app/
  main.py
  config.py
  platform_client.py
  extractor.py
  aggregator.py
  events.py
  notifications.py
  ingest_client.py
  models.py
  notifier/
    base.py
    email.py
    manager.py
    webhook.py
  storage/
    base.py
    cloudflare.py
    feishu_bitable.py
    noop.py
    supabase.py
  utils/
    api_keys.py
    formatting.py
    time.py
cloudflare/
  worker.js
  schema.sql
supabase/
  schema.sql
tests/
  test_main.py
.env.example
CONTRIBUTING.md
LICENSE
CHANGELOG.md
SECURITY.md
docs/
  architecture.md
  deployment.md
README.md
```

## Project Metadata

- License: [MIT](/Users/ch3cke/Desktop/project/Deepseek-Monitor/LICENSE:1)
- Contributing guide: [CONTRIBUTING.md](/Users/ch3cke/Desktop/project/Deepseek-Monitor/CONTRIBUTING.md:1)
- Security policy: [SECURITY.md](/Users/ch3cke/Desktop/project/Deepseek-Monitor/SECURITY.md:1)
- Changelog: [CHANGELOG.md](/Users/ch3cke/Desktop/project/Deepseek-Monitor/CHANGELOG.md:1)
- Architecture notes: [docs/architecture.md](/Users/ch3cke/Desktop/project/Deepseek-Monitor/docs/architecture.md:1)
- Deployment guide: [docs/deployment.md](/Users/ch3cke/Desktop/project/Deepseek-Monitor/docs/deployment.md:1)
- Feishu Bitable storage guide: [docs/feishu-bitable-storage.md](/Users/ch3cke/Desktop/project/Deepseek-Monitor/docs/feishu-bitable-storage.md:1)
- Supabase storage guide: [docs/supabase-storage.md](/Users/ch3cke/Desktop/project/Deepseek-Monitor/docs/supabase-storage.md:1)

## Open Source Setup

This repository is structured to be published as an open-source project.

- Do not commit real cookies, tokens, SMTP credentials, or bot webhooks.
- Put all sensitive values into GitHub Actions Secrets.
- Use [.env.example](/Users/ch3cke/Desktop/project/Deepseek-Monitor/.env.example:1) as the local template and keep real values only in `.env`, which is already ignored by git.

## Required GitHub Secrets

Configure these in `Settings -> Secrets and variables -> Actions`.

```text
AUTH
MONITORED_USERS
DEFAULT_BUDGET_LIMIT
DEFAULT_WARNING_THRESHOLD

DEEPSEEK_INTERCOM_DEVICE_ID
DEEPSEEK_HWWAFSESID
DEEPSEEK_HWWAFSESTIME

SMTP_SERVER
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
SENDER_EMAIL
RECEIVER_EMAIL
```

Optional:

```text
STORAGE_BACKEND
CLOUDFLARE_INGEST_URL
INGEST_TOKEN
FEISHU_APP_ID
FEISHU_APP_SECRET
FEISHU_BITABLE_APP_TOKEN
FEISHU_BITABLE_USERS_TABLE_ID
FEISHU_BITABLE_API_KEYS_TABLE_ID
FEISHU_BITABLE_USAGE_TABLE_ID
FEISHU_BITABLE_EVENTS_TABLE_ID
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_MANAGED_USERS_TABLE
SUPABASE_API_KEYS_TABLE
SUPABASE_USAGE_RECORDS_TABLE
SUPABASE_EVENTS_TABLE
FEISHU_BOT_WEBHOOK_URL
FEISHU_BOT_SECRET
FEISHU_BOT_KEYWORD
FEISHU_BOT_MESSAGE_TYPE
```

Example:

```text
MONITORED_USERS=alice,bob,charlie
DEFAULT_WARNING_THRESHOLD=80
DEFAULT_BUDGET_LIMIT=100
STORAGE_BACKEND=cloudflare
CLOUDFLARE_INGEST_URL=https://your-worker.workers.dev/api/ingest
```

`STORAGE_BACKEND` supports:

- `auto`: use Cloudflare first, then Supabase, then Feishu Bitable when their full configs are present
- `cloudflare`: prefer Cloudflare storage, but still degrades to no-op if required secrets are missing
- `supabase`: prefer Supabase storage, but still degrades to no-op if required secrets are missing
- `feishu_bitable`: prefer Feishu Bitable storage, but still degrades to no-op if required secrets are missing
- `none`: disable persistence explicitly

## Cloudflare Setup

This section is optional. `IngestClient` is enabled only when both `CLOUDFLARE_INGEST_URL` and `INGEST_TOKEN` are set. If either one is missing, the monitor still runs, but without persisted state, history, or cross-run deduplication.

1. Create a D1 database.
2. Run [cloudflare/schema.sql](/Users/ch3cke/Desktop/project/Deepseek-Monitor/cloudflare/schema.sql:1) in the D1 SQL console.
3. Deploy [cloudflare/worker.js](/Users/ch3cke/Desktop/project/Deepseek-Monitor/cloudflare/worker.js:1) as a Worker.
4. Bind the D1 database to `DB`.
5. Add a Worker secret:

```text
INGEST_TOKEN=<same value as GitHub secret>
```

The Worker exposes:

- `POST /api/ingest`
- `GET /api/state`
- `GET /api/users`
- `GET /api/usage?user=<name>&limit=100&month=6&year=2026`
- `GET /api/events?user=<name>&event_type=warning&limit=100`
- `GET /api/api-keys?user=<name>&status=used`
- `GET /api/summary?month=6&year=2026`

All `/api/*` endpoints require `Authorization: Bearer <INGEST_TOKEN>`.

## Interface Model

The storage layer is now abstracted behind `app/storage/`.

- `managed_users` is the configuration interface for monitored names and thresholds.
- `api_keys` is the lifecycle interface for active and used keys.
- `usage_records` is a snapshot interface for periodic usage observations.
- `events` is the audit/event-stream interface for warning, block, and delete actions.

Current implementations:

- `CloudflareStorage`: wraps [app/ingest_client.py](/Users/ch3cke/Desktop/project/Deepseek-Monitor/app/ingest_client.py:1)
- `SupabaseStorage`: writes the same logical tables into a Supabase Postgres schema through the REST API
- `FeishuBitableStorage`: reads and writes the same logical state into Feishu Bitable tables
- `NoopStorage`: runs the monitor without persistence

`IngestClient` remains the Cloudflare-specific transport with:

- `get_state()`
- `get_users()`
- `get_usage()`
- `get_events()`
- `get_api_keys()`
- `get_summary()`
- `push_snapshot()`

This means future backends such as another online database can be added as new classes under `app/storage/` without changing `app/main.py`.

For the Feishu Bitable schema and setup details, see [docs/feishu-bitable-storage.md](/Users/ch3cke/Desktop/project/Deepseek-Monitor/docs/feishu-bitable-storage.md:1).
For the Supabase schema and setup details, see [docs/supabase-storage.md](/Users/ch3cke/Desktop/project/Deepseek-Monitor/docs/supabase-storage.md:1).

## GitHub Actions Schedule

The workflow is configured in [monitor.yml](/Users/ch3cke/Desktop/project/Deepseek-Monitor/.github/workflows/monitor.yml:1) and runs every 10 minutes:

```yaml
schedule:
  - cron: "*/10 * * * *"
```

You can also trigger it manually with `workflow_dispatch`.

There is also a daily summary workflow at [summary.yml](/Users/ch3cke/Desktop/project/Deepseek-Monitor/.github/workflows/summary.yml:1). It runs `python -m app.main summary` and sends a consolidated usage email.

## Notification Channels

The project supports a composite notifier in `app/notifier/manager.py`, which currently includes:

- Email via SMTP
- Feishu custom bot via webhook

If both are configured, both will receive warning, delete, and summary notifications. Additional channels can be added as new classes under `app/notifier/` without changing the monitor flow.

Feishu setup:

1. Create a custom bot in the target Feishu group.
2. Copy its webhook URL.
3. Save it as the GitHub secret `FEISHU_BOT_WEBHOOK_URL`.
4. If the bot enables signature verification, save the bot secret as `FEISHU_BOT_SECRET`.
5. If the group requires a keyword, save it as `FEISHU_BOT_KEYWORD`.
6. Optionally set `FEISHU_BOT_MESSAGE_TYPE` to `text`, `post`, or `interactive`.

Current Feishu features:

- `text` message mode
- `post` rich text mode
- `interactive` card mode
- optional webhook signature fields `timestamp` and `sign`
- optional keyword prefix injection

The official Feishu custom bot documentation is here:

- https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
- https://open.feishu.cn/document/server-docs/im-v1/message-content-description/create_json

## Local Verification

Install dependencies and run:

```bash
python -m unittest discover -s tests
python -m compileall app
node --check cloudflare/worker.js
```

## D1 Data Model

- `managed_users`: monitored names and thresholds.
- `api_keys`: lifecycle table for active and used keys.
- `usage_records`: periodic per-user usage snapshots.
- `events`: warning, block, and delete events.

This is a hybrid storage model:

- `api_keys` and `managed_users` hold the latest lifecycle/config state.
- `usage_records` stores repeated monthly snapshots every 10 minutes.
- `events` stores immutable governance actions and warning history.

That means you can build interfaces for both "current state" and "historical audit" from the same database.

Deleted keys remain in `api_keys` with:

```text
status = used
deleted_at = timestamp
final_cost / final_tokens / final_requests = final observed totals
```
