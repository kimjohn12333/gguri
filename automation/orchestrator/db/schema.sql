PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS queue_items (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  priority TEXT NOT NULL,
  task TEXT NOT NULL,
  success_criteria TEXT NOT NULL,
  owner_session TEXT NOT NULL DEFAULT '-',
  started_at_kst TEXT NOT NULL DEFAULT '-',
  due_at_kst TEXT NOT NULL DEFAULT '-',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  lease_owner TEXT,
  lease_expires_at INTEGER,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  idempotency_key TEXT,
  last_error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS queue_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (item_id) REFERENCES queue_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_queue_items_status_priority
  ON queue_items(status, priority);

CREATE INDEX IF NOT EXISTS idx_queue_items_updated_at
  ON queue_items(updated_at);

CREATE INDEX IF NOT EXISTS idx_queue_items_lease
  ON queue_items(lease_expires_at);

CREATE INDEX IF NOT EXISTS idx_queue_items_idempotency
  ON queue_items(idempotency_key);