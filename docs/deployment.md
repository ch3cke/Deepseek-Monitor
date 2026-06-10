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
- `CLOUDFLARE_INGEST_URL`
- `INGEST_TOKEN`

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

## 3. Deploy Cloudflare Worker

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

## 6. Common Deployment Choices

### Email Only

Configure SMTP secrets and leave Feishu secrets empty.

### Feishu Only

Configure `FEISHU_BOT_WEBHOOK_URL` and leave SMTP secrets empty.

### Email And Feishu

Configure both. The monitor sends the same warning and summary content to both channels.
