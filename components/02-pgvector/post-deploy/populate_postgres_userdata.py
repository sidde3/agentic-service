#!/usr/bin/env python3
"""
Populate the userinfo database with the normalized 8-table schema
and seed it with sample data derived from sample_usage.json.

Tables: users, subscriptions, plans, user_plans, usage_records,
        billing, usage_insights, chat_sessions
"""

import os
import sys
import json
import logging
import random
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DDL = """
-- Drop old flat tables if they exist (from previous schema)
DROP TABLE IF EXISTS user_analytics CASCADE;
DROP TABLE IF EXISTS user_usage_history CASCADE;
DROP TABLE IF EXISTS user_current_usage CASCADE;

-- New normalized schema
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    external_id VARCHAR(50),
    username VARCHAR(50),
    user_name VARCHAR(100),
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_external_id ON users(external_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    mobile_number VARCHAR(20) UNIQUE,
    account_number VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plans (
    plan_id SERIAL PRIMARY KEY,
    plan_name VARCHAR(100) UNIQUE,
    data_limit_gb INT,
    voice_limit_minutes INT,
    sms_limit INT,
    price DECIMAL(10,2)
);

CREATE TABLE IF NOT EXISTS user_plans (
    id SERIAL PRIMARY KEY,
    subscription_id INT REFERENCES subscriptions(subscription_id),
    plan_id INT REFERENCES plans(plan_id),
    start_date DATE,
    end_date DATE
);

CREATE TABLE IF NOT EXISTS usage_records (
    usage_id SERIAL PRIMARY KEY,
    subscription_id INT REFERENCES subscriptions(subscription_id),
    usage_date DATE,
    data_used_gb DECIMAL(5,2),
    voice_used_minutes INT,
    sms_used INT,
    UNIQUE(subscription_id, usage_date)
);

CREATE TABLE IF NOT EXISTS billing (
    bill_id SERIAL PRIMARY KEY,
    subscription_id INT REFERENCES subscriptions(subscription_id),
    billing_cycle_start DATE,
    billing_cycle_end DATE,
    total_amount DECIMAL(10,2),
    paid BOOLEAN DEFAULT FALSE,
    payment_date DATE
);

CREATE TABLE IF NOT EXISTS usage_insights (
    id SERIAL PRIMARY KEY,
    subscription_id INT REFERENCES subscriptions(subscription_id),
    month DATE,
    usage_type VARCHAR(20),
    data_usage_percent DECIMAL(5,2)
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    username  TEXT PRIMARY KEY,
    history   JSONB NOT NULL
);
"""

PLAN_CATALOG = [
    ("Budget Saver 5GB",    5,   200,  100,  15.00),
    ("Standard 20GB",       20,  500,  300,  30.00),
    ("Premium 50GB",        50,  1000, 500,  50.00),
    ("Ultimate Unlimited",  999, 9999, 9999, 80.00),
    ("Starter 10GB",        10,  300,  200,  22.00),
    ("Business 100GB",      100, 2000, 1000, 99.00),
]


def create_schema(conn):
    """Create all tables."""
    logger.info("Creating schema (8 tables) ...")
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()
    logger.info("Schema created.")


def seed_plans(conn):
    """Insert the plan catalog."""
    logger.info("Seeding plans ...")
    with conn.cursor() as cur:
        for name, data_gb, voice, sms, price in PLAN_CATALOG:
            cur.execute("""
                INSERT INTO plans (plan_name, data_limit_gb, voice_limit_minutes, sms_limit, price)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (plan_name) DO NOTHING
            """, (name, data_gb, voice, sms, price))
    conn.commit()
    logger.info(f"Seeded {len(PLAN_CATALOG)} plans.")


