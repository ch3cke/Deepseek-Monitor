# Security Policy

## Supported Scope

Security reports are welcome for:

- DeepSeek credential handling
- GitHub Actions secret usage
- Cloudflare Worker authentication
- D1 data exposure
- Feishu and SMTP notifier handling

## Reporting A Vulnerability

Do not open public issues for vulnerabilities.

Use GitHub Security Advisories for private reporting:

- https://github.com/ch3cke/Deepseek-Monitor/security/advisories/new

When reporting, include:

- affected component
- reproduction steps
- impact assessment
- whether credentials, cookies, or tokens could leak

## Sensitive Data Rules

Never include any of the following in issues, PRs, logs, screenshots, or examples:

- DeepSeek cookies
- Bearer tokens
- SMTP credentials
- Feishu bot webhook URLs
- Feishu bot secrets
- Cloudflare ingest tokens

## Response Expectations

- reports will be reviewed privately
- fixes should prefer secret rotation guidance where appropriate
- public disclosure should happen only after a fix or mitigation is available
