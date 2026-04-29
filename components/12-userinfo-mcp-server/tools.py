"""
Tool handlers for the User Info MCP Server.

Contains API helpers and the 5 tool handler functions.
The TOOLS dict and TOOL_SCHEMAS live in tools_schema.py.
"""

import os
from datetime import date as dt
from typing import Optional
import httpx

USERINFO_API_URL = os.getenv("USERINFO_API_URL", "http://userinfo-api.user-info.svc.cluster.local:8000")


async def _api(endpoint: str, params: dict = None) -> dict:
    """GET a JSON resource from the User Info API."""
    url = f"{USERINFO_API_URL}/api/v1{endpoint}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, params=params or {})
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

async def _find_user(username: str) -> Optional[dict]:
    result = await _api("/users", params={"username": username, "page_size": 1})
    if "error" in result or result.get("total", 0) == 0:
        return None
    return result["items"][0]

async def _sub_api(mobile: str, endpoint: str = "", params: dict = None):
    """Find subscription by mobile, then GET a sub-endpoint. Returns (data, error_str)."""
    subs = await _api("/subscriptions", params={"page_size": 100})
    if "error" in subs:
        return None, f"Subscription with mobile '{mobile}' not found"
    sub = next((s for s in subs.get("items", []) if s["mobile_number"] == mobile), None)
    if not sub:
        return None, f"Subscription with mobile '{mobile}' not found"
    if not endpoint:
        return sub, None
    data = await _api(f"/subscriptions/{sub['subscription_id']}{endpoint}", params=params)
    if "error" in data:
        return None, f"Error: {data['error']}"
    return data, None

async def get_user_info(args: dict) -> str:
    user = await _find_user(args["username"])
    if not user:
        return f"User '{args['username']}' not found"

    detail = await _api(f"/users/{user['user_id']}")
    if "error" in detail:
        return f"Error: {detail['error']}"

    out = f"User: {detail['user_name']} (@{detail['username']})\nEmail: {detail['email']}\nUser ID: {detail['user_id']}\n"
    for s in detail.get("subscriptions", []):
        out += f"  - Mobile: {s['mobile_number']} | Account: {s['account_number']} | Status: {s['status']}\n"
    return out


async def get_user_subscriptions(args: dict) -> str:
    user = await _find_user(args["username"])
    if not user:
        return f"User '{args['username']}' not found"

    subs = await _api("/subscriptions", params={"user_id": user["user_id"]})
    if "error" in subs or subs.get("total", 0) == 0:
        return f"No subscriptions found for '{args['username']}'"

    out = f"Subscriptions for {args['username']}:\n"
    for s in subs["items"]:
        out += f"  ID: {s['subscription_id']}  Mobile: {s['mobile_number']}  Status: {s['status']}\n"
    return out

async def get_current_plan(args: dict) -> str:
    plans, err = await _sub_api(args["mobile_number"], "/plans")
    if err:
        return err
    if not plans:
        return f"No plans found for {args['mobile_number']}"

    today = str(dt.today())
    current = next((p for p in plans if p["start_date"] <= today <= p["end_date"]), plans[0])
    p = current["plan"]
    return (f"Current Plan for {args['mobile_number']}:\n"
            f"  {p['plan_name']} — ${p['price']}/mo\n"
            f"  Data: {p['data_limit_gb']}GB  Voice: {p['voice_limit_minutes']}min  SMS: {p['sms_limit']}\n"
            f"  Active: {current['start_date']} → {current['end_date']}")

async def get_subscription_usage(args: dict) -> str:
    mobile = args["mobile_number"]
    params = {k: args[k] for k in ("start_date", "end_date") if args.get(k)}

    usage, err = await _sub_api(mobile, "/usage", params=params)
    if err:
        return err
    if not usage:
        return f"No usage records for {mobile}"

    out = f"Usage Records for {mobile}:\n"
    for r in usage[:10]:
        out += f"  {r['usage_date']}: Data={r['data_used_gb']}GB  Voice={r['voice_used_minutes']}min  SMS={r['sms_used']}\n"
    if len(usage) > 10:
        out += f"  … and {len(usage) - 10} more records\n"
    return out

async def get_usage_insights(args: dict) -> str:
    insights, err = await _sub_api(args["mobile_number"], "/insights")
    if err:
        return err
    if not insights:
        return f"No insights for {args['mobile_number']}"

    out = f"Usage Insights for {args['mobile_number']}:\n"
    for i in insights:
        out += f"  {i['month']}: {i['usage_type']} — {i['data_usage_percent']}% of plan\n"
    return out