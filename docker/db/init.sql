-- EcomReview AI - PostgreSQL 16 Schema (6 Core Tables + Audit Log + Read-Only Role)

-- 1. Customer reviews (PII-scrubbed)
CREATE TABLE IF NOT EXISTS reviews (
    review_id         TEXT NOT NULL,
    scenario_tag      TEXT NOT NULL DEFAULT 'real_shop',
    platform          TEXT NOT NULL DEFAULT 'tiktok',
    shop              TEXT NOT NULL DEFAULT 'shop_a',
    product           TEXT NOT NULL DEFAULT 'ao_mua_da_ca',
    rating            INTEGER CHECK (rating BETWEEN 1 AND 5),
    text_raw          TEXT NOT NULL,
    text_norm         TEXT NOT NULL,
    source            TEXT NOT NULL DEFAULT 'review',
    overall_sentiment TEXT,
    informative       INTEGER DEFAULT 1,
    created_at        TEXT,
    imported_at       TEXT,
    PRIMARY KEY (review_id, scenario_tag)
);

-- 2. Aspect-based sentiment opinions (ABSA extraction)
CREATE TABLE IF NOT EXISTS opinions (
    id                BIGSERIAL PRIMARY KEY,
    review_id         TEXT NOT NULL,
    scenario_tag      TEXT NOT NULL DEFAULT 'real_shop',
    aspect            TEXT NOT NULL,
    polarity          TEXT NOT NULL,
    evidence          TEXT NOT NULL,
    evidence_ok       INTEGER NOT NULL DEFAULT 1,
    analyzer_method   TEXT NOT NULL DEFAULT 'gemini_v2',
    created_at        TEXT,
    FOREIGN KEY (review_id, scenario_tag) REFERENCES reviews(review_id, scenario_tag) ON DELETE CASCADE
);

-- 3. Numerically verified statistical insights
CREATE TABLE IF NOT EXISTS insights (
    id                SERIAL PRIMARY KEY,
    scenario_tag      TEXT NOT NULL DEFAULT 'real_shop',
    kind              TEXT NOT NULL,
    aspect            TEXT,
    statement         TEXT NOT NULL,
    numbers           TEXT NOT NULL,
    evidence_ids      TEXT NOT NULL,
    confidence        TEXT NOT NULL,
    created_at        TEXT
);

-- 4. Action proposals (Marketing & Operations) verified by Hybrid Critic
CREATE TABLE IF NOT EXISTS actions (
    id                  SERIAL PRIMARY KEY,
    scenario_tag        TEXT NOT NULL DEFAULT 'real_shop',
    action_type         TEXT NOT NULL,
    is_marketing        INTEGER NOT NULL DEFAULT 1,
    title               TEXT NOT NULL,
    what_to_do          TEXT NOT NULL,
    why_rationale       TEXT NOT NULL,
    how_and_when        TEXT NOT NULL,
    success_metric      TEXT NOT NULL,
    effort              TEXT NOT NULL,
    impact              TEXT NOT NULL,
    priority_score      REAL NOT NULL DEFAULT 0.0,
    insight_ids         TEXT NOT NULL,
    evidence_review_ids TEXT NOT NULL,
    critic_passed       INTEGER NOT NULL DEFAULT 1,
    critic_trace        TEXT,
    status              TEXT NOT NULL DEFAULT 'proposed',
    created_at          TEXT
);

-- 5. Human-in-the-loop shop owner decision feedback
CREATE TABLE IF NOT EXISTS action_feedback (
    id                SERIAL PRIMARY KEY,
    action_id         INTEGER NOT NULL REFERENCES actions(id) ON DELETE CASCADE,
    decision          TEXT NOT NULL,
    reason_category   TEXT,
    note              TEXT,
    edited_content    TEXT,
    decided_by        TEXT,
    decided_at        TEXT
);

-- 6. System background jobs & audit log
CREATE TABLE IF NOT EXISTS system_jobs_audit (
    id                SERIAL PRIMARY KEY,
    job_type          TEXT NOT NULL,
    status            TEXT NOT NULL,
    details           TEXT,
    created_at        TEXT,
    completed_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_reviews_scenario ON reviews(scenario_tag, platform);
CREATE INDEX IF NOT EXISTS idx_opinions_aspect_pol ON opinions(scenario_tag, aspect, polarity);
CREATE INDEX IF NOT EXISTS idx_actions_scenario_status ON actions(scenario_tag, status);

-- Read-Only Role for Agent Security Layer 4
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ecom_agent_ro') THEN
        CREATE ROLE ecom_agent_ro WITH LOGIN PASSWORD 'agent_readonly_pass';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE ecomreview TO ecom_agent_ro;
GRANT USAGE ON SCHEMA public TO ecom_agent_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ecom_agent_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ecom_agent_ro;

-- CreBy: MenBoyBMN
