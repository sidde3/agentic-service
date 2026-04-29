#!/usr/bin/env python3
"""
Mobile Usage MCP Server V2

JSON-RPC based MCP server for retrieving user mobile usage data.
Queries a normalized PostgreSQL schema in the userinfo database.
Provides 4 tools for personalized mobile plan recommendations.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from pydantic import BaseModel
import uvicorn
import os
import json
import traceback
from typing import Dict, Any, Optional
from datetime import date, timedelta

import asyncpg

DB_HOST = os.getenv("DB_HOST", "pgvector")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "userinfo")
DB_USER = os.getenv("DB_USER", "user_info")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secret")

pool: Optional[asyncpg.Pool] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    dsn = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    print(f"Connecting to PostgreSQL: {DB_HOST}:{DB_PORT}/{DB_NAME} as {DB_USER}")
    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    print("PostgreSQL connection pool created")
    yield
    await pool.close()
    print("PostgreSQL connection pool closed")


app = FastAPI(title="Mobile Usage MCP Server V2", lifespan=lifespan)


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict | None = None
    id: int | str | None = None


# ---------------------------------------------------------------------------
# Tool implementations — all query PostgreSQL
# ---------------------------------------------------------------------------

async def _resolve_user_id(conn, identifier: str) -> int | None:
    """Resolve email, username, or external_id to the internal integer PK."""
    identifier = identifier.strip()
    if "@" in identifier:
        row = await conn.fetchrow("SELECT user_id FROM users WHERE email = $1", identifier)
    else:
        row = await conn.fetchrow(
            "SELECT user_id FROM users WHERE username = $1 OR external_id = $1",
            identifier,
        )
    return row["user_id"] if row else None


async def get_user_current_usage_impl(user_id: str) -> Dict[str, Any]:
    """Get current billing-cycle usage for a user's subscription(s)."""
    async with pool.acquire() as conn:
        uid = await _resolve_user_id(conn, user_id)
        if uid is None:
            return {"error": f"User {user_id} not found"}

        # Walk from the user to their subscriptions, then pull in:
        #   - the currently-active plan  (user_plans + plans)
        #   - the current billing cycle  (billing)
        #   - aggregated usage within that billing cycle (usage_records)
        # LEFT JOINs ensure we still return rows even if a subscription
        # has no active plan or no billing record yet.
        rows = await conn.fetch("""
            SELECT
                s.mobile_number,
                s.account_number,
                s.status,
                p.plan_name,
                p.data_limit_gb,
                p.voice_limit_minutes,
                p.sms_limit,
                p.price AS plan_price,
                b.billing_cycle_start,
                b.billing_cycle_end,
                b.total_amount AS billed_amount,
                b.paid,
                COALESCE(SUM(ur.data_used_gb), 0)          AS data_used_gb,
                COALESCE(SUM(ur.voice_used_minutes), 0)     AS voice_used_minutes,
                COALESCE(SUM(ur.sms_used), 0)               AS sms_used
            FROM users u
            JOIN subscriptions s ON u.user_id = s.user_id
            LEFT JOIN user_plans up
                ON  s.subscription_id = up.subscription_id
                AND CURRENT_DATE BETWEEN up.start_date AND up.end_date
            LEFT JOIN plans p ON up.plan_id = p.plan_id
            LEFT JOIN billing b
                ON  s.subscription_id = b.subscription_id
                AND CURRENT_DATE BETWEEN b.billing_cycle_start AND b.billing_cycle_end
            LEFT JOIN usage_records ur
                ON  s.subscription_id = ur.subscription_id
                AND ur.usage_date BETWEEN
                    COALESCE(b.billing_cycle_start, date_trunc('month', CURRENT_DATE)::date)
                    AND
                    COALESCE(b.billing_cycle_end, (date_trunc('month', CURRENT_DATE) + interval '1 month - 1 day')::date)
            WHERE u.user_id = $1
            GROUP BY s.mobile_number, s.account_number, s.status,
                     p.plan_name, p.data_limit_gb, p.voice_limit_minutes, p.sms_limit, p.price,
                     b.billing_cycle_start, b.billing_cycle_end, b.total_amount, b.paid
        """, uid)

        if not rows:
            return {"error": f"User {user_id} not found"}

        results = []
        for r in rows:
            cycle_start = r["billing_cycle_start"] or date.today().replace(day=1)
            cycle_end = r["billing_cycle_end"] or (date.today().replace(day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)
            days_into_cycle = (date.today() - cycle_start).days

            data_limit = r["data_limit_gb"] or 0
            data_used = float(r["data_used_gb"])
            overage = max(0, data_used - data_limit) if data_limit > 0 else 0

            results.append({
                "mobile_number": r["mobile_number"],
                "account_number": r["account_number"],
                "status": r["status"],
                "current_plan": r["plan_name"] or "No active plan",
                "data_used_gb": round(data_used, 2),
                "data_limit_gb": data_limit,
                "voice_used_minutes": int(r["voice_used_minutes"]),
                "voice_limit_minutes": r["voice_limit_minutes"] or 0,
                "sms_used": int(r["sms_used"]),
                "sms_limit": r["sms_limit"] or 0,
                "billing_cycle_start": str(cycle_start),
                "billing_cycle_end": str(cycle_end),
                "days_into_cycle": days_into_cycle,
                "overage_gb": round(overage, 2),
                "plan_price": float(r["plan_price"]) if r["plan_price"] else 0,
                "paid": r["paid"] if r["paid"] is not None else False,
            })

        if len(results) == 1:
            return results[0]
        return {"user_id": user_id, "subscriptions": results}


async def get_usage_history_impl(user_id: str, months: int = 3) -> list:
    """Get monthly usage history for a user."""
    async with pool.acquire() as conn:
        uid = await _resolve_user_id(conn, user_id)
        if uid is None:
            return [{"error": f"User {user_id} not found"}]

        # Aggregate daily usage_records into monthly totals for the
        # last N months, grouped by subscription (mobile_number).
        rows = await conn.fetch("""
            SELECT
                s.mobile_number,
                to_char(ur.usage_date, 'YYYY-MM') AS month,
                SUM(ur.data_used_gb)          AS data_used_gb,
                SUM(ur.voice_used_minutes)    AS voice_used_minutes,
                SUM(ur.sms_used)              AS sms_used
            FROM users u
            JOIN subscriptions s  ON u.user_id = s.user_id
            JOIN usage_records ur ON s.subscription_id = ur.subscription_id
            WHERE u.user_id = $1
              AND ur.usage_date >= (CURRENT_DATE - ($2 || ' months')::interval)::date
            GROUP BY s.mobile_number, to_char(ur.usage_date, 'YYYY-MM')
            ORDER BY month DESC
        """, uid, str(months))

        return [
            {
                "mobile_number": r["mobile_number"],
                "month": r["month"],
                "data_used_gb": round(float(r["data_used_gb"]), 2),
                "voice_used_minutes": int(r["voice_used_minutes"]),
                "sms_used": int(r["sms_used"]),
            }
            for r in rows
        ]


async def analyze_usage_patterns_impl(user_id: str) -> Dict[str, Any]:
    """Analyze usage patterns from usage_insights + aggregated usage_records."""
    async with pool.acquire() as conn:
        uid = await _resolve_user_id(conn, user_id)
        if uid is None:
            return {"error": f"User {user_id} not found"}

        # Fetch the most recent 6 monthly insight rows (pre-computed
        # "over" / "under" usage labels stored by the ingestion pipeline).
        insights = await conn.fetch("""
            SELECT
                s.mobile_number,
                ui.month,
                ui.usage_type,
                ui.data_usage_percent
            FROM users u
            JOIN subscriptions s  ON u.user_id = s.user_id
            JOIN usage_insights ui ON s.subscription_id = ui.subscription_id
            WHERE u.user_id = $1
            ORDER BY ui.month DESC
            LIMIT 6
        """, uid)

        # Calculate daily averages over the last 3 months, then
        # multiply by 30 to estimate monthly averages.
        averages = await conn.fetchrow("""
            SELECT
                COALESCE(AVG(ur.data_used_gb), 0)       AS avg_daily_data_gb,
                COALESCE(AVG(ur.voice_used_minutes), 0)  AS avg_daily_voice,
                COALESCE(AVG(ur.sms_used), 0)            AS avg_daily_sms,
                COUNT(DISTINCT to_char(ur.usage_date, 'YYYY-MM')) AS months_of_data
            FROM users u
            JOIN subscriptions s  ON u.user_id = s.user_id
            JOIN usage_records ur ON s.subscription_id = ur.subscription_id
            WHERE u.user_id = $1
              AND ur.usage_date >= (CURRENT_DATE - interval '3 months')
        """, uid)

        if not averages or averages["months_of_data"] == 0:
            return {"error": f"No usage data found for user {user_id}"}

        avg_monthly_data = round(float(averages["avg_daily_data_gb"]) * 30, 2)
        avg_monthly_voice = round(float(averages["avg_daily_voice"]) * 30)
        avg_monthly_sms = round(float(averages["avg_daily_sms"]) * 30)

        if avg_monthly_data < 5:
            category = "light"
        elif avg_monthly_data < 20:
            category = "medium"
        elif avg_monthly_data < 50:
            category = "heavy"
        else:
            category = "ultra-heavy"

        over_count = sum(1 for i in insights if i["usage_type"] == "over")
        under_count = sum(1 for i in insights if i["usage_type"] == "under")
        if over_count > under_count:
            trend = "increasing"
        elif under_count > over_count:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "user_id": user_id,
            "average_monthly_data_gb": avg_monthly_data,
            "average_monthly_voice_minutes": avg_monthly_voice,
            "average_monthly_sms": avg_monthly_sms,
            "usage_category": category,
            "trend": trend,
            "recent_insights": [
                {
                    "mobile_number": i["mobile_number"],
                    "month": str(i["month"]),
                    "usage_type": i["usage_type"],
                    "data_usage_percent": float(i["data_usage_percent"]) if i["data_usage_percent"] else 0,
                }
                for i in insights
            ],
        }


