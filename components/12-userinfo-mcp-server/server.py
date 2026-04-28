#!/usr/bin/env python3
"""
Simple MCP Server for User Info API

Provides read-only query tools for accessing user subscription data.
Single-file implementation using FastAPI.

Tools:
- get_user_info: Get user details by username
- get_user_subscriptions: Get all subscriptions for a user
- get_subscription_usage: Get usage records for a subscription
- get_usage_insights: Get usage insights for a subscription
- get_current_plan: Get current active plan for a subscription
"""

import os
from datetime import date as dt
from typing import Optional
import httpx
import uvicorn
import traceback
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

# Configuration
USERINFO_API_URL = os.getenv(
    "USERINFO_API_URL",
    "http://userinfo-api.user-info.svc.cluster.local:8000"
)

# Initialize FastAPI app
app = FastAPI(
    title="User Info MCP Server",
    description="MCP server providing read-only query tools for User Info API",
    version="1.0.0"
)


# Helper function to make API calls
async def call_api(endpoint: str, params: dict = None) -> dict:
    """Call the User Info API and return JSON response."""
    url = f"{USERINFO_API_URL}/api/v1{endpoint}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"error": "Not found", "detail": e.response.json().get("detail", "Resource not found")}
            else:
                return {"error": f"API error: {e.response.status_code}", "detail": str(e)}
        except Exception as e:
            return {"error": "Request failed", "detail": str(e)}


# JSON-RPC Request model
class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict | None = None
    id: int | str | None = None


# Request models
class UserInfoRequest(BaseModel):
    username: str


class UserSubscriptionsRequest(BaseModel):
    username: str


class SubscriptionUsageRequest(BaseModel):
    mobile_number: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class UsageInsightsRequest(BaseModel):
    mobile_number: str


class CurrentPlanRequest(BaseModel):
    mobile_number: str


# Response model
class ToolResponse(BaseModel):
    result: str


@app.get("/")
async def root():
    """Root endpoint with available tools."""
    return {
        "name": "User Info MCP Server",
        "version": "1.0.0",
        "tools": [
            "get_user_info",
            "get_user_subscriptions",
            "get_subscription_usage",
            "get_usage_insights",
            "get_current_plan"
        ],
        "api_url": USERINFO_API_URL
    }


@app.post("/mcp")
async def mcp_endpoint(request: JSONRPCRequest):
    """MCP JSON-RPC endpoint."""

    print(f"Received request: method={request.method}, id={request.id}, params={request.params}")

    try:
        if request.method == "initialize":
            params = request.params or {}
            client_protocol = params.get("protocolVersion", "2024-11-05")

            response_data = {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {
                    "protocolVersion": client_protocol,
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "userinfo-mcp-server",
                        "version": "1.0.0"
                    }
                }
            }
            print(f"Initialize response: {response_data}")
            return response_data

        elif request.method == "ping":
            response_data = {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {}
            }
            print(f"Ping response: {response_data}")
            return response_data

        elif request.method == "notifications/initialized":
            # Notifications don't need a JSON-RPC response - return 204 No Content
            print("Received initialized notification - no response needed")
            return Response(status_code=204)

        elif request.method == "tools/list":
            response_data = {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {
                    "tools": [
                        {
                            "name": "get_user_info",
                            "description": "Get user information by username including subscriptions",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "username": {"type": "string", "description": "Username to search for"}
                                },
                                "required": ["username"]
                            }
                        },
                        {
                            "name": "get_user_subscriptions",
                            "description": "Get all subscriptions for a user",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "username": {"type": "string", "description": "Username to search for"}
                                },
                                "required": ["username"]
                            }
                        },
                        {
                            "name": "get_subscription_usage",
                            "description": "Get usage records for a subscription by mobile number",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "mobile_number": {"type": "string", "description": "Mobile number"},
                                    "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                                    "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"}
                                },
                                "required": ["mobile_number"]
                            }
                        },
                        {
                            "name": "get_usage_insights",
                            "description": "Get usage insights and patterns for a subscription",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "mobile_number": {"type": "string", "description": "Mobile number"}
                                },
                                "required": ["mobile_number"]
                            }
                        },
                        {
                            "name": "get_current_plan",
                            "description": "Get the currently active plan for a subscription",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "mobile_number": {"type": "string", "description": "Mobile number"}
                                },
                                "required": ["mobile_number"]
                            }
                        }
                    ]
                }
            }
            return response_data

        elif request.method == "tools/call":
            params = request.params or {}
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            # Call the appropriate tool endpoint
            if tool_name == "get_user_info":
                result = await get_user_info(UserInfoRequest(**arguments))
                result_text = result.result
            elif tool_name == "get_user_subscriptions":
                result = await get_user_subscriptions(UserSubscriptionsRequest(**arguments))
                result_text = result.result
            elif tool_name == "get_subscription_usage":
                result = await get_subscription_usage(SubscriptionUsageRequest(**arguments))
                result_text = result.result
            elif tool_name == "get_usage_insights":
                result = await get_usage_insights(UsageInsightsRequest(**arguments))
                result_text = result.result
            elif tool_name == "get_current_plan":
                result = await get_current_plan(CurrentPlanRequest(**arguments))
                result_text = result.result
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }

            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result_text
                        }
                    ]
                }
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {request.method}"
                }
            }

    except Exception as e:
        print(f"Error handling request: {e}")
        traceback.print_exc()
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/tools/get_user_info", response_model=ToolResponse)
async def get_user_info(request: UserInfoRequest) -> ToolResponse:
    """
    Get user information by username.

    Returns user details including user_id, email, and associated subscriptions.
    """
    username = request.username

    # First, search for user by username
    result = await call_api("/users", params={"username": username, "page_size": 1})

    if "error" in result:
        return ToolResponse(result=f"Error: {result['detail']}")

    if result.get("total", 0) == 0:
        return ToolResponse(result=f"User '{username}' not found")

    user = result["items"][0]
    user_id = user["user_id"]

    # Get full user details with subscriptions
    user_detail = await call_api(f"/users/{user_id}")

    if "error" in user_detail:
        return ToolResponse(result=f"Error fetching user details: {user_detail['detail']}")

    # Format response
    output = f"User: {user_detail['user_name']} (@{user_detail['username']})\n"
    output += f"Email: {user_detail['email']}\n"
    output += f"User ID: {user_detail['user_id']}\n"
    output += f"Created: {user_detail['created_at']}\n"

    if user_detail.get('subscriptions'):
        output += f"\nSubscriptions ({len(user_detail['subscriptions'])}):\n"
        for sub in user_detail['subscriptions']:
            output += f"  - Mobile: {sub['mobile_number']} (ID: {sub['subscription_id']})\n"
            output += f"    Account: {sub['account_number']}\n"
            output += f"    Status: {sub['status']}\n"
    else:
        output += "\nNo subscriptions found\n"

    return ToolResponse(result=output)


