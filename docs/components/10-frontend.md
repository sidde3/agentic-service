# 10 — Frontend (Chat UI)

Streamlit-based chat interface for interacting with the agentic system.

## What It Does

Provides a web UI where users can:
- Enter messages in a chat interface
- Select quick actions with predefined intents (e.g., "Check my data usage", "Compare plans")
- Configure their user email in the sidebar
- View streaming responses from the router

## Source: `src/chat_app.py`

### Key Features
- Chat history maintained in Streamlit session state
- Quick action buttons map to specific `predefined_intent` values, bypassing BERT classification
- Messages sent to `POST {ROUTER_URL}/chat` with user email and optional predefined intent
- Response displayed in chat bubbles

## Running Locally

The frontend is not deployed on OpenShift — it runs locally via Streamlit.

```bash
# 1. Install dependencies
pip install -r components/10-frontend/requirements.txt

# 2. Set the router URL (your cluster's external route)
export ROUTER_URL=https://router-service-<NS_SERVICES>.<CLUSTER_DOMAIN>

# 3. Start the UI
streamlit run components/10-frontend/src/chat_app.py
```

## UI Testing

Once the app opens in your browser:
1. Verify the sidebar shows the default user email (`jessica.thompson@example.com`)
2. Click **"Check my data usage"** — sends a predefined intent, bypassing BERT classification
3. Verify a response appears with tool call indicators (usage data from MCP)
4. Type a free-text message like *"Compare plans for me"* — goes through BERT classification
5. Verify the response includes plan recommendations from the agent

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `ROUTER_URL` | Router service route URL | Router's external OpenShift route (must be set) |
| `DEFAULT_USER_EMAIL` | `jessica.thompson@example.com` | Default user for chat |
| `REQUEST_TIMEOUT` | `120` | HTTP request timeout in seconds |

## Connections

- **09-router** — All chat messages are sent to the router's `/chat` endpoint
