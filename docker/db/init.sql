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
    created_at_ts     TIMESTAMPTZ,
    imported_at       TEXT,
    variation         TEXT NOT NULL DEFAULT '',
    anomaly_flags     TEXT NOT NULL DEFAULT '[]',
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
    run_id            TEXT,
    is_archived       INTEGER NOT NULL DEFAULT 0,
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
    status              TEXT NOT NULL DEFAULT 'PENDING',
    run_id              TEXT,
    is_archived         INTEGER NOT NULL DEFAULT 0,
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

-- 6. Customer care reply drafts history
CREATE TABLE IF NOT EXISTS review_replies (
    id               SERIAL PRIMARY KEY,
    review_id        TEXT NOT NULL,
    scenario_tag     TEXT NOT NULL DEFAULT 'real_shop',
    reply_text       TEXT NOT NULL,
    mode_used        TEXT NOT NULL DEFAULT 'template',
    guardrail_passed INTEGER NOT NULL DEFAULT 1,
    violations       TEXT NOT NULL DEFAULT '[]',
    status           TEXT NOT NULL DEFAULT 'DRAFT',
    created_by       TEXT,
    created_at       TEXT,
    sent_at          TEXT,
    FOREIGN KEY (review_id, scenario_tag) REFERENCES reviews(review_id, scenario_tag) ON DELETE CASCADE
);

-- 7. System background jobs & audit log
CREATE TABLE IF NOT EXISTS system_jobs_audit (
    id                SERIAL PRIMARY KEY,
    job_type          TEXT NOT NULL,
    scenario_tag      TEXT,
    status            TEXT NOT NULL,
    details           TEXT,
    created_at        TEXT,
    completed_at      TEXT
);

-- 8. Pilot shops registry (1-to-1 slug <-> scenario_tag isolation)
CREATE TABLE IF NOT EXISTS pilot_shops (
    id                SERIAL PRIMARY KEY,
    slug              TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    industry          TEXT NOT NULL DEFAULT 'raincoat',
    platforms         TEXT NOT NULL DEFAULT '["shopee","tiktok"]',
    alert_config      TEXT NOT NULL DEFAULT '{}',
    webhook_secret    TEXT,
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT
);

-- 9. Pilot users & RBAC (admin / owner / cskh)
CREATE TABLE IF NOT EXISTS users (
    id                SERIAL PRIMARY KEY,
    email             TEXT NOT NULL UNIQUE,
    password_hash     TEXT NOT NULL,
    full_name         TEXT NOT NULL,
    role              TEXT NOT NULL DEFAULT 'owner',
    allowed_shops     TEXT NOT NULL DEFAULT '[]',
    is_active         INTEGER NOT NULL DEFAULT 1,
    token_version     INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT,
    last_login_at     TEXT
);

-- 10. Outbound alert dispatches & deduplication log
CREATE TABLE IF NOT EXISTS alert_dispatches (
    id                SERIAL PRIMARY KEY,
    scenario_tag      TEXT NOT NULL,
    dedup_key         TEXT NOT NULL UNIQUE,
    channel           TEXT NOT NULL,
    severity          TEXT NOT NULL DEFAULT 'MEDIUM',
    title             TEXT NOT NULL,
    payload           TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'SENT',
    error_message     TEXT,
    created_at        TEXT,
    sent_at           TEXT
);

-- 11. Scoped per-shop API keys (hashed at rest)
CREATE TABLE IF NOT EXISTS shop_api_keys (
    id                SERIAL PRIMARY KEY,
    scenario_tag      TEXT NOT NULL,
    name              TEXT NOT NULL,
    key_prefix        TEXT NOT NULL,
    key_hash          TEXT NOT NULL UNIQUE,
    role              TEXT NOT NULL DEFAULT 'owner',
    scopes            TEXT NOT NULL DEFAULT '["read","write"]',
    created_by        TEXT,
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT,
    last_used_at      TEXT,
    revoked_at        TEXT
);

-- 12. Immutable audit log for sensitive operations
CREATE TABLE IF NOT EXISTS audit_logs (
    id                SERIAL PRIMARY KEY,
    actor             TEXT NOT NULL,
    actor_role        TEXT NOT NULL DEFAULT 'system',
    action            TEXT NOT NULL,
    scenario_tag      TEXT,
    target_type       TEXT,
    target_id         TEXT,
    ip_address        TEXT,
    request_id        TEXT,
    details           TEXT NOT NULL DEFAULT '{}',
    created_at        TEXT
);