async def get_overage_risk_impl(user_id: str) -> Dict[str, Any]:
    """Calculate overage risk based on current usage vs plan limits."""
    async with pool.acquire() as conn:
        uid = await _resolve_user_id(conn, user_id)
        if uid is None:
            return {"error": f"User {user_id} not found"}

        # Sum data usage from the billing-cycle start up to today so
        # we can project whether the user will exceed their plan limit
        # by the end of the cycle.
        row = await conn.fetchrow("""
            SELECT
                s.mobile_number,
                p.plan_name,
                p.data_limit_gb,
                b.billing_cycle_start,
                b.billing_cycle_end,
                COALESCE(SUM(ur.data_used_gb), 0) AS data_used_gb
            FROM users u
            JOIN subscriptions s ON u.user_id = s.user_id
            LEFT JOIN user_plans up
                ON  s.subscription_id = up.subscription_id
                AND CURRENT_DATE BETWEEN up.start_date AND up.end_date
            LEFT JOIN plans p ON up.plan_id = p.plan_id
            LEFT JOIN billing b
                ON  s.subscription_id = b.subscription_id
                AND CURRENT_DATE BETWEEN b.billing_cycle_start AND b.billing_cycle_end
            LEFT JOIN usage_records ur
                ON  s.subscription_id = ur.subscription_id
                AND ur.usage_date BETWEEN
                    COALESCE(b.billing_cycle_start, date_trunc('month', CURRENT_DATE)::date)
                    AND CURRENT_DATE
            WHERE u.user_id = $1
            GROUP BY s.mobile_number, p.plan_name, p.data_limit_gb,
                     b.billing_cycle_start, b.billing_cycle_end
            LIMIT 1
        """, uid)

        if not row:
            return {"error": f"User {user_id} not found"}

        plan_limit = row["data_limit_gb"] or 0
        data_used = float(row["data_used_gb"])
        cycle_start = row["billing_cycle_start"] or date.today().replace(day=1)
        cycle_end = row["billing_cycle_end"] or (date.today().replace(day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)

        days_into_cycle = max((date.today() - cycle_start).days, 1)
        days_remaining = max((cycle_end - date.today()).days, 0)
        daily_average = data_used / days_into_cycle
        projected_total = data_used + (daily_average * days_remaining)

        if plan_limit == 0:
            risk_level = "none"
            projected_overage = 0
            usage_pct = 0
            recommendation = "No plan limit found or unlimited plan — no overage risk."
        else:
            usage_pct = (data_used / plan_limit) * 100
            projected_overage = max(0, projected_total - plan_limit)

            if usage_pct < 70:
                risk_level = "low"
                recommendation = "Usage is on track. No immediate concerns."
            elif usage_pct < 85:
                risk_level = "medium"
                recommendation = f"At {usage_pct:.1f}% of data limit. Monitor usage to avoid overage."
            elif usage_pct < 95:
                risk_level = "high"
                recommendation = f"High overage risk! {usage_pct:.1f}% used with {days_remaining} days left."
            else:
                risk_level = "critical"
                recommendation = f"Critical! {usage_pct:.1f}% used with {days_remaining} days remaining."

        return {
            "mobile_number": row["mobile_number"],
            "plan_name": row["plan_name"] or "Unknown",
            "risk_level": risk_level,
            "current_usage_gb": round(data_used, 2),
            "plan_limit_gb": plan_limit,
            "current_usage_percentage": round(usage_pct, 1),
            "daily_average_gb": round(daily_average, 2),
            "projected_total_gb": round(projected_total, 2),
            "projected_overage_gb": round(projected_overage, 2),
            "days_into_cycle": days_into_cycle,
            "days_remaining": days_remaining,
            "recommendation": recommendation,
        }


# ---------------------------------------------------------------------------
# MCP JSON-RPC endpoint
# ---------------------------------------------------------------------------

TOOLS_LIST = [
    {
        "name": "get_user_current_usage",
        "description": "Retrieves current billing-cycle usage data for a user including data, voice, SMS usage and plan details",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User email (e.g. 'jessica.thompson@example.com'), username (e.g. 'jessica_thompson'), or external_id (e.g. 'user_heavy_1')"}
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "get_usage_history",
        "description": "Retrieves monthly usage history for the past N months to identify trends",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User email, username, or external_id"},
                "months": {"type": "integer", "description": "Number of past months (default 3, max 12)", "default": 3},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "analyze_usage_patterns",
        "description": "Analyzes usage patterns providing insights on averages, trends, and usage category",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User email, username, or external_id"}
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "get_overage_risk",
        "description": "Calculates overage risk based on current usage trajectory and provides recommendations",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User email, username, or external_id"}
            },
            "required": ["user_id"],
        },
    },
]

