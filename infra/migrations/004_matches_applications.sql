-- Faz2-3.md: matches genişletme + applications tablosu

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS matched_terms TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS estimated_amount_range TEXT;

CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    program_id UUID NOT NULL REFERENCES funding_programs(id) ON DELETE CASCADE,
    match_id UUID REFERENCES matches(id) ON DELETE SET NULL,
    state TEXT NOT NULL DEFAULT 'draft_ready',
    draft JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_applications_company_id ON applications (company_id);
CREATE INDEX IF NOT EXISTS idx_applications_match_id ON applications (match_id);