-- 13. Refresh token rotation & reuse detection table
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash        TEXT NOT NULL UNIQUE,
    family_id         TEXT NOT NULL,
    expires_at        TEXT NOT NULL,
    revoked_at        TEXT,
    replaced_by_hash  TEXT,
    created_at        TEXT
);

-- 14. Per-shop two-way Marketplace OAuth connections (tokens encrypted at rest)
CREATE TABLE IF NOT EXISTS shop_marketplace_connections (
    id                    SERIAL PRIMARY KEY,
    scenario_tag          TEXT NOT NULL,
    platform              TEXT NOT NULL,
    external_shop_id      TEXT NOT NULL,
    shop_name             TEXT,
    access_token          TEXT NOT NULL,
    refresh_token         TEXT,
    token_expires_at      TEXT,
    refresh_expires_at    TEXT,
    auto_sync_enabled     INTEGER NOT NULL DEFAULT 1,
    sync_interval_minutes INTEGER NOT NULL DEFAULT 30,
    last_synced_at        TEXT,
    last_sync_status      TEXT NOT NULL DEFAULT 'NEVER',
    last_sync_error       TEXT,
    is_active             INTEGER NOT NULL DEFAULT 1,
    created_at            TEXT,
    updated_at            TEXT,
    UNIQUE (scenario_tag, platform)
);

-- 15. Daily pre-aggregated aspect sentiment metrics (O(1) trend & overview reads)
CREATE TABLE IF NOT EXISTS daily_aspect_metrics (
    scenario_tag      TEXT NOT NULL,
    metric_date       TEXT NOT NULL,
    platform          TEXT NOT NULL DEFAULT 'all',
    aspect            TEXT NOT NULL,
    pos_count         INTEGER NOT NULL DEFAULT 0,
    neg_count         INTEGER NOT NULL DEFAULT 0,
    neu_count         INTEGER NOT NULL DEFAULT 0,
    total_count       INTEGER NOT NULL DEFAULT 0,
    updated_at        TEXT,
    PRIMARY KEY (scenario_tag, metric_date, platform, aspect)
);

-- 16. Tenant subscriptions & SaaS package limits
CREATE TABLE IF NOT EXISTS tenant_subscriptions (
    id                       SERIAL PRIMARY KEY,
    tenant_key               TEXT NOT NULL UNIQUE,
    plan_code                TEXT NOT NULL DEFAULT 'basic',
    status                   TEXT NOT NULL DEFAULT 'ACTIVE',
    monthly_llm_review_limit INTEGER NOT NULL DEFAULT 2000,
    max_shops                INTEGER NOT NULL DEFAULT 2,
    max_users                INTEGER NOT NULL DEFAULT 3,
    overage_policy           TEXT NOT NULL DEFAULT 'fallback_b1',
    trial_ends_at            TEXT,
    notes                    TEXT,
    updated_by               TEXT,
    created_at               TEXT,
    updated_at               TEXT
);

-- 17. Monthly review & CSKH reply metering per shop
CREATE TABLE IF NOT EXISTS usage_monthly (
    scenario_tag      TEXT NOT NULL,
    month_key         TEXT NOT NULL,
    llm_reviews_used  INTEGER NOT NULL DEFAULT 0,
    rule_reviews_used INTEGER NOT NULL DEFAULT 0,
    replies_generated INTEGER NOT NULL DEFAULT 0,
    updated_at        TEXT,
    PRIMARY KEY (scenario_tag, month_key)
);