@app.post("/tools/get_user_subscriptions", response_model=ToolResponse)
async def get_user_subscriptions(request: UserSubscriptionsRequest) -> ToolResponse:
    """Get all subscriptions for a user."""
    username = request.username

    # Find user by username
    result = await call_api("/users", params={"username": username, "page_size": 1})

    if "error" in result:
        return ToolResponse(result=f"Error: {result['detail']}")

    if result.get("total", 0) == 0:
        return ToolResponse(result=f"User '{username}' not found")

    user_id = result["items"][0]["user_id"]

    # Get subscriptions for user
    subs_result = await call_api("/subscriptions", params={"user_id": user_id})

    if "error" in subs_result:
        return ToolResponse(result=f"Error: {subs_result['detail']}")

    if subs_result.get("total", 0) == 0:
        return ToolResponse(result=f"No subscriptions found for user '{username}'")

    output = f"Subscriptions for {username}:\n\n"
    for sub in subs_result["items"]:
        output += f"Subscription ID: {sub['subscription_id']}\n"
        output += f"  Mobile Number: {sub['mobile_number']}\n"
        output += f"  Account: {sub['account_number']}\n"
        output += f"  Status: {sub['status']}\n"
        output += f"  Created: {sub['created_at']}\n\n"

    return ToolResponse(result=output)


