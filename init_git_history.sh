#!/usr/bin/env bash
# Creates a clean git history for the Phase 1 code as logical, incremental commits.
# Run from INSIDE the repo folder (the one containing README.md). Uses YOUR git identity.
# Note: commits get today's real timestamps. Do not backdate; from now on, commit after every piece of work.
set -euo pipefail

[ -f README.md ] && [ -d src/sentinel ] || { echo "Run this from the repo root (README.md and src/sentinel must exist)."; exit 1; }
if [ -d .git ]; then echo ".git already exists. Remove it first if you want to rebuild history."; exit 1; fi
git config user.name  >/dev/null || { echo "Set your identity first: git config --global user.name 'Your Name'"; exit 1; }
git config user.email >/dev/null || { echo "Set your identity first: git config --global user.email 'you@college.ac.in'"; exit 1; }

git init -q -b main

c() { msg="$1"; shift; git add -- "$@"; git commit -q -m "$msg"; echo "committed: $msg"; }

c "chore: project skeleton, tooling and Docker setup" \
  .gitignore LICENSE README.md requirements.txt pytest.ini Dockerfile docker-compose.yml Makefile .env.example data/.gitkeep docs/.gitkeep
c "feat(db): core Postgres schema for documents, source health, prices and macro series" db/init/001_core.sql
c "feat: typed settings and sector-balanced 15-stock S&P 100 universe" \
  src/sentinel/__init__.py src/sentinel/config.py src/sentinel/universe.py
c "feat(ingest): common document model, text normalization and SimHash near-duplicate index" \
  src/sentinel/ingest/__init__.py src/sentinel/ingest/base.py src/sentinel/ingest/dedupe.py tests/test_base_dedupe.py
c "feat(store): dedupe-aware inserts, source health tracking and config store" src/sentinel/store.py
c "feat(ingest): GDELT GKG connector with finance-theme filtering" src/sentinel/ingest/gdelt.py tests/test_gdelt.py
c "feat(ingest): RSS connector with conditional GET and SEC EDGAR 8-K connector" \
  src/sentinel/ingest/rss.py src/sentinel/ingest/edgar.py config/feeds.yaml tests/test_edgar_rss.py
c "feat(market): yfinance price history and FRED macro series loaders" \
  src/sentinel/market/__init__.py src/sentinel/market/prices.py src/sentinel/market/fred.py
c "feat(ingest): Bluesky Jetstream and Reddit social connectors" \
  src/sentinel/ingest/bluesky.py src/sentinel/ingest/reddit.py tests/test_social_fred.py
c "feat(ingest): ingestion runner with Redis Streams publishing and per-source health" src/sentinel/ingest/runner.py
c "feat: operational CLI (seed, sync, check-sources) and health/documents API" \
  src/sentinel/cli.py src/sentinel/tools/__init__.py src/sentinel/api/__init__.py src/sentinel/api/main.py
c "test: Postgres integration test for dedupe, idempotency and source health" tests/test_integration_db.py

if [ -n "$(git status --porcelain)" ]; then
  git add -A && git commit -q -m "chore: remaining project files" && echo "committed: remaining files"
fi
echo; git log --oneline