ALTER TABLE insights ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE insights ADD COLUMN IF NOT EXISTS is_archived INTEGER NOT NULL DEFAULT 0;
ALTER TABLE actions ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE actions ADD COLUMN IF NOT EXISTS is_archived INTEGER NOT NULL DEFAULT 0;
ALTER TABLE actions ADD COLUMN IF NOT EXISTS implemented_at TEXT;
ALTER TABLE review_replies ADD COLUMN IF NOT EXISTS sent_at TEXT;
ALTER TABLE review_replies ADD COLUMN IF NOT EXISTS external_sync_status TEXT NOT NULL DEFAULT 'LOCAL_ONLY';
ALTER TABLE review_replies ADD COLUMN IF NOT EXISTS external_sync_error TEXT;
ALTER TABLE review_replies ADD COLUMN IF NOT EXISTS external_synced_at TEXT;
ALTER TABLE system_jobs_audit ADD COLUMN IF NOT EXISTS scenario_tag TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS variation TEXT NOT NULL DEFAULT '';
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS anomaly_flags TEXT NOT NULL DEFAULT '[]';
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS created_at_ts TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_reviews_scenario ON reviews(scenario_tag, platform);
CREATE INDEX IF NOT EXISTS idx_reviews_scenario_created ON reviews(scenario_tag, created_at);
CREATE INDEX IF NOT EXISTS idx_reviews_scenario_created_ts ON reviews(scenario_tag, created_at_ts);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_scenario_date ON daily_aspect_metrics(scenario_tag, metric_date, aspect);
CREATE INDEX IF NOT EXISTS idx_reviews_scenario_rating ON reviews(scenario_tag, rating);
CREATE INDEX IF NOT EXISTS idx_reviews_scenario_product_var ON reviews(scenario_tag, product, variation);
CREATE INDEX IF NOT EXISTS idx_opinions_aspect_pol ON opinions(scenario_tag, aspect, polarity);
CREATE INDEX IF NOT EXISTS idx_actions_scenario_status ON actions(scenario_tag, status);
CREATE INDEX IF NOT EXISTS idx_actions_scenario_archived ON actions(scenario_tag, is_archived);
CREATE INDEX IF NOT EXISTS idx_opinions_review ON opinions(scenario_tag, review_id);
CREATE INDEX IF NOT EXISTS idx_insights_scenario_kind ON insights(scenario_tag, kind);
CREATE INDEX IF NOT EXISTS idx_action_feedback_action_id ON action_feedback(action_id);
CREATE INDEX IF NOT EXISTS idx_review_replies_review ON review_replies(scenario_tag, review_id);
CREATE INDEX IF NOT EXISTS idx_alert_dispatches_scenario ON alert_dispatches(scenario_tag, status);
CREATE INDEX IF NOT EXISTS idx_jobs_scenario ON system_jobs_audit(scenario_tag);
CREATE INDEX IF NOT EXISTS idx_shop_api_keys_scenario ON shop_api_keys(scenario_tag, is_active);
CREATE INDEX IF NOT EXISTS idx_audit_logs_scenario_created ON audit_logs(scenario_tag, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor, created_at);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id, revoked_at);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_family ON refresh_tokens(family_id);
CREATE INDEX IF NOT EXISTS idx_mp_conn_active ON shop_marketplace_connections(is_active, auto_sync_enabled, platform);
CREATE INDEX IF NOT EXISTS idx_tenant_subs_key ON tenant_subscriptions(tenant_key);
CREATE INDEX IF NOT EXISTS idx_usage_monthly_month ON usage_monthly(month_key, scenario_tag);

-- Read-Only Role for Agent Security Layer 4
DO $$
BEGIN
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ecom_agent_ro') THEN
            CREATE ROLE ecom_agent_ro WITH LOGIN PASSWORD 'agent_readonly_pass';
        END IF;
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'Skipping CREATE ROLE ecom_agent_ro due to insufficient privileges';
    END;

    BEGIN
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO ecom_agent_ro', current_database());
        GRANT USAGE ON SCHEMA public TO ecom_agent_ro;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO ecom_agent_ro;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ecom_agent_ro;
        REVOKE SELECT ON users FROM ecom_agent_ro;
        REVOKE SELECT ON pilot_shops FROM ecom_agent_ro;
        REVOKE SELECT ON shop_api_keys FROM ecom_agent_ro;
        REVOKE SELECT ON audit_logs FROM ecom_agent_ro;
        REVOKE SELECT ON refresh_tokens FROM ecom_agent_ro;
        REVOKE SELECT ON shop_marketplace_connections FROM ecom_agent_ro;
        REVOKE SELECT ON tenant_subscriptions FROM ecom_agent_ro;
    EXCEPTION WHEN insufficient_privilege OR undefined_object THEN
        RAISE NOTICE 'Skipping GRANTs to ecom_agent_ro due to insufficient privileges or missing object';
    END;
END
$$;

-- CreBy: MenBoyBMN
