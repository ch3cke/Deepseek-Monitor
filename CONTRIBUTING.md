# Contributing

## Scope

This project monitors DeepSeek platform usage, emits governance events, and stores audit data in Cloudflare D1. Contributions should preserve these core behaviors:

- monitored users are configured by `api_key.name`
- warning threshold defaults to `80`
- budget limit defaults to `100`
- over-budget keys are deleted from the DeepSeek platform
- deleted keys remain in storage and are marked as `used`

## Development Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy the local environment template:

   ```bash
   cp .env.example .env
   ```

3. Fill in real credentials only in `.env` or GitHub Actions Secrets.

## Project Structure

- `app/` contains the Python monitoring logic.
- `cloudflare/` contains the Worker API and D1 schema.
- `.github/workflows/` contains scheduled automation.
- `tests/` contains unit tests.
- `docs/` contains deployment and architecture references.

## Before Opening a Pull Request

Run:

```bash
python -m unittest discover -s tests
python -m compileall app
node --check cloudflare/worker.js
```

## Pull Request Guidelines

- Keep changes focused and explain the user-facing effect.
- Avoid committing credentials, cookies, tokens, or webhook URLs.
- Update `README.md` and `docs/` when changing workflows, interfaces, or required secrets.
- Add or update tests when changing aggregation, event generation, or notifier behavior.

## Security Notes

- Never include real DeepSeek cookies, SMTP credentials, or Feishu bot secrets in issues, PRs, or logs.
- Prefer mocked tests for external integrations.
