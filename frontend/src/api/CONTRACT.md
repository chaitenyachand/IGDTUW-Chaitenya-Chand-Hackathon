# SENTINEL terminal – API contract

The terminal (`/app/*`) talks to a real backend only. There is no mock or sample fallback.
All screens read data through `src/api/client.ts` (TanStack Query hooks) and `src/api/ws.ts`.

## Configuration (frontend `.env`)

| Variable | Required | Example |
|---|---|---|
| `VITE_API_BASE_URL` | yes | `https://api.example.com` |
| `VITE_WS_URL` | for live push | `wss://api.example.com/ws/signals` |
| `VITE_API_TOKEN` | optional | sent as `Authorization: Bearer <token>` on POST/DELETE |

If `VITE_API_BASE_URL` is missing the terminal shows a "Backend not configured" screen.
The backend must allow CORS from the frontend origin (including the `Authorization` and `Content-Type` headers).

## Envelope and errors

```json
{ "data": {}, "meta": { "source": "live", "asOf": "2026-10-10T13:00:00Z", "nextCursor": "opaque-or-null" } }
```
* `meta.source`: `live | replay | backfill | synthetic` (drives `<ProvenanceBadge/>`).
* `meta.nextCursor` (list endpoints): opaque string. Pass it back **unchanged** as `?cursor=`. `null`/absent = last page.
* Errors: `{ "error": { "code": "not_found", "message": "No such signal" } }` with a non-2xx status.
* JSON keys camelCase, timestamps ISO 8601 UTC.

## Event types
`Geopolitical, Macroeconomic, Credit Event, Merger/Acquisition, Product Launch, Regulatory, Supply Chain, Cyber, Natural Disaster, Market Commentary, Earnings`

`Signal.impact`, `Signal.bookImpact` and `Signal.halfLifeDays` may be `null` while the impact model is not live.
The UI shows `—`, sorts nulls last and never treats null as 0.

## REST endpoints

