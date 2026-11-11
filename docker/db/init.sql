-- EcomReview AI - PostgreSQL 16 Schema (6 Core Tables + Audit Log)

-- 1. Customer reviews (PII-scrubbed)
CREATE TABLE IF NOT EXISTS reviews (
    review_id         TEXT NOT NULL,
    scenario_tag      TEXT NOT NULL DEFAULT 'real_shop',
    platform          TEXT NOT NULL,              -- 'shopee' | 'tiktok'
    shop              TEXT NOT NULL DEFAULT 'shop_a',
    product           TEXT NOT NULL DEFAULT 'ao_mua_da_ca',
    rating            SMALLINT CHECK (rating BETWEEN 1 AND 5),
    text_raw          TEXT NOT NULL,
    text_norm         TEXT NOT NULL,
    source            TEXT NOT NULL DEFAULT 'review', -- 'review' | 'comment' | 'chat'
    overall_sentiment TEXT,                       -- 'positive' | 'negative' | 'neutral'
    informative       BOOLEAN DEFAULT TRUE,
    created_at        DATE,
    imported_at       TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (review_id, scenario_tag)
);

-- 2. Aspect-based sentiment opinions (ABSA extraction)
CREATE TABLE IF NOT EXISTS opinions (
    id                BIGSERIAL PRIMARY KEY,
    review_id         TEXT NOT NULL,
    scenario_tag      TEXT NOT NULL DEFAULT 'real_shop',
    aspect            TEXT NOT NULL,              -- 8 domain aspects + 'GENERAL'
    polarity          TEXT NOT NULL,              -- 'positive' | 'negative' | 'neutral'
    evidence          TEXT NOT NULL,
    evidence_ok       BOOLEAN NOT NULL DEFAULT TRUE,
    analyzer_method   TEXT NOT NULL DEFAULT 'gemini_v2',
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (review_id, scenario_tag) REFERENCES reviews(review_id, scenario_tag) ON DELETE CASCADE
);

-- 3. Numerically verified statistical insights
CREATE TABLE IF NOT EXISTS insights (
    id                SERIAL PRIMARY KEY,
    scenario_tag      TEXT NOT NULL DEFAULT 'real_shop',
    kind              TEXT NOT NULL,              -- 'TOP_PAIN' | 'STRENGTH' | 'HIDDEN_COMPLAINT' | 'PLATFORM_GAP' | 'EMERGING_ISSUE'
    aspect            TEXT,
    statement         TEXT NOT NULL,
    numbers           JSONB NOT NULL,
    evidence_ids      TEXT[] NOT NULL,
    confidence        TEXT NOT NULL,              -- 'high' | 'medium' | 'low'
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Action proposals (Marketing & Operations) verified by Hybrid Critic
CREATE TABLE IF NOT EXISTS actions (
    id                  SERIAL PRIMARY KEY,
    scenario_tag        TEXT NOT NULL DEFAULT 'real_shop',
    action_type         TEXT NOT NULL,          -- 'LISTING_UPDATE' | 'CONTENT' | 'REVIEW_REPLY' | 'PROMOTION' | 'CUSTOMER_CARE' | 'PRODUCT_FIX' | 'OPS'
    is_marketing        BOOLEAN NOT NULL DEFAULT TRUE,
    title               TEXT NOT NULL,
    what_to_do          TEXT NOT NULL,
    why_rationale       TEXT NOT NULL,
    how_and_when        TEXT NOT NULL,
    success_metric      TEXT NOT NULL,
    effort              TEXT NOT NULL,          -- 'low' | 'medium' | 'high'
    impact              TEXT NOT NULL,          -- 'low' | 'medium' | 'high'
    priority_score      REAL NOT NULL DEFAULT 0.0,
    insight_ids         INT[] NOT NULL,
    evidence_review_ids TEXT[] NOT NULL,
    critic_passed       BOOLEAN NOT NULL DEFAULT TRUE,
    critic_trace        JSONB,
    status              TEXT NOT NULL DEFAULT 'proposed', -- 'proposed' | 'approved' | 'edited' | 'rejected' | 'done'
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Human-in-the-loop shop owner decision feedback
CREATE TABLE IF NOT EXISTS action_feedback (
    id                SERIAL PRIMARY KEY,
    action_id         INT NOT NULL REFERENCES actions(id) ON DELETE CASCADE,
    decision          TEXT NOT NULL,              -- 'approve' | 'edit' | 'reject' | 'mark_done'
    reason_category   TEXT,
    note              TEXT,
    edited_content    JSONB,
    decided_at        TIMESTAMPTZ DEFAULT NOW()
);

-- 6. System background jobs & audit log
CREATE TABLE IF NOT EXISTS system_jobs_audit (
    id                SERIAL PRIMARY KEY,
    job_type          TEXT NOT NULL,              -- 'import' | 'analyze' | 'plan_actions' | 'decision'
    status            TEXT NOT NULL,              -- 'running' | 'completed' | 'failed'
    details           JSONB,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    completed_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_reviews_scenario ON reviews(scenario_tag, platform);
CREATE INDEX IF NOT EXISTS idx_opinions_aspect_pol ON opinions(aspect, polarity);
CREATE INDEX IF NOT EXISTS idx_actions_scenario_status ON actions(scenario_tag, status);

-- CreBy: MenBoyBMN