def resolve_plan_name(raw_plan_name: str) -> str:
    """Map sample_usage.json plan names to the catalog."""
    name = raw_plan_name.lower()
    for catalog_name, _, _, _, _ in PLAN_CATALOG:
        if catalog_name.lower() in name or name in catalog_name.lower():
            return catalog_name
    if "5gb" in name or "budget" in name or "saver" in name:
        return "Budget Saver 5GB"
    if "10gb" in name or "starter" in name:
        return "Starter 10GB"
    if "20gb" in name or "standard" in name:
        return "Standard 20GB"
    if "50gb" in name or "premium" in name:
        return "Premium 50GB"
    if "100gb" in name or "business" in name:
        return "Business 100GB"
    if "unlimited" in name or "ultimate" in name:
        return "Ultimate Unlimited"
    return "Standard 20GB"


def seed_from_json(conn, data_file: Path):
    """Read sample_usage.json and populate normalized tables."""
    logger.info(f"Loading sample data from {data_file}")
    with open(data_file) as f:
        raw = json.load(f)
    logger.info(f"Loaded {len(raw)} user profiles")

    today = date.today()
    cycle_start = today.replace(day=1)
    cycle_end = (cycle_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    with conn.cursor() as cur:
        for idx, (old_id, profile) in enumerate(raw.items(), start=1):
            user_name = profile.get("name", old_id)
            username = user_name.lower().replace(" ", "_").replace("the_", "")
            email = f"{username.replace('_', '.')}@example.com"

            # users
            cur.execute("""
                INSERT INTO users (external_id, username, user_name, email)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id
            """, (old_id, username, user_name, email))
            user_id = cur.fetchone()[0]

            # subscriptions
            mobile = f"08{random.randint(10000000, 99999999)}"
            account = f"ACC-{1000 + idx}"
            cur.execute("""
                INSERT INTO subscriptions (user_id, mobile_number, account_number, status)
                VALUES (%s, %s, %s, 'active')
                RETURNING subscription_id
            """, (user_id, mobile, account))
            sub_id = cur.fetchone()[0]

            # plan
            plan_name = resolve_plan_name(profile.get("current_plan", "Standard 20GB"))
            cur.execute("SELECT plan_id FROM plans WHERE plan_name = %s", (plan_name,))
            plan_row = cur.fetchone()
            if plan_row:
                plan_id = plan_row[0]
                cur.execute("""
                    INSERT INTO user_plans (subscription_id, plan_id, start_date, end_date)
                    VALUES (%s, %s, %s, %s)
                """, (sub_id, plan_id, cycle_start, cycle_end))

            # usage_records — generate daily rows for current cycle from current_usage totals
            current = profile.get("current_usage", {})
            days_into = current.get("days_into_cycle", 23)
            total_data = current.get("data_used_gb", 0)
            total_voice = current.get("voice_minutes", 0)
            total_sms = current.get("sms_count", 0)

            for d in range(days_into):
                usage_date = cycle_start + timedelta(days=d)
                frac = random.uniform(0.5, 1.5)
                day_data = round(total_data / max(days_into, 1) * frac, 2)
                day_voice = max(0, int(total_voice / max(days_into, 1) * frac))
                day_sms = max(0, int(total_sms / max(days_into, 1) * frac))
                cur.execute("""
                    INSERT INTO usage_records (subscription_id, usage_date, data_used_gb, voice_used_minutes, sms_used)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (subscription_id, usage_date) DO NOTHING
                """, (sub_id, usage_date, day_data, day_voice, day_sms))

            # usage_records — generate rows for historical months
            for hist in profile.get("usage_history", []):
                month_str = hist.get("month", "")
                if not month_str:
                    continue
                year, mon = int(month_str[:4]), int(month_str[5:7])
                hist_start = date(year, mon, 1)
                hist_end = (hist_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                h_data = hist.get("data_used_gb", 0)
                h_voice = hist.get("voice_minutes", 0)
                h_sms = hist.get("sms_count", 0)
                num_days = (hist_end - hist_start).days + 1
                for d in range(num_days):
                    usage_date = hist_start + timedelta(days=d)
                    frac = random.uniform(0.5, 1.5)
                    cur.execute("""
                        INSERT INTO usage_records (subscription_id, usage_date, data_used_gb, voice_used_minutes, sms_used)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (subscription_id, usage_date) DO NOTHING
                    """, (
                        sub_id, usage_date,
                        round(h_data / num_days * frac, 2),
                        max(0, int(h_voice / num_days * frac)),
                        max(0, int(h_sms / num_days * frac)),
                    ))

            # billing — current cycle
            overage = current.get("overage_charges", 0)
            cur.execute("SELECT price FROM plans WHERE plan_name = %s", (plan_name,))
            price_row = cur.fetchone()
            plan_price = float(price_row[0]) if price_row else 30.0
            total_bill = plan_price + overage

            paid = random.choice([True, True, True, False])
            payment_dt = (cycle_start + timedelta(days=random.randint(5, 20))) if paid else None
            cur.execute("""
                INSERT INTO billing (subscription_id, billing_cycle_start, billing_cycle_end, total_amount, paid, payment_date)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (sub_id, cycle_start, cycle_end, total_bill, paid, payment_dt))

            # billing — historical months
            for hist in profile.get("usage_history", []):
                month_str = hist.get("month", "")
                if not month_str:
                    continue
                year, mon = int(month_str[:4]), int(month_str[5:7])
                h_start = date(year, mon, 1)
                h_end = (h_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                h_overage = hist.get("overage_charges", 0)
                cur.execute("""
                    INSERT INTO billing (subscription_id, billing_cycle_start, billing_cycle_end, total_amount, paid, payment_date)
                    VALUES (%s, %s, %s, %s, TRUE, %s)
                """, (sub_id, h_start, h_end, plan_price + h_overage, h_end + timedelta(days=5)))

            # usage_insights — derive from analytics
            analytics = profile.get("usage_analytics", {})
            trend = analytics.get("trend", "stable")
            for hist in profile.get("usage_history", []):
                month_str = hist.get("month", "")
                if not month_str:
                    continue
                year, mon = int(month_str[:4]), int(month_str[5:7])
                h_data = hist.get("data_used_gb", 0)
                cur.execute("SELECT data_limit_gb FROM plans WHERE plan_name = %s", (plan_name,))
                limit_row = cur.fetchone()
                limit_gb = limit_row[0] if limit_row else 20
                pct = (h_data / limit_gb * 100) if limit_gb > 0 else 0

                if pct > 100:
                    usage_type = "over"
                elif pct < 50:
                    usage_type = "under"
                else:
                    usage_type = "normal"

                cur.execute("""
                    INSERT INTO usage_insights (subscription_id, month, usage_type, data_usage_percent)
                    VALUES (%s, %s, %s, %s)
                """, (sub_id, date(year, mon, 1), usage_type, round(pct, 2)))

            conn.commit()
            logger.info(f"Seeded user: {user_name} (id={user_id}, sub={sub_id}, mobile={mobile})")

    logger.info("All users seeded.")


def verify(conn):
    """Print row counts for all tables."""
    tables = ["users", "subscriptions", "plans", "user_plans", "usage_records", "billing", "usage_insights", "chat_sessions"]
    with conn.cursor() as cur:
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            count = cur.fetchone()[0]
            logger.info(f"  {t}: {count} rows")


def main():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("POSTGRES_DB", "userinfo")
    user = os.getenv("POSTGRES_USER", "user_info")
    password = os.getenv("POSTGRES_PASSWORD", "secret")

    logger.info("=" * 60)
    logger.info("PostgreSQL userinfo Schema Population")
    logger.info("=" * 60)
    logger.info(f"Host: {host}:{port}")
    logger.info(f"Database: {database}")
    logger.info(f"User: {user}")
    logger.info("=" * 60)

    data_file = Path(os.getenv("DATA_FILE", str(Path(__file__).parent.parent / "data/sample_usage.json")))

    try:
        conn = psycopg2.connect(host=host, port=port, database=database, user=user, password=password)
        logger.info("Connected to PostgreSQL")

        create_schema(conn)
        seed_plans(conn)
        seed_from_json(conn, data_file)
        verify(conn)

        conn.close()
        logger.info("=" * 60)
        logger.info("Population completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Failed to populate database: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
