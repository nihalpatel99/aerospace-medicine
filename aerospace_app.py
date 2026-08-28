"""Streamlit console for the aerospace-medicine Azure AI Foundry agent."""

import json
import os

import streamlit as st
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
AGENT_NAME = os.getenv("AGENT_NAME")

USER_AVATAR = "🧑‍✈️"
ASSISTANT_AVATAR = "🩺"

CSS = """
<style>
#MainMenu, footer { visibility: hidden; }

.block-container {
    padding-top: 2.25rem;
    padding-bottom: 3rem;
    max-width: 880px;
}

[data-testid="stChatMessage"] {
    border-radius: 14px;
    margin-bottom: 0.35rem;
}

.app-header {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    margin-bottom: 0.1rem;
}
.app-header .icon {
    font-size: 1.9rem;
    line-height: 1;
}
.app-header h1 {
    margin: 0;
    font-size: 1.55rem;
    font-weight: 700;
    letter-spacing: -0.01em;
}
.app-subtitle {
    color: #9CA9B7;
    font-size: 0.92rem;
    margin: 0.15rem 0 1.4rem 0;
}

.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.76rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    padding: 3px 10px 3px 8px;
    border-radius: 999px;
    background: rgba(46, 213, 115, 0.12);
    color: #2ED573;
    border: 1px solid rgba(46, 213, 115, 0.35);
}
.status-pill.offline {
    background: rgba(255, 82, 82, 0.12);
    color: #FF6B6B;
    border-color: rgba(255, 82, 82, 0.35);
}
.status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 6px currentColor;
}

.sidebar-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6B7A8A;
    margin-bottom: 0.15rem;
}
.sidebar-value {
    font-size: 0.86rem;
    font-family: "SFMono-Regular", Consolas, monospace;
    color: #E8EDF2;
    margin-bottom: 0.75rem;
    word-break: break-all;
}

.disclaimer {
    font-size: 0.78rem;
    color: #6B7A8A;
    line-height: 1.4;
}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def init_session_state():
    defaults = {
        "messages": [],
        "conversation_id": None,
        "pending_approvals": [],
        "awaiting_approval": False,
        "error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


@st.cache_resource(show_spinner=False)
def get_clients(endpoint: str, agent_name: str):
    credential = DefaultAzureCredential(
        exclude_environment_credential=True,
        exclude_managed_identity_credential=True,
    )
    project_client = AIProjectClient(credential=credential, endpoint=endpoint)
    openai_client = project_client.get_openai_client()
    agent = project_client.agents.get(agent_name=agent_name)
    return openai_client, agent


def new_conversation(openai_client):
    conversation = openai_client.conversations.create(items=[])
    st.session_state.conversation_id = conversation.id
    st.session_state.messages = []
    st.session_state.pending_approvals = []
    st.session_state.awaiting_approval = False


def handle_response(response):
    approval_requests = [
        item
        for item in (getattr(response, "output", None) or [])
        if getattr(item, "type", None) == "mcp_approval_request"
    ]

    if approval_requests:
        pending = []
        for req in approval_requests:
            try:
                args_str = json.dumps(json.loads(req.arguments), indent=2)
            except Exception:
                args_str = req.arguments
            pending.append(
                {
                    "id": req.id,
                    "name": req.name,
                    "server_label": getattr(req, "server_label", "unknown"),
                    "arguments": args_str,
                }
            )
        st.session_state.pending_approvals = pending
        st.session_state.awaiting_approval = True
        return

    st.session_state.awaiting_approval = False
    text = getattr(response, "output_text", None)
    citations = getattr(response, "citations", None) or []

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": text if text else "_No response received._",
            "citations": [getattr(c, "content", "Knowledge base") for c in citations],
        }
    )


def call_agent(openai_client, agent):
    response = openai_client.responses.create(
        conversation=st.session_state.conversation_id,
        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
        input="",
    )
    handle_response(response)


def send_message(openai_client, agent, user_message: str):
    st.session_state.messages.append(
        {"role": "user", "content": user_message, "citations": []}
    )
    openai_client.conversations.items.create(
        conversation_id=st.session_state.conversation_id,
        items=[{"type": "message", "role": "user", "content": user_message}],
    )
    call_agent(openai_client, agent)


def submit_approvals(openai_client, agent, decisions: dict):
    approval_items = [
        {
            "type": "mcp_approval_response",
            "approval_request_id": request_id,
            "approve": approved,
        }
        for request_id, approved in decisions.items()
    ]
    openai_client.conversations.items.create(
        conversation_id=st.session_state.conversation_id,
        items=approval_items,
    )
    st.session_state.pending_approvals = []
    call_agent(openai_client, agent)


def render_setup_instructions():
    st.markdown(
        '<div class="app-header"><span class="icon">🛩️</span>'
        "<h1>Aerospace Medicine Assistant</h1></div>",
        unsafe_allow_html=True,
    )
    st.error("Configuration missing — the agent isn't set up yet.")
    st.markdown(
        "Create a `.env` file in the project root with:\n"
        "```\nPROJECT_ENDPOINT=<your Azure AI Foundry project endpoint>\n"
        "AGENT_NAME=<your agent name>\n```"
    )


def render_connection_error(exc: Exception):
    st.markdown(
        '<div class="app-header"><span class="icon">🛩️</span>'
        "<h1>Aerospace Medicine Assistant</h1></div>",
        unsafe_allow_html=True,
    )
    st.error("Couldn't connect to the Azure AI Foundry project.")
    st.markdown(
        "This usually means the Azure credential chain couldn't authenticate, "
        "the project endpoint is wrong, or the agent name doesn't exist in this project."
    )
    with st.expander("Error details"):
        st.code(str(exc))


def render_sidebar(agent):
    with st.sidebar:
        st.markdown(
            '<div class="app-header"><span class="icon">🛩️</span>'
            "<h1 style='font-size:1.2rem;'>Mission Control</h1></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<span class="status-pill"><span class="status-dot"></span>Connected</span>',
            unsafe_allow_html=True,
        )
        st.divider()

        st.markdown('<div class="sidebar-label">Agent</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sidebar-value">{agent.name}</div>', unsafe_allow_html=True)

        endpoint_host = (PROJECT_ENDPOINT or "").split("//")[-1].split("/")[0]
        st.markdown('<div class="sidebar-label">Project</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sidebar-value">{endpoint_host}</div>', unsafe_allow_html=True)

        if st.session_state.conversation_id:
            st.markdown('<div class="sidebar-label">Conversation</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="sidebar-value">{st.session_state.conversation_id[:18]}…</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        if st.button("New conversation", use_container_width=True, icon="🔄"):
            st.session_state.pop("_new_conv_trigger", None)
            st.session_state["_start_new_conversation"] = True
            st.rerun()

        st.divider()
        st.markdown(
            '<p class="disclaimer">For education and reference only. '
            "Not a substitute for a certified aviation medical examiner.</p>",
            unsafe_allow_html=True,
        )


def render_header():
    st.markdown(
        '<div class="app-header"><span class="icon">🛩️</span>'
        "<h1>Aerospace Medicine Assistant</h1></div>"
        '<p class="app-subtitle">Ask about pilot health, fatigue, and aeromedical '
        "standards — grounded in your agent's knowledge base.</p>",
        unsafe_allow_html=True,
    )


def render_error_banner():
    if st.session_state.error:
        col1, col2 = st.columns([6, 1])
        with col1:
            st.error(st.session_state.error)
        with col2:
            if st.button("Dismiss", use_container_width=True):
                st.session_state.error = None
                st.rerun()


def render_chat_history():
    for message in st.session_state.messages:
        avatar = USER_AVATAR if message["role"] == "user" else ASSISTANT_AVATAR
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])
            if message.get("citations"):
                with st.expander(f"Sources ({len(message['citations'])})"):
                    for citation in message["citations"]:
                        st.markdown(f"- {citation}")

    if not st.session_state.messages and not st.session_state.awaiting_approval:
        st.info(
            "Ask a question to get started — for example, "
            '"What are the FAA fatigue rules for long-haul crews?"'
        )


def render_approval_ui(openai_client, agent):
    st.warning(
        "The agent wants to run a tool that requires your approval before it can continue."
    )
    with st.form("approval_form"):
        decisions = {}
        for request in st.session_state.pending_approvals:
            with st.container(border=True):
                st.markdown(f"**Tool:** `{request['name']}`")
                st.markdown(f"**Server:** `{request['server_label']}`")
                st.code(request["arguments"], language="json")
                choice = st.radio(
                    "Decision",
                    options=["Deny", "Approve"],
                    index=0,
                    horizontal=True,
                    key=f"approval_choice_{request['id']}",
                    label_visibility="collapsed",
                )
                decisions[request["id"]] = choice == "Approve"
        submitted = st.form_submit_button("Submit decision", type="primary")

    if submitted:
        with st.spinner("Sending your decision to the agent…"):
            try:
                submit_approvals(openai_client, agent, decisions)
            except Exception as exc:
                st.session_state.error = f"Failed to submit approval: {exc}"
        st.rerun()


def render_chat_input(openai_client, agent):
    prompt = st.chat_input("Ask about pilot health, fatigue, or aerospace medicine…")
    if prompt:
        with st.spinner("Thinking…"):
            try:
                send_message(openai_client, agent, prompt)
            except Exception as exc:
                st.session_state.error = f"Failed to get a response: {exc}"
        st.rerun()


def main():
    st.set_page_config(
        page_title="Aerospace Medicine Assistant",
        page_icon="🛩️",
        layout="centered",
    )
    inject_css()
    init_session_state()

    if not PROJECT_ENDPOINT or not AGENT_NAME:
        render_setup_instructions()
        st.stop()

    try:
        with st.spinner("Connecting to Azure AI Foundry…"):
            openai_client, agent = get_clients(PROJECT_ENDPOINT, AGENT_NAME)
    except Exception as exc:
        render_connection_error(exc)
        st.stop()

    if st.session_state.pop("_start_new_conversation", False):
        try:
            new_conversation(openai_client)
        except Exception as exc:
            st.session_state.error = f"Couldn't start a new conversation: {exc}"

    if st.session_state.conversation_id is None:
        try:
            new_conversation(openai_client)
        except Exception as exc:
            st.session_state.error = f"Couldn't start a conversation: {exc}"

    render_sidebar(agent)
    render_header()
    render_error_banner()
    render_chat_history()

    if st.session_state.awaiting_approval:
        render_approval_ui(openai_client, agent)
    else:
        render_chat_input(openai_client, agent)


if __name__ == "__main__":
    main()
