# Architecture

## Overview

The project is a scheduled governance system for DeepSeek API usage.

```text
GitHub Actions
  -> Python monitor package
     -> DeepSeek platform client
     -> CSV extractor
     -> Usage aggregator
     -> Event engine
     -> Notification manager
     -> Storage backend
        -> Cloudflare ingest client
        -> Supabase storage
        -> Feishu Bitable storage
        -> No-op storage
  -> Optional Cloudflare Worker
     -> Authenticated REST API
     -> D1 persistence
```

## Runtime Components

### GitHub Actions

- `monitor.yml` runs every 10 minutes.
- `summary.yml` runs once per day.
- All secrets are injected at runtime through Actions Secrets.

### Python Application

- `app/main.py` orchestrates monitor and summary commands.
- `app/platform_client.py` talks to DeepSeek platform APIs.
- `app/extractor.py` parses the export ZIP and CSV payloads.
- `app/aggregator.py` groups usage by monitored `api_key.name`.
- `app/events.py` decides warning and delete actions.
- `app/notifications.py` formats user-facing messages.
- `app/notifier/` contains channel implementations plus a composite manager.
- `app/storage/` contains storage backends selected by configuration.
- `app/ingest_client.py` is the Cloudflare-specific transport used by the Cloudflare storage backend.

### Storage Backends

- `CloudflareStorage` persists monitor state and history through Worker APIs.
- `SupabaseStorage` persists the same lifecycle and audit model into hosted Postgres tables via Supabase REST.
- `FeishuBitableStorage` persists the same lifecycle and audit model into Feishu Base tables.
- `NoopStorage` allows the monitor to run without persistence.
- Future backends such as another online database should be added as new classes under `app/storage/`.

### Cloudflare Worker and D1

- [cloudflare/worker.js](/Users/ch3cke/Desktop/project/Deepseek-Monitor/cloudflare/worker.js:1) exposes authenticated REST endpoints.
- [cloudflare/schema.sql](/Users/ch3cke/Desktop/project/Deepseek-Monitor/cloudflare/schema.sql:1) defines D1 tables and indexes.
- D1 stores both current lifecycle state and historical audit data when Cloudflare storage is enabled.

## Data Model

### managed_users

Current configuration for monitored names:

- budget limit
- warning threshold
- current status

### api_keys

Lifecycle state per key identity:

- first seen / last seen
- active vs used
- final cost, token, and request counts after deletion

### usage_records

Repeated snapshots taken every 10 minutes:

- user totals
- model totals
- active key identities
- key-level summarized usage

### events

Immutable governance history:

- warning
- block
- delete_api

## Interface Model

The Worker is the primary query interface over storage:

- `POST /api/ingest`
- `GET /api/state`
- `GET /api/users`
- `GET /api/usage`
- `GET /api/events`
- `GET /api/api-keys`
- `GET /api/summary`

This keeps the Python runner loosely coupled to storage. GitHub Actions performs collection and decisions, while the selected storage backend handles persistence and query APIs.

## Notification Model

Notification channels are independent and optional implementations behind the notifier manager:

- SMTP email
- Feishu custom bot webhook

The monitor can use either channel alone or both together, and future channels can be added without changing the monitor orchestration.