TOOL_DISPATCH = {
    "get_user_current_usage": lambda args: get_user_current_usage_impl(args.get("user_id", "")),
    "get_usage_history": lambda args: get_usage_history_impl(args.get("user_id", ""), args.get("months", 3)),
    "analyze_usage_patterns": lambda args: analyze_usage_patterns_impl(args.get("user_id", "")),
    "get_overage_risk": lambda args: get_overage_risk_impl(args.get("user_id", "")),
}


@app.post("/mcp")
async def mcp_endpoint(request: JSONRPCRequest):
    """MCP JSON-RPC endpoint."""
    print(f"Received request: method={request.method}, id={request.id}, params={request.params}")

    try:
        if request.method == "initialize":
            params = request.params or {}
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {
                    "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "mobile-usage-mcp-v2", "version": "2.0.0"},
                },
            }

        elif request.method == "ping":
            return {"jsonrpc": "2.0", "id": request.id, "result": {}}

        elif request.method == "notifications/initialized":
            return Response(status_code=204)

        elif request.method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {"tools": TOOLS_LIST},
            }

        elif request.method == "tools/call":
            params = request.params or {}
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            handler = TOOL_DISPATCH.get(tool_name)
            if not handler:
                return {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                }

            result = await handler(arguments)
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]},
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32601, "message": f"Method not found: {request.method}"},
            }

    except Exception as e:
        print(f"Error handling request: {e}")
        traceback.print_exc()
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
        }


@app.get("/healthz")
async def health():
    """Health check endpoint — verifies DB connectivity."""
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "server": "mobile-usage-mcp-v2", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "server": "mobile-usage-mcp-v2", "database": str(e)}


if __name__ == "__main__":
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_SERVER_PORT", "8000"))

    print(f"Starting Mobile Usage MCP Server V2 (PostgreSQL backend)")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"MCP endpoint: http://{host}:{port}/mcp")
    print("=" * 60)

    uvicorn.run(app, host=host, port=port, log_level="info")
