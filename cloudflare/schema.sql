CREATE TABLE IF NOT EXISTS managed_users (
  name TEXT PRIMARY KEY,
  budget_limit REAL NOT NULL DEFAULT 100,
  warning_threshold REAL NOT NULL DEFAULT 80,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  api_key_identity TEXT NOT NULL UNIQUE,
  user_name TEXT NOT NULL,
  sensitive_id TEXT,
  redacted_key TEXT,
  platform_created_at TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  deleted_at TEXT,
  final_cost REAL DEFAULT 0,
  final_tokens INTEGER DEFAULT 0,
  final_requests INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS usage_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  recorded_at TEXT NOT NULL,
  month INTEGER NOT NULL,
  year INTEGER NOT NULL,
  user_name TEXT NOT NULL,
  api_key TEXT,
  api_key_identity TEXT,
  cost REAL NOT NULL DEFAULT 0,
  tokens INTEGER NOT NULL DEFAULT 0,
  requests INTEGER NOT NULL DEFAULT 0,
  models_info TEXT,
  status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  user_name TEXT NOT NULL,
  api_key_identity TEXT,
  event_type TEXT NOT NULL,
  reason TEXT,
  cost REAL DEFAULT 0,
  tokens INTEGER DEFAULT 0,
  requests INTEGER DEFAULT 0,
  payload TEXT
);

CREATE INDEX IF NOT EXISTS idx_usage_user_recorded_at
ON usage_records(user_name, recorded_at);

CREATE INDEX IF NOT EXISTS idx_events_user_type_key
ON events(user_name, event_type, api_key_identity);
