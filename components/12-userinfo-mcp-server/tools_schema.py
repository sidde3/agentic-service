"""
Tool registry — maps tool names to handlers and JSON schemas.

TOOLS:        name → async handler function
TOOL_SCHEMAS: list of JSON schemas for MCP tools/list
"""

from tools import (
    get_user_info,
    get_user_subscriptions,
    get_current_plan,
    get_subscription_usage,
    get_usage_insights,
)

TOOLS = {
    "get_user_info": get_user_info,
    "get_user_subscriptions": get_user_subscriptions,
    "get_current_plan": get_current_plan,
    "get_subscription_usage": get_subscription_usage,
    "get_usage_insights": get_usage_insights,
}

TOOL_SCHEMAS = [
    {"name": "get_user_info",
     "description": "Get user information by username including subscriptions",
     "inputSchema": {"type": "object",
                     "properties": {"username": {"type": "string", "description": "Username to search for"}},
                     "required": ["username"]}},
    {"name": "get_user_subscriptions",
     "description": "Get all subscriptions for a user",
     "inputSchema": {"type": "object",
                     "properties": {"username": {"type": "string", "description": "Username to search for"}},
                     "required": ["username"]}},
    {"name": "get_current_plan",
     "description": "Get the currently active plan for a subscription",
     "inputSchema": {"type": "object",
                     "properties": {"mobile_number": {"type": "string", "description": "Mobile number"}},
                     "required": ["mobile_number"]}},
    {"name": "get_subscription_usage",
     "description": "Get usage records for a subscription by mobile number",
     "inputSchema": {"type": "object",
                     "properties": {
                         "mobile_number": {"type": "string", "description": "Mobile number"},
                         "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                         "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"}},
                     "required": ["mobile_number"]}},
    {"name": "get_usage_insights",
     "description": "Get usage insights and patterns for a subscription",
     "inputSchema": {"type": "object",
                     "properties": {"mobile_number": {"type": "string", "description": "Mobile number"}},
                     "required": ["mobile_number"]}},
]
