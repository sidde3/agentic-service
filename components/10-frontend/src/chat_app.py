"""
Chat Interface for Intent Classifier Router

Streamlit app that connects to the router's POST /chat endpoint.
Supports:
  - Free-text messages (BERT semantic classification)
  - Select buttons (fast-path with predefined_intent)
  - Multi-turn sessions with persistent session_id
  - Visual display of intent, backend_data, and tool calls
"""

import os
import uuid

import httpx
import streamlit as st

ROUTER_URL = os.getenv(
    "ROUTER_URL",
    "http://router-service:8000",
)
DEFAULT_USER_EMAIL = os.getenv("DEFAULT_USER_EMAIL", "jessica.thompson@example.com")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))

# ── Page config ───────────────────────────────────────────────────────

st.set_page_config(
    page_title="Chat Assistant",
    page_icon="💬",
    layout="centered",
)

st.markdown("""
<style>
    .stChatMessage { max-width: 100%; }
    div[data-testid="stStatusWidget"] { display: none; }
    .intent-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .intent-agent { background: #dbeafe; color: #1e40af; }
    .intent-stub  { background: #f3f4f6; color: #374151; }
    .intent-error { background: #fee2e2; color: #991b1b; }
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_email" not in st.session_state:
    st.session_state.user_email = DEFAULT_USER_EMAIL
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "pending_intent" not in st.session_state:
    st.session_state.pending_intent = None
if "pending_payload" not in st.session_state:
    st.session_state.pending_payload = None


# ── Router API call ───────────────────────────────────────────────────

def call_router(message: str, predefined_intent: str = None) -> dict:
    payload = {
        "user_id": st.session_state.user_email,
        "message": message,
        "session_id": st.session_state.session_id,
    }
    if predefined_intent:
        payload["predefined_intent"] = predefined_intent

    with httpx.Client(verify=False, timeout=REQUEST_TIMEOUT) as client:
        resp = client.post(f"{ROUTER_URL}/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if data.get("user_info") and not st.session_state.user_info:
            st.session_state.user_info = data["user_info"]
        return data


# ── Sidebar ───────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Settings")

    st.session_state.user_email = st.text_input("Email", value=st.session_state.user_email)

    if st.session_state.user_info:
        ui = st.session_state.user_info
        st.markdown(f"**User:** {ui.get('display_name', 'N/A')}")
        st.markdown(f"**Plan:** {ui.get('plan_name', 'N/A')}")
        st.markdown(f"**Mobile:** {ui.get('mobile_number', 'N/A')}")

    st.markdown(f"**Session:** `{st.session_state.session_id[:12]}...`")

    if st.button("🔄 New Session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.user_info = None
        st.session_state.pending_intent = None
        st.session_state.pending_payload = None
        st.rerun()

    st.divider()
    st.markdown("**Quick Actions (Fast Path)**")

    quick_actions = [
        ("📊 Compare Data Plans", "MOBILE_USAGE_COMPARE_DATA_PLAN"),
        ("📈 Check My Usage", "MOBILE_USAGE_CHECK_DATA_CURRENT"),
        ("📱 SIM Activation (Postpaid)", "MOBILE_SIM_ACTIVATION_POSTPAID"),
        ("📱 SIM Activation (Prepaid)", "MOBILE_SIM_ACTIVATION_PREPAID"),
        ("💳 Check Billing", "MOBILE_BILLING_CHECK_DUE_DATE"),
        ("🌐 Network Issues", "MOBILE_NETWORK_CHECK_NO_SIGNAL"),
    ]

    for label, intent in quick_actions:
        if st.button(label, key=f"quick_{intent}", use_container_width=True):
            st.session_state.pending_intent = intent
            st.session_state.pending_payload = label
            st.rerun()

    st.divider()
    st.caption("Powered by BERT + Llama Stack + pgvector")


# ── Chat display ──────────────────────────────────────────────────────

st.title("💬 Chat Assistant")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant" and msg.get("metadata"):
            meta = msg["metadata"]
            intent = meta.get("intent", "")

            if "USAGE_COMPARE" in intent or "USAGE_CHECK" in intent:
                badge_class = "intent-agent"
            elif intent in ("UNKNOWN", "SYSTEM_ERROR"):
                badge_class = "intent-error"
            else:
                badge_class = "intent-stub"

            st.markdown(
                f'<span class="intent-badge {badge_class}">{intent}</span>',
                unsafe_allow_html=True,
            )

            tool_calls = meta.get("tool_calls", [])
            if tool_calls:
                st.caption(f"🔧 Tools: {', '.join(tool_calls)}")

            bd = meta.get("backend_data")
            if bd and isinstance(bd, dict):
                bd_type = bd.get("type", "")

                if bd_type == "select":
                    cols = st.columns(len(bd.get("options", [])))
                    for i, opt in enumerate(bd.get("options", [])):
                        with cols[i]:
                            if st.button(
                                opt.get("title", "Option"),
                                key=f"sel_{msg.get('ts', '')}_{i}",
                                use_container_width=True,
                            ):
                                st.session_state.pending_intent = opt.get("predefined_intent")
                                st.session_state.pending_payload = opt.get("payload", opt.get("title"))
                                st.rerun()

                elif bd_type == "action_link":
                    url = bd.get("url", "#")
                    st.markdown(f"🔗 [Open Self-Service]({url})")


# ── Handle pending button click ───────────────────────────────────────

if st.session_state.pending_intent:
    intent = st.session_state.pending_intent
    payload = st.session_state.pending_payload or intent
    st.session_state.pending_intent = None
    st.session_state.pending_payload = None

    st.session_state.messages.append({"role": "user", "content": payload})

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            try:
                result = call_router(payload, predefined_intent=intent)
                reply = result.get("reply", "")
                bd = result.get("backend_data")
                resolved_intent = result.get("intent", "")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": reply,
                    "ts": str(uuid.uuid4())[:8],
                    "metadata": {
                        "intent": resolved_intent,
                        "backend_data": bd,
                        "tool_calls": bd.get("tool_calls", []) if isinstance(bd, dict) else [],
                    },
                })
            except Exception as e:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Error: {e}",
                    "ts": str(uuid.uuid4())[:8],
                    "metadata": {"intent": "SYSTEM_ERROR"},
                })

    st.rerun()


# ── Chat input ────────────────────────────────────────────────────────

if prompt := st.chat_input("Type your message..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Classifying intent and generating response..."):
            try:
                result = call_router(prompt)
                reply = result.get("reply", "")
                bd = result.get("backend_data")
                resolved_intent = result.get("intent", "")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": reply,
                    "ts": str(uuid.uuid4())[:8],
                    "metadata": {
                        "intent": resolved_intent,
                        "backend_data": bd,
                        "tool_calls": bd.get("tool_calls", []) if isinstance(bd, dict) else [],
                    },
                })
            except Exception as e:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Error: {e}",
                    "ts": str(uuid.uuid4())[:8],
                    "metadata": {"intent": "SYSTEM_ERROR"},
                })

    st.rerun()
