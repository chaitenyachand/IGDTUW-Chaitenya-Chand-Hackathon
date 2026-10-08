.PHONY: up down logs train-final serve serve-logs labels labels-random import-labels import-test-labels eval-gate train-baseline eval-transformers migrate seed prices fred check test api ingest
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