### GET /api/signals
Query: `limit, cursor, entity, eventType (comma-separated), minImpact, sourceType (news|social), mode (live|replay|backfill)`
```json
{ "data": [ {
  "id": "sig_01", "ts": "2026-10-10T12:58:01Z", "mode": "live", "entity": "Acme Corp", "ticker": "ACME",
  "headline": "Acme misses guidance", "text": "Full text…", "sourceType": "news", "sourceName": "Reuters", "url": "https://…",
  "sentiment": -0.62, "eventType": "Earnings", "secondaryEventType": null,
  "impact": 6.4, "bookImpact": 3.1, "confidence": 0.81, "halfLifeDays": 4.5,
  "integrity": { "score": 0.78, "corroboratedBy": ["Bloomberg"], "flags": ["single_source"] },
  "explanation": [ { "token": "misses", "weight": -0.7 } ],
  "affectedHoldings": [ { "holdingId": "h_12", "estLoss": 120000 } ]
} ], "meta": { "source": "live", "asOf": "…", "nextCursor": "eyJvIjoyMH0" } }
```
### GET /api/signals/:id  → one `Signal`
### GET /api/risk-index
```json
{ "data": { "value": 54, "regime": "Elevated", "updatedAt": "…", "series": [ { "ts": "…", "value": 51 } ] }, "meta": {…} }
```
`regime`: `Calm | Elevated | Stressed`. `Stressed` shows the circuit-breaker banner.
### GET /api/precedent/:signalId
```json
{ "data": { "signalId": "sig_01", "status": "ready", "n": 14, "dateRange": { "from": "2008-01-01", "to": "2026-09-30" }, "horizonDays": 30,
  "analogs": [ { "eventId": "e1", "title": "…", "date": "2020-03-09", "similarity": 0.83, "region": "US", "maxDrawdown": -0.12, "recoveryDays": 21,
                 "paths": { "equity_index": [ { "day": 0, "ret": 0 }, { "day": 1, "ret": -0.01 } ] } } ],
  "series": { "equity_index": { "n": 14, "median": [ { "day": 0, "ret": 0 } ], "band": [ { "day": 0, "p10": 0, "p90": 0 } ] } },
  "halfLifeDays": 4.2,
  "shocks": [ { "assetClass": "equity_index", "median": -0.03, "p10": -0.07, "p90": 0.01, "n": 14 } ] }, "meta": {…} }
```
`status`: `pending` (the server later pushes WS `precedent_ready`), `ready`, `insufficient_data`.
### GET /api/index/constituents → `IndexConstituent[]`
`{ "ticker": "ACME", "name": "Acme Corp", "sector": "Industrials", "benchmarkWeight": 0.02, "currentWeight": 0.017, "sentiment": -0.3, "integrity": 0.8, "price": 41.2 }`
### GET /api/index/weights?from&to
`{ "tickers": ["ACME"], "points": [ { "ts": "…", "weights": { "ACME": 0.02 } } ] }`
### GET /api/index/rebalances → `RebalanceEvent[]`
`{ "id": "rb_1", "ts": "…", "triggerSignalId": "sig_01", "triggerHeadline": "…", "status": "pending", "moves": [ { "ticker": "ACME", "from": 0.02, "to": 0.017 } ] }`
### GET /api/index/performance
`{ "series": [ { "ts": "…", "benchmark": 100, "tilted": 100.4, "naive": 99.1 } ], "stats": { "benchmark": PerfStats, "tilted": PerfStats, "naive": PerfStats } }`
`PerfStats = { totalReturn, trackingError, turnover, maxDrawdown, informationRatio|null }`
### GET /api/index/config / POST /api/index/config
`{ "mode": "approval", "maxWeight": 0.05, "minWeight": 0.005, "maxTurnover": 0.1, "sentimentThreshold": 0.3, "requireCorroboration": true, "decay": true }`
### POST /api/index/rebalances/:id/approve | /reject → `RebalanceEvent`
### GET /api/portfolio → `Holding[]` (`meta.source` is `synthetic`)
`{ "id": "h_1", "assetType": "Loan", "counterparty": "Acme", "sector": "Industrials", "country": "US", "notional": 5000000, "marketValue": 4900000, "rating": "BBB", "maturity": "2029-06-30" }`
### GET /api/portfolio/exposure
`{ "byCountry": [ { "country": "US", "exposure": 1, "stressedLoss": 1 } ], "bySector": [ { "sector": "Energy", "exposure": 1, "stressedLoss": 1 } ], "graph": { "nodes": [ { "id": "c1", "label": "Acme", "type": "counterparty", "notional": 1 } ], "edges": [ { "source": "c1", "target": "s1", "weight": 1 } ] } }`
`country` is an ISO 3166-1 alpha-2 or alpha-3 code or a country name.
### GET /api/stress/scenarios → `Scenario[]`
`{ "id": "sc_1", "name": "Oil shock", "eventType": "Geopolitical", "description": "…", "shocks": [ { "factor": "equity", "value": -0.08, "unit": "pct" } ], "armed": true }`
Factors used by the UI sliders: `equity` (pct), `rates` (bps), `credit_spread` (bps), `fx` (pct), `commodities` (pct), `volatility` (pct).
### POST /api/stress/run
Body `{ "scenarioId"?: string, "shocks"?: ScenarioShock[], "mode": "calibrated"|"manual", "signalId"?: string }` → `StressResult`
### GET/POST /api/stress/rules, DELETE /api/stress/rules/:id
`StressRule = { id, eventType, minImpact, minIntegrity|null, scenarioId, enabled, cooldownMinutes }` (POST = upsert)
### GET /api/stress/reverse → `ReverseStressRow[]`, POST /api/stress/watchlist `{ eventType, onWatchlist }`
### GET /api/model/metrics → `ModelMetrics` (see `types.ts`)
### GET /api/health → `Health`
`{ "status": "ok", "documents": { "total": 100, "lastHour": 12, "latestPublishedAt": "…" }, "sources": [ { "name": "reuters_rss", "enabled": true, "status": "ok", "lastSuccess": "…", "lastError": null, "itemsLastRun": 10, "itemsTotal": 400, "errorCount": 0 } ], "queueLagSeconds": 1, "modelVersion": "hybrid_v1" }`
### GET /api/audit?cursor → `AuditEntry[]` (paged with `meta.nextCursor`)
### GET /api/audit/verify → `{ "intact": true, "checked": 120, "brokenAtId": null }`
### GET /api/alerts → `Alert[]`
`{ "id": "a1", "ts": "…", "severity": "warning", "title": "…", "message": "…", "signalId": null }`
### GET /api/demo/scenarios → `DemoScenario[]`; POST /api/demo/inject `{ "scenarioId": "…" }`
Replays a real archived event through the live pipeline; resulting signals have `mode: "replay"`.

## WebSocket `VITE_WS_URL`
Connect with `?since=<lastEventId>&minImpact=<n>`. Messages: `{ "type", "id", "data" }`
`hello`, `signal` (Signal), `precedent_ready` ({signalId}), `risk_index` (RiskIndex), `rebalance` (RebalanceEvent), `stress_run` (StressResult), `alert` (Alert), `ping`.
The client reconnects with exponential backoff (1s → 30s) and sends `since=<lastEventId>` so the server can replay missed events.

## Conventions the backend implements (verified by `tests/test_frontend_contract.py`)
* Shock units: `pct` values are **fractions** (`-0.15` = -15 %), `bps` values are basis points. Volatility is the relative change of the VIX.
* `GET /api/portfolio` returns the holdings array; the as-of date is in `meta.asOf`.
* `GET /api/index/config` and `POST /api/index/config` (PUT is accepted too) use `maxTurnover`, `sentimentThreshold`, `decay`; extra engine knobs ride along.
* `POST /api/stress/rules` is an upsert (client `id`); `POST /api/stress/watchlist` toggles one event type.
* `GET /api/demo/scenarios` lists archived episodes (`available` is false until `make replay-fetch EPISODE=<id>` has run); `POST /api/demo/inject {scenarioId}`.
* `GET /api/audit?cursor=` pages with `meta.nextCursor`; `GET /api/audit/verify` returns `{intact, checked, brokenAtId}`.
* `GET /api/risk-index` answers `409 insufficient_history` until enough hourly history exists (never a made-up value).
* Model metrics are `null` / empty until the job that produces them has run (`make eval-test`, `eval-calibration`, `train-impact`, `validate-precedent`, `signal-backtest`, `drift-baseline`).
