# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows semantic versioning in spirit, even if releases are currently lightweight.

## [Unreleased]

### Added

- package-style Python app layout under `app/`
- Cloudflare Worker REST query endpoints for users, usage, events, API keys, and summary
- Feishu custom bot notifications with `text`, `post`, and `interactive` message modes
- optional Feishu keyword prefix and webhook signature fields
- `.env.example` for local setup
- open-source repository files: `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, issue templates, PR template, and docs
- architecture and deployment documentation under `docs/`

### Changed

- monitor workflow now runs with `python -m app.main monitor`
- summary workflow now runs with `python -m app.main summary`
- email notifications are now optional instead of mandatory
- D1 storage is exposed as a clearer authenticated REST interface

### Fixed

- multi-key usage aggregation no longer overwrites earlier keys for the same monitored user
- deleted API keys remain stored as `used` instead of disappearing from audit history
- warning deduplication is scoped by billing period and active key scope
