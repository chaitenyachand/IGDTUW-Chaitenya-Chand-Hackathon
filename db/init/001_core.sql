-- SENTINEL core schema (phase 0/1). Later phases add signals, event library, portfolio, audit tables.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  id            TEXT PRIMARY KEY,
  source_type   TEXT NOT NULL CHECK (source_type IN ('news','social')),
  source_name   TEXT NOT NULL,
  mode          TEXT NOT NULL DEFAULT 'live' CHECK (mode IN ('live','replay','backfill')),
  url           TEXT,
  canonical_url TEXT,
  published_at  TIMESTAMPTZ NOT NULL,
  ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  language      TEXT,
  title         TEXT,
  text          TEXT NOT NULL,
  author        TEXT,
  raw_hash      TEXT NOT NULL,
  simhash       BIGINT,
  dup_of        TEXT REFERENCES documents(id),
  meta          JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS documents_published_idx ON documents (published_at DESC);
CREATE INDEX IF NOT EXISTS documents_source_idx ON documents (source_name, published_at DESC);
CREATE INDEX IF NOT EXISTS documents_dup_idx ON documents (dup_of) WHERE dup_of IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS documents_canonical_url_uq
  ON documents (canonical_url) WHERE canonical_url IS NOT NULL;

CREATE TABLE IF NOT EXISTS source_health (
  source_name    TEXT PRIMARY KEY,
  enabled        BOOLEAN NOT NULL DEFAULT TRUE,
  status         TEXT NOT NULL DEFAULT 'starting',
  last_success   TIMESTAMPTZ,
  last_error     TIMESTAMPTZ,
  last_error_msg TEXT,
  items_last_run INT NOT NULL DEFAULT 0,
  items_total    BIGINT NOT NULL DEFAULT 0,
  error_count    BIGINT NOT NULL DEFAULT 0,
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entities (
  ticker  TEXT PRIMARY KEY,
  name    TEXT NOT NULL,
  sector  TEXT NOT NULL,
  country TEXT NOT NULL DEFAULT 'US',
  cik     TEXT,
  aliases TEXT[] NOT NULL DEFAULT '{}',
  in_index BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS prices (
  symbol    TEXT NOT NULL,
  ts        TIMESTAMPTZ NOT NULL,
  open      DOUBLE PRECISION,
  high      DOUBLE PRECISION,
  low       DOUBLE PRECISION,
  close     DOUBLE PRECISION NOT NULL,
  adj_close DOUBLE PRECISION,
  volume    BIGINT,
  PRIMARY KEY (symbol, ts)
);

CREATE TABLE IF NOT EXISTS macro_series (
  series_id TEXT NOT NULL,
  ts        TIMESTAMPTZ NOT NULL,
  value     DOUBLE PRECISION NOT NULL,
  PRIMARY KEY (series_id, ts)
);

CREATE TABLE IF NOT EXISTS app_config (
  key        TEXT PRIMARY KEY,
  value      JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
