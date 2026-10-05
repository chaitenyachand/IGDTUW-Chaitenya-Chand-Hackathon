-- Phase 2a: per-document NLP features (relevance gate, entities, weak event label).
CREATE TABLE IF NOT EXISTS schema_migrations (
  filename   TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS doc_features (
  document_id       TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  clean_title       TEXT NOT NULL,
  entities          JSONB NOT NULL DEFAULT '[]'::jsonb,
  relevance         REAL NOT NULL,
  relevant          BOOLEAN NOT NULL,
  weak_event        TEXT,
  weak_event_scores JSONB NOT NULL DEFAULT '{}'::jsonb,
  features          JSONB NOT NULL DEFAULT '{}'::jsonb,
  pipeline_version  TEXT NOT NULL,
  processed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS doc_features_relevant_idx ON doc_features (relevant, processed_at DESC);