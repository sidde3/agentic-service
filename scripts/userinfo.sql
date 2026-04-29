-- setup_userinfo_sample.sql
-- Creates tables (if missing) and loads minimal sample data for userinfo DB.
-- Run: psql "postgresql://USER:PASS@HOST:5432/userinfo" -v ON_ERROR_STOP=1 -f setup_userinfo_sample.sql

BEGIN;

-- ── Schema (matches userinfo-api models + chat_sessions used by router) ──

CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    external_id VARCHAR(50),
    username VARCHAR(50) NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_external_id ON users(external_id);

CREATE TABLE IF NOT EXISTS plans (
    plan_id SERIAL PRIMARY KEY,
    plan_name VARCHAR(100) NOT NULL UNIQUE,
    data_limit_gb INTEGER NOT NULL,
    voice_limit_minutes INTEGER NOT NULL,
    sms_limit INTEGER NOT NULL,
    price NUMERIC(10,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    mobile_number VARCHAR(20) NOT NULL UNIQUE,
    account_number VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_plans (
    id SERIAL PRIMARY KEY,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(subscription_id),
    plan_id INTEGER NOT NULL REFERENCES plans(plan_id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_records (
    usage_id SERIAL PRIMARY KEY,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(subscription_id),
    usage_date DATE NOT NULL,
    data_used_gb NUMERIC(5,2) NOT NULL,
    voice_used_minutes INTEGER NOT NULL,
    sms_used INTEGER NOT NULL,
    UNIQUE (subscription_id, usage_date)
);

CREATE TABLE IF NOT EXISTS billing (
    bill_id SERIAL PRIMARY KEY,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(subscription_id),
    billing_cycle_start DATE NOT NULL,
    billing_cycle_end DATE NOT NULL,
    total_amount NUMERIC(10,2) NOT NULL,
    paid BOOLEAN DEFAULT FALSE,
    payment_date DATE
);

CREATE TABLE IF NOT EXISTS usage_insights (
    id SERIAL PRIMARY KEY,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(subscription_id),
    month DATE NOT NULL,
    usage_type VARCHAR(20) NOT NULL,
    data_usage_percent NUMERIC(5,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    username TEXT PRIMARY KEY,
    history JSONB NOT NULL
);

-- ── Reset sample data (dev only) ──
TRUNCATE TABLE
    usage_insights,
    billing,
    usage_records,
    user_plans,
    subscriptions,
    users,
    plans,
    chat_sessions
RESTART IDENTITY CASCADE;

-- ── Seed: plans ──
INSERT INTO plans (plan_name, data_limit_gb, voice_limit_minutes, sms_limit, price) VALUES
    ('Budget Saver 5GB', 5, 200, 100, 15.00),
    ('Standard 20GB', 20, 500, 300, 30.00),
    ('Premium 50GB', 50, 1000, 500, 50.00);

-- ── Seed: users ──
INSERT INTO users (external_id, username, user_name, email) VALUES
    ('demo_ext_1', 'jessica.thompson', 'Jessica Thompson', 'jessica.thompson@example.com');

-- ── Seed: subscriptions ──
INSERT INTO subscriptions (user_id, mobile_number, account_number, status)
VALUES (1, '0812345678', 'ACC-1001', 'active');

-- ── Seed: user_plans (subscription 1 on Standard 20GB this month) ──
INSERT INTO user_plans (subscription_id, plan_id, start_date, end_date)
VALUES (
    1,
    (SELECT plan_id FROM plans WHERE plan_name = 'Standard 20GB'),
    date_trunc('month', CURRENT_DATE)::date,
    (date_trunc('month', CURRENT_DATE) + interval '1 month - 1 day')::date
);

-- ── Seed: usage_records (two days) ──
INSERT INTO usage_records (subscription_id, usage_date, data_used_gb, voice_used_minutes, sms_used) VALUES
    (1, CURRENT_DATE - 1, 1.20, 10, 5),
    (1, CURRENT_DATE,     0.80,  8, 3);

-- ── Seed: billing ──
INSERT INTO billing (subscription_id, billing_cycle_start, billing_cycle_end, total_amount, paid, payment_date)
VALUES (
    1,
    date_trunc('month', CURRENT_DATE)::date,
    (date_trunc('month', CURRENT_DATE) + interval '1 month - 1 day')::date,
    30.00,
    TRUE,
    CURRENT_DATE - 5
);

-- ── Seed: usage_insights ──
INSERT INTO usage_insights (subscription_id, month, usage_type, data_usage_percent)
VALUES (
    1,
    date_trunc('month', CURRENT_DATE)::date,
    'normal',
    45.50
);

-- ── Seed: chat_sessions (router / optional) ──
INSERT INTO chat_sessions (username, history) VALUES (
    'jessica.thompson',
    '[]'::jsonb
);

COMMIT;
