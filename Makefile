.PHONY: up down logs seed prices fred check test api ingest
up:        ## start db + redis + api + ingest
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f ingest api
seed:      ## load the 15-stock universe
	docker compose run --rm api python -m sentinel.cli seed
prices:    ## download price history (yfinance)
	docker compose run --rm api python -m sentinel.cli sync-prices
fred:      ## download macro series (needs FRED_API_KEY)
	docker compose run --rm api python -m sentinel.cli sync-fred
check:     ## ping every data source and report status
	docker compose run --rm api python -m sentinel.cli check-sources
test:
	PYTHONPATH=src pytest -q
