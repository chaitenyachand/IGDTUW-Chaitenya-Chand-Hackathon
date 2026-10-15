-- Phase 5: replay-aware state, risk-index history and stored model runs.
-- `source` separates live state from replay (demo) state so a replayed 2023 episode never pollutes the live book of signals.
ALTER TABLE rebalance_events ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'live';
ALTER TABLE alerts           ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'live';
ALTER TABLE stress_runs      ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'live';

ALTER TABLE index_weights DROP CONSTRAINT IF EXISTS index_weights_pkey;
ALTER TABLE index_weights ADD PRIMARY KEY (source, ts);

CREATE TABLE IF NOT EXISTS risk_index_history (
  ts        TIMESTAMPTZ NOT NULL,
  source    TEXT NOT NULL DEFAULT 'live',
  raw       DOUBLE PRECISION NOT NULL,
  value     DOUBLE PRECISION,                      -- NULL while the trailing baseline is too short to rank against
  regime    TEXT,
  n_signals INT NOT NULL DEFAULT 0,
  PRIMARY KEY (source, ts)
);

CREATE TABLE IF NOT EXISTS model_runs (
  id            BIGSERIAL PRIMARY KEY,
  kind          TEXT NOT NULL,                     -- impact | precedent_validation | signal_backtest | drift_baseline ...
  ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
  model_version TEXT,
  metrics       JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS model_runs_kind_idx ON model_runs (kind, ts DESC);

CREATE INDEX IF NOT EXISTS signals_event_idx ON signals (event_type, ts DESC);
CREATE INDEX IF NOT EXISTS signals_ticker_idx ON signals (ticker, ts DESC) WHERE ticker IS NOT NULL;
