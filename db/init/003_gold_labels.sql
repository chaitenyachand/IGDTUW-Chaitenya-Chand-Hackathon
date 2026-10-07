-- Phase 2b: hand-checked gold labels (evaluation + training data for the learned models).
CREATE TABLE IF NOT EXISTS gold_labels (
  document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  relevant    BOOLEAN NOT NULL,
  event_type  TEXT NOT NULL,
  sentiment   SMALLINT,
  labeler     TEXT NOT NULL DEFAULT 'claude-assisted',
  labeled_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
