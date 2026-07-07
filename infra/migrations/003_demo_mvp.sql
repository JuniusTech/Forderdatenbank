-- Culinary Funding OS — MVP demo tables

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    region TEXT NOT NULL,
    sector TEXT,
    employees INT,
    company_size TEXT,
    investment_need TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    program_id UUID NOT NULL REFERENCES funding_programs(id) ON DELETE CASCADE,
    score NUMERIC(5,2) NOT NULL,
    score_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    human_review_required BOOLEAN NOT NULL DEFAULT TRUE,
    disclaimer TEXT NOT NULL DEFAULT 'Nihai karar ilgili kuruma aittir.',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, program_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_company_id ON matches (company_id);
CREATE INDEX IF NOT EXISTS idx_matches_score ON matches (score DESC);