@app.post("/tools/get_subscription_usage", response_model=ToolResponse)
async def get_subscription_usage(request: SubscriptionUsageRequest) -> ToolResponse:
    """Get usage records for a subscription by mobile number."""
    mobile_number = request.mobile_number
    start_date = request.start_date
    end_date = request.end_date

    # Find subscription by mobile number
    subs_result = await call_api("/subscriptions", params={"page_size": 100})

    if "error" in subs_result:
        return ToolResponse(result=f"Error: {subs_result['detail']}")

    # Find matching subscription
    subscription = None
    for sub in subs_result.get("items", []):
        if sub["mobile_number"] == mobile_number:
            subscription = sub
            break

    if not subscription:
        return ToolResponse(result=f"Subscription with mobile number '{mobile_number}' not found")

    subscription_id = subscription["subscription_id"]

    # Get usage records
    params = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date

    usage_result = await call_api(f"/subscriptions/{subscription_id}/usage", params=params)

    if "error" in usage_result:
        return ToolResponse(result=f"Error: {usage_result['detail']}")

    if not usage_result:
        return ToolResponse(result=f"No usage records found for mobile {mobile_number}")

    output = f"Usage Records for {mobile_number}:\n\n"

    # Also get aggregate if date range provided
    if start_date and end_date:
        agg_result = await call_api(
            f"/subscriptions/{subscription_id}/usage/aggregate",
            params={"start_date": start_date, "end_date": end_date}
        )

        if "error" not in agg_result:
            output += f"Summary ({start_date} to {end_date}):\n"
            output += f"  Total Data: {agg_result['total_data_gb']} GB\n"
            output += f"  Total Voice: {agg_result['total_voice_minutes']} minutes\n"
            output += f"  Total SMS: {agg_result['total_sms']} messages\n"
            output += f"  Record Count: {agg_result['record_count']} days\n\n"

    output += "Daily Usage:\n"
    for record in usage_result[:10]:  # Show latest 10 records
        output += f"  {record['usage_date']}:\n"
        output += f"    Data: {record['data_used_gb']} GB\n"
        output += f"    Voice: {record['voice_used_minutes']} min\n"
        output += f"    SMS: {record['sms_used']} messages\n"

    if len(usage_result) > 10:
        output += f"\n  ... and {len(usage_result) - 10} more records\n"

    return ToolResponse(result=output)


@app.post("/tools/get_usage_insights", response_model=ToolResponse)
async def get_usage_insights(request: UsageInsightsRequest) -> ToolResponse:
    """Get usage insights for a subscription."""
    mobile_number = request.mobile_number

    # Find subscription by mobile number
    subs_result = await call_api("/subscriptions", params={"page_size": 100})

    if "error" in subs_result:
        return ToolResponse(result=f"Error: {subs_result['detail']}")

    # Find matching subscription
    subscription = None
    for sub in subs_result.get("items", []):
        if sub["mobile_number"] == mobile_number:
            subscription = sub
            break

    if not subscription:
        return ToolResponse(result=f"Subscription with mobile number '{mobile_number}' not found")

    subscription_id = subscription["subscription_id"]

    # Get usage insights
    insights_result = await call_api(f"/subscriptions/{subscription_id}/insights")

    if "error" in insights_result:
        return ToolResponse(result=f"Error: {insights_result['detail']}")

    if not insights_result:
        return ToolResponse(result=f"No usage insights found for mobile {mobile_number}")

    output = f"Usage Insights for {mobile_number}:\n\n"

    for insight in insights_result:
        output += f"Month: {insight['month']}\n"
        output += f"  Usage Type: {insight['usage_type']}\n"
        output += f"  Data Usage: {insight['data_usage_percent']}% of plan\n\n"

    return ToolResponse(result=output)


@app.post("/tools/get_current_plan", response_model=ToolResponse)
async def get_current_plan(request: CurrentPlanRequest) -> ToolResponse:
    """Get the current active plan for a subscription."""
    mobile_number = request.mobile_number

    # Find subscription by mobile number
    subs_result = await call_api("/subscriptions", params={"page_size": 100})

    if "error" in subs_result:
        return ToolResponse(result=f"Error: {subs_result['detail']}")

    # Find matching subscription
    subscription = None
    for sub in subs_result.get("items", []):
        if sub["mobile_number"] == mobile_number:
            subscription = sub
            break

    if not subscription:
        return ToolResponse(result=f"Subscription with mobile number '{mobile_number}' not found")

    subscription_id = subscription["subscription_id"]

    # Get subscription plans
    plans_result = await call_api(f"/subscriptions/{subscription_id}/plans")

    if "error" in plans_result:
        return ToolResponse(result=f"Error: {plans_result['detail']}")

    if not plans_result:
        return ToolResponse(result=f"No plans found for mobile {mobile_number}")

    # Get current plan (first one, as they're ordered by start_date desc)
    today = str(dt.today())

    current_plan = None
    for up in plans_result:
        if up['start_date'] <= today <= up['end_date']:
            current_plan = up
            break

    if not current_plan:
        current_plan = plans_result[0]  # Most recent

    plan = current_plan['plan']

    output = f"Current Plan for {mobile_number}:\n\n"
    output += f"Plan: {plan['plan_name']}\n"
    output += f"  Data Limit: {plan['data_limit_gb']} GB\n"
    output += f"  Voice Limit: {plan['voice_limit_minutes']} minutes\n"
    output += f"  SMS Limit: {plan['sms_limit']} messages\n"
    output += f"  Price: ${plan['price']}/month\n"
    output += f"  Active Period: {current_plan['start_date']} to {current_plan['end_date']}\n"

    return ToolResponse(result=output)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
