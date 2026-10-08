-- Phase 2c: keep a random, untouched test set apart from the development labels.
ALTER TABLE gold_labels ADD COLUMN IF NOT EXISTS split TEXT NOT NULL DEFAULT 'dev';
