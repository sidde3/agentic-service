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

## No Kubernetes Manifests

The frontend runs **locally** via Streamlit:

```bash
streamlit run components/10-frontend/src/chat_app.py
```

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `ROUTER_URL` | `http://localhost:8080` | Router service URL (use the route URL) |
| `DEFAULT_USER_EMAIL` | `jessica.thompson@example.com` | Default user for chat |
| `REQUEST_TIMEOUT` | `120` | HTTP request timeout in seconds |

## Connections

- **09-router** — All chat messages are sent to the router's `/chat` endpoint
