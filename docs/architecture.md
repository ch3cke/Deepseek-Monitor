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
     -> Email / Feishu notifiers
     -> Cloudflare ingest client
  -> Cloudflare Worker
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
- `app/notifier/` dispatches email and Feishu messages.
- `app/ingest_client.py` writes snapshots and reads the Worker API.

### Cloudflare Worker and D1

- `cloudflare/worker.js` exposes authenticated REST endpoints.
- `cloudflare/schema.sql` defines D1 tables and indexes.
- D1 stores both current lifecycle state and historical audit data.

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

This keeps the Python runner stateless. GitHub Actions performs collection and decisions, while Cloudflare hosts state and query APIs.

## Notification Model

Notification channels are independent and optional:

- SMTP email
- Feishu custom bot webhook

The monitor can use either channel alone or both together.
