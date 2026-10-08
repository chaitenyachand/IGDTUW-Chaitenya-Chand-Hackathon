-- Phase 3a: model scores for every document, and the signals the API serves.
CREATE TABLE IF NOT EXISTS doc_scores (
  document_id   TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  relevance_p   REAL NOT NULL,
  relevant      BOOLEAN NOT NULL,
  event_pred    TEXT,
  event_proba   JSONB NOT NULL DEFAULT '{}'::jsonb,
  model_version TEXT NOT NULL,
  scored_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS doc_scores_version_idx ON doc_scores (model_version);

CREATE TABLE IF NOT EXISTS signals (
  id                   TEXT PRIMARY KEY,            -- equals documents.id
  document_id          TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ts                   TIMESTAMPTZ NOT NULL,
  mode                 TEXT NOT NULL DEFAULT 'live',
  entity               TEXT NOT NULL,
  ticker               TEXT,
  entities             JSONB NOT NULL DEFAULT '[]'::jsonb,
  headline             TEXT NOT NULL,
  text                 TEXT NOT NULL,
  source_type          TEXT NOT NULL,
  source_name          TEXT NOT NULL,
  url                  TEXT,
  sentiment            DOUBLE PRECISION NOT NULL,
  sentiment_probs      JSONB NOT NULL DEFAULT '{}'::jsonb,
  event_type           TEXT NOT NULL,
  secondary_event_type TEXT,
  impact               DOUBLE PRECISION,                        -- filled by the impact model (later phase)
  book_impact          DOUBLE PRECISION,
  confidence           DOUBLE PRECISION NOT NULL,
  half_life_days       DOUBLE PRECISION,
  integrity            JSONB NOT NULL,
  explanation          JSONB NOT NULL DEFAULT '[]'::jsonb,
  affected_holdings    JSONB NOT NULL DEFAULT '[]'::jsonb,
  embedding            REAL[],
  model_version        TEXT NOT NULL,
  scored_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS signals_ts_idx ON signals (ts DESC, id DESC);
CREATE INDEX IF NOT EXISTS signals_entity_idx ON signals (entity, ts DESC);
