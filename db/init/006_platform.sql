-- Phase 4: SEC event history, PRECEDENT library, portfolio, index, stress, alerts and the audit ledger.
ALTER TABLE signals ADD COLUMN IF NOT EXISTS impact_basis TEXT;

CREATE TABLE IF NOT EXISTS corporate_events (
  id TEXT PRIMARY KEY,                           -- SEC accession number
  ticker TEXT NOT NULL, filed_at TIMESTAMPTZ NOT NULL, form TEXT NOT NULL,
  items TEXT[] NOT NULL DEFAULT '{}', event_type TEXT NOT NULL,
  t0 DATE, car3 DOUBLE PRECISION, abs_car3 DOUBLE PRECISION, ar1 DOUBLE PRECISION, beta DOUBLE PRECISION,
  vol60 DOUBLE PRECISION, prior_abs DOUBLE PRECISION, vix_prev DOUBLE PRECISION, labeled_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS corporate_events_ticker_idx ON corporate_events (ticker, filed_at);

CREATE TABLE IF NOT EXISTS event_library (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL, event_date DATE NOT NULL, reaction_date DATE NOT NULL,
  event_type TEXT NOT NULL, region TEXT, vix_level DOUBLE PRECISION, embedding REAL[]
);
CREATE TABLE IF NOT EXISTS event_outcomes (
  event_id TEXT NOT NULL REFERENCES event_library(id) ON DELETE CASCADE, asset_key TEXT NOT NULL,
  path JSONB NOT NULL, max_drawdown DOUBLE PRECISION, recovery_days INT, PRIMARY KEY (event_id, asset_key)
);

CREATE TABLE IF NOT EXISTS portfolio_holdings (
  id TEXT PRIMARY KEY, asset_type TEXT NOT NULL, counterparty TEXT NOT NULL, ticker TEXT, sector TEXT NOT NULL,
  country TEXT NOT NULL, notional DOUBLE PRECISION NOT NULL, rating TEXT, maturity DATE NOT NULL, terms JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS index_weights (
  ts TIMESTAMPTZ PRIMARY KEY, weights JSONB NOT NULL, source TEXT NOT NULL DEFAULT 'live'
);
CREATE TABLE IF NOT EXISTS rebalance_events (
  id TEXT PRIMARY KEY, ts TIMESTAMPTZ NOT NULL, trigger_signal_id TEXT, trigger_headline TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('applied','pending','rejected')), moves JSONB NOT NULL, decided_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS stress_rules (
  id TEXT PRIMARY KEY, event_type TEXT NOT NULL, min_impact DOUBLE PRECISION NOT NULL, min_integrity DOUBLE PRECISION,
  scenario_id TEXT NOT NULL, enabled BOOLEAN NOT NULL DEFAULT TRUE, cooldown_minutes INT NOT NULL DEFAULT 60,
  last_fired TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS stress_runs (
  id TEXT PRIMARY KEY, ts TIMESTAMPTZ NOT NULL, scenario_id TEXT, mode TEXT NOT NULL,
  triggered_by_signal_id TEXT, result JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS stress_runs_ts_idx ON stress_runs (ts DESC);
CREATE TABLE IF NOT EXISTS stress_watchlist (event_type TEXT PRIMARY KEY, added_at TIMESTAMPTZ NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY, ts TIMESTAMPTZ NOT NULL, severity TEXT NOT NULL, title TEXT NOT NULL, message TEXT NOT NULL,
  signal_id TEXT
);
CREATE INDEX IF NOT EXISTS alerts_ts_idx ON alerts (ts DESC);

CREATE TABLE IF NOT EXISTS audit_log (
  seq BIGSERIAL PRIMARY KEY, id TEXT UNIQUE NOT NULL, ts TIMESTAMPTZ NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, summary TEXT NOT NULL, payload JSONB NOT NULL, hash TEXT NOT NULL, prev_hash TEXT
);
CREATE OR REPLACE FUNCTION audit_immutable() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_log is append-only'; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS audit_no_change ON audit_log;
CREATE TRIGGER audit_no_change BEFORE UPDATE OR DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION audit_immutable();
