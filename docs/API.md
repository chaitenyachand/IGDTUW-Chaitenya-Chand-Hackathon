# SENTINEL backend API

Base: `/api`. Every success is `{"data": ..., "meta": {"source": "live|replay|backfill|synthetic", "asOf": ISO8601}}`;
every error is `{"error": {"code": "...", "message": "..."}}`. Fields are camelCase. Lists use opaque `cursor` pagination.
Write endpoints (POST/PUT/DELETE) need `Authorization: Bearer $API_TOKEN` (open when `API_TOKEN` is empty) and a stricter rate limit
(`WRITE_RATE_LIMIT_PER_MINUTE`, default 60; reads `RATE_LIMIT_PER_MINUTE`, default 600). Cacheable GETs return `ETag` and honour `If-None-Match` (304).

| Area | Endpoints |
|---|---|
| Signals | `GET /signals` (filters, `mode=replay` to see replay), `GET /signals/{id}`, `GET /documents` |
| PRECEDENT | `GET /precedent/{signalId}` (analogs, forward-return bands, low-n flag and shrinkage) |
| Risk | `GET /risk-index`, `GET /alerts` |
| Index | `GET /index/constituents|weights|rebalances|performance|config`, `PUT /index/config`, `POST /index/recompute`, `POST /index/rebalances/{id}/approve|reject` |
| Portfolio | `GET /portfolio`, `GET /portfolio/exposure` |
| Stress | `GET /stress/scenarios|runs|runs/{id}|runs/{id}/brief (PDF)|reverse|rules|watchlist`, `POST /stress/run`, `POST|PUT|DELETE /stress/rules`, `PUT /stress/watchlist` |
| Model | `GET /model/metrics` |
| Audit | `GET /audit`, `GET /audit/verify` |
| Demo | `GET /demo/episodes|status`, `POST /demo/inject|reset` |
| Health | `GET /health` |

## WebSocket
`/ws/signals?since=<streamId>&minImpact=<n>&source=all|live|replay`. Replays missed messages from `since`, then streams live.
Message types: `signal`, `precedent_ready`, `risk_index`, `rebalance`, `stress_run`, `alert`; server ping every 20 s.

## Demo replay
Episodes in `data/replay/episodes.yaml` are real archived periods. `make replay-fetch EPISODE=<id>` samples the GDELT GKG archive
(DOC API only reaches about 3 months back). `POST /demo/inject` queues them with `mode='replay'`; each is processed as of its own
timestamp, and derived state is tagged `source='replay'` so live state is untouched. `POST /demo/reset` removes replay state only;
the audit ledger is append-only and keeps its entries.

## Assumptions
- Rating migration matrix (`stress/credit.py`) is illustrative, not agency data; LGD 45% loans, 60% bonds.
- Index: tilt `w = bench * exp(kappa * z)`, position caps, deadband, turnover cap, transaction cost per config.
- Shock horizons and calibrated shocks come from PRECEDENT forward returns; low-sample analogs are shrunk.
- The worst-shock solver is gradient-based (not SciPy SLSQP).
- Risk Index: percentile of the 6 h decayed raw sum against the trailing 90 days of hourly values.

## Environment
`DATABASE_URL`, `REDIS_URL`, `API_TOKEN`, `RATE_LIMIT_PER_MINUTE`, `WRITE_RATE_LIMIT_PER_MINUTE`, `AUDIT_MIN_IMPACT` (7.0), `REPLAY_PACE_SECONDS` (1.0), `SEC_USER_AGENT`, `FRED_API_KEY`.

## Frontend contract (SENTINEL terminal)
Response shapes match `frontend/src/api/types.ts` exactly; `tests/test_frontend_contract.py` checks every endpoint and WebSocket message against those types.
Differences from the first version of this document: portfolio/constituents/rebalances/reverse stress/alerts are plain arrays; shocks use `pct` as fractions;
`POST /index/config`, `POST /stress/rules` (upsert), `POST /stress/watchlist {eventType,onWatchlist}`, `GET /demo/scenarios`, `GET /stress/worst-shock`;
audit pages with `meta.nextCursor`; `/risk-index` is 409 until history exists. See `frontend/src/api/CONTRACT.md`.
