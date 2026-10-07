.PHONY: up down logs labels import-labels eval-gate migrate seed prices fred check test api ingest
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
