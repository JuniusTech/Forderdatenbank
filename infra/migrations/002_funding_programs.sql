-- Culinary Funding OS — Faz 1b XML ingest tables

CREATE TABLE IF NOT EXISTS funding_programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id TEXT UNIQUE NOT NULL,
    source_path TEXT NOT NULL,
    title TEXT NOT NULL,
    funding_type TEXT[] NOT NULL DEFAULT '{}',
    provider_name TEXT,
    region TEXT,
    target_groups TEXT[] NOT NULL DEFAULT '{}',
    eligible_costs TEXT[] NOT NULL DEFAULT '{}',
    company_sizes TEXT[] NOT NULL DEFAULT '{}',
    external_links JSONB NOT NULL DEFAULT '[]'::jsonb,
    application_url TEXT,
    contact JSONB,
    raw_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    date_of_issue TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    license_attribution TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_funding_programs_region ON funding_programs (region);
CREATE INDEX IF NOT EXISTS idx_funding_programs_status ON funding_programs (status);
CREATE INDEX IF NOT EXISTS idx_funding_programs_last_synced_at ON funding_programs (last_synced_at DESC);
CREATE INDEX IF NOT EXISTS idx_funding_programs_funding_type ON funding_programs USING GIN (funding_type);

CREATE TABLE IF NOT EXISTS xml_ingest_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_root TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    programs_processed INT NOT NULL DEFAULT 0,
    new_count INT NOT NULL DEFAULT 0,
    updated_count INT NOT NULL DEFAULT 0,
    skipped_count INT NOT NULL DEFAULT 0,
    error_count INT NOT NULL DEFAULT 0,
    errors JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_xml_ingest_runs_started_at ON xml_ingest_runs (started_at DESC);
