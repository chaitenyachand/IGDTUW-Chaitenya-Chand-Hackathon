.PHONY: edgar label-events train-impact library portfolio caps risk-backfill index-backfill validate-precedent signal-backtest drift-baseline eval-calibration replay-fetch replay-inject replay-reset audit-verify scheduler bootstrap up down logs eval-test train-final serve serve-logs labels labels-random import-labels import-test-labels eval-gate train-baseline eval-transformers migrate seed prices fred check test api ingest
up:        ## start db + redis + api + ingest
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f ingest nlp api
labels:    ## write a stratified headline sample to data/labeling/sample_300.txt
	docker compose run --rm api python -m sentinel.cli labels-sample
import-labels: ## load data/labeling/gold_labels.csv into the database
	docker compose run --rm api python -m sentinel.cli import-labels
eval-gate: ## score the relevance gate against the gold labels
	docker compose run --rm api python -m sentinel.cli eval-gate
train-baseline: ## cross-validated TF-IDF classifiers vs the rules, on the gold labels
	docker compose run --rm api python -m sentinel.cli train-baseline
eval-transformers: ## MiniLM embeddings + FinBERT on the gold labels (builds the ml image once)
	docker compose --profile ml run --rm --build ml python -m sentinel.cli eval-transformers
labels-random: ## write a uniform random sample (held-out test set) to data/labeling/random_150.txt
	docker compose run --rm api python -m sentinel.cli labels-sample-random
import-test-labels: ## load data/labeling/test_labels.csv as the held-out test split
	docker compose run --rm -e GOLD_FILE=data/labeling/test_labels.csv -e GOLD_SPLIT=test api python -m sentinel.cli import-labels
train-final: ## train the frozen production models and save models/hybrid_v1.joblib
	docker compose --profile ml run --rm --build ml python -m sentinel.cli train-final
serve:     ## start the model-serving worker (writes live signals)
	docker compose --profile ml up -d --build serve
serve-logs:
	docker compose --profile ml logs -f serve
eval-test: ## ONE-SHOT: score the frozen pipeline on the held-out test split
	docker compose --profile ml run --rm --build ml python -m sentinel.cli eval-test
migrate:   ## apply new database migrations
	docker compose run --rm api python -m sentinel.cli migrate
seed:      ## load the 15-stock universe
	docker compose run --rm api python -m sentinel.cli seed
prices:    ## download price history (yfinance)
	docker compose run --rm api python -m sentinel.cli sync-prices
fred:      ## download macro series (needs FRED_API_KEY)
	docker compose run --rm api python -m sentinel.cli sync-fred
check:     ## ping every data source and report status
	docker compose run --rm api python -m sentinel.cli check-sources
test:
	docker compose run --rm api python -m pytest -q

# ---- Phases 4-8: SEC history, PRECEDENT, portfolio, Module A/B, risk index, audit, demo ----
edgar:     ## SEC 8-K history of the 15 stocks + real abnormal-return labels (needs SEC_USER_AGENT)
	docker compose run --rm api python -m sentinel.cli edgar-backfill
label-events: ## label any unlabelled 8-K filings with their abnormal returns
	docker compose run --rm api python -m sentinel.cli label-events
train-impact: ## train the company-event impact model -> models/impact_v1.joblib
	docker compose run --rm api python -m sentinel.cli train-impact
library:   ## build the PRECEDENT event library with real forward market paths (ml image)
	docker compose --profile ml run --rm --build ml python -m sentinel.cli build-library
portfolio: ## generate the seeded synthetic wholesale book + default stress rules
	docker compose run --rm api python -m sentinel.cli portfolio
caps:      ## market-cap benchmark weights for the Adaptive Index
	docker compose run --rm api python -m sentinel.cli sync-caps
risk-backfill: ## compute the hourly Global Risk Index over the archived signals
	docker compose run --rm api python -m sentinel.cli risk-backfill
index-backfill: ## replay archived signals through Module A (stored as source=backfill)
	docker compose run --rm api python -m sentinel.cli index-backfill
validate-precedent: ## leave-one-out, point-in-time validation of PRECEDENT
	docker compose run --rm api python -m sentinel.cli validate-precedent
signal-backtest: ## do high-sentiment signals precede higher abnormal returns?
	docker compose run --rm api python -m sentinel.cli signal-backtest
drift-baseline: ## snapshot signal feature distributions for drift (PSI) monitoring
	docker compose run --rm api python -m sentinel.cli drift-baseline
eval-calibration: ## reliability curves and ECE of the frozen pipeline (after eval-test)
	docker compose --profile ml run --rm --build ml python -m sentinel.cli eval-calibration
replay-fetch: ## download a real archived episode: make replay-fetch EPISODE=svb-2023-03
	docker compose run --rm api python -m sentinel.cli replay-fetch --episode $(EPISODE)
replay-inject: ## queue an episode for replay (serve worker must be running)
	docker compose run --rm api python -m sentinel.cli replay-inject --episode $(EPISODE)
replay-reset: ## remove all replay documents, signals and replay state
	docker compose run --rm api python -m sentinel.cli replay-reset
audit-verify: ## recompute the audit hash chain
	docker compose run --rm api python -m sentinel.cli audit-verify
scheduler: ## start the scheduler service (risk index, index decay, daily refreshes)
	docker compose up -d --build scheduler
bootstrap: migrate seed prices fred edgar train-impact library portfolio ## everything needed on a fresh machine (then: make train-final serve scheduler)
