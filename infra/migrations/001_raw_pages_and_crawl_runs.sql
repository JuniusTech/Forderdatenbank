-- Culinary Funding OS — Faz 1 crawler tables

CREATE TABLE IF NOT EXISTS raw_pages (
    url TEXT PRIMARY KEY,
    raw_html TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_valid_until DATE
);

CREATE INDEX IF NOT EXISTS idx_raw_pages_content_hash ON raw_pages (content_hash);
CREATE INDEX IF NOT EXISTS idx_raw_pages_last_synced_at ON raw_pages (last_synced_at);

CREATE TABLE IF NOT EXISTS crawl_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    pages_checked INT NOT NULL DEFAULT 0,
    new_count INT NOT NULL DEFAULT 0,
    changed_count INT NOT NULL DEFAULT 0,
    skipped_count INT NOT NULL DEFAULT 0,
    stopped_early_at_page INT,
    total_hits INT,
    errors JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_crawl_runs_started_at ON crawl_runs (started_at DESC);
