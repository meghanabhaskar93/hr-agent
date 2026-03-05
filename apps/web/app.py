"""
PingHR - 3-rail Streamlit UI with session memory and HR escalation panel.
"""

from __future__ import annotations

from datetime import datetime
import html
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv

from hr_agent.agent.langgraph_agent import HRAgentLangGraph
from hr_agent.repositories.employee import EmployeeRepository
from hr_agent.seed import seed_if_needed
from hr_agent.services.base import get_employee_service, get_escalation_service

load_dotenv()

# Ensure database schema/data exist.
seed_if_needed()

st.set_page_config(
    page_title="PingHR",
    page_icon="P",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================================
# THEME
# ============================================================================

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght@400');

    html {
        font-size: 85%;
    }

    :root {
        --bg: #f5f7fb;
        --panel: #ffffff;
        --line: #dde4ee;
        --text: #22314a;
        --muted: #7a8ea8;
        --brand: #f5a623;
        --brand-soft: #fff6e6;
        --blue: #2a9fd6;
        --green: #1fa971;
        --danger: #df4c5f;
        --tile-a: #fff9ef;
        --tile-b: #f1fbf6;
        --tile-c: #f4f9ff;
        --tile-d: #fff8f0;
        --tile-e: #fff4f7;
        --tile-f: #f1fcfa;
        --tile-g: #f7f3ff;
        --tile-h: #fffaf0;
    }

    .stApp {
        font-family: 'Inter', sans-serif;
        background: #f4f6fb;
        color: var(--text);
        font-size: 13px;
    }

    [data-testid="stHeader"],
    #MainMenu,
    footer {
        visibility: hidden;
        height: 0;
    }

    .main .block-container {
        max-width: 1800px;
        padding: 0.45rem 0.55rem 0.55rem;
    }

    div[data-testid="stVerticalBlock"] > div:has(> .rail-shell) {
        min-height: calc(100vh - 2rem);
    }

    .rail-shell {
        border: 1px solid var(--line);
        border-radius: 16px;
        overflow: hidden;
        background: var(--panel);
    }

    .rail-title {
        font-weight: 600;
        font-size: 0.95rem;
        color: var(--text);
        margin: 0 0 0.25rem 0;
    }

    .rail-subtitle {
        margin: 0.35rem 0 0.55rem 0;
        color: var(--muted);
        font-size: 0.8rem;
    }

    .panel-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 2.9rem;
        height: 2.9rem;
        box-sizing: border-box;
        padding: 0 0.14rem;
        background: #ffffff;
    }

    .panel-top-btn {
        padding: 0.1rem 0.12rem;
    }

    .panel-divider {
        border-top: 1px solid var(--line);
        margin: 0 0 0.65rem 0;
    }

    .global-top-divider {
        border-top: 1px solid var(--line);
        margin: 0 0 0.62rem;
    }

    .top-center-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--text);
        margin: 0;
        line-height: 1.2;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .top-center-bar {
        gap: 0.6rem;
        width: 100%;
    }

    .top-requests-link {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        text-decoration: none !important;
        border: 1px solid #f0ca7e;
        border-radius: 10px;
        background: #fff6e6;
        color: #c7830f;
        font-size: 0.86rem;
        font-weight: 600;
        padding: 0.38rem 0.88rem;
        white-space: nowrap;
        line-height: 1;
    }

    .left-head {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        padding: 0;
        font-size: 1.16rem;
        font-weight: 600;
        color: var(--text);
    }

    .logo-box {
        width: 34px;
        height: 34px;
        border: 1px solid #efc35f;
        border-radius: 10px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: #ffe8bb;
        color: #c07c10;
        font-size: 0.9rem;
        font-weight: 700;
    }

    .thin-divider {
        border-top: 1px solid var(--line);
        margin: 0.45rem 0 0.45rem 0;
    }

    .thread-link {
        text-decoration: none !important;
        color: inherit !important;
        display: block;
    }

    .left-col-marker {
        display: none;
    }

    div[data-testid="column"]:has(.left-col-marker) {
        background: #ffffff;
        border-right: 1px solid var(--line);
    }

    .new-convo-gap-top {
        height: 0.2rem;
    }

    .new-convo-gap-bottom {
        height: 0.34rem;
    }

    .thread-card {
        border: 1px solid transparent;
        border-radius: 12px;
        padding: 0.45rem 0.46rem;
        background: transparent;
        margin-bottom: 0.08rem;
        cursor: pointer;
    }

    .thread-card:hover {
        border-color: #d7e2f0;
        background: #f7fbff;
    }

    .thread-row {
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
    }

    .thread-icon {
        font-family: 'Material Symbols Outlined';
        font-size: 1rem;
        color: #94abc4;
        line-height: 1;
        margin-top: 0.05rem;
    }

    .thread-title {
        font-size: 0.84rem;
        font-weight: 500;
        color: #5f7592;
        margin: 0;
        line-height: 1.2;
    }

    .thread-meta {
        margin-top: 0.22rem;
        font-size: 0.72rem;
        color: #88a0bd;
    }

    .thread-active {
        border-color: #d7e2f0;
        background: #f7fbff;
    }

    .profile-footer {
        margin-top: 0.55rem;
        border-top: 1px solid var(--line);
        padding-top: 0.65rem;
    }

    .profile-footer-row {
        display: flex;
        align-items: center;
        gap: 0.7rem;
    }

    .profile-avatar {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        border: 1px solid #efc35f;
        background: #ffe8bb;
        color: #bf7a10;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.9rem;
    }

    .profile-name {
        font-size: 0.83rem;
        font-weight: 500;
        color: #2f425f;
        margin: 0;
        line-height: 1.2;
    }

    .profile-email {
        font-size: 0.72rem;
        color: #88a0bd;
        margin: 0.1rem 0 0 0;
    }

    .rail-close {
        color: #99aac0;
        font-size: 1.25rem;
        font-weight: 400;
        line-height: 1;
    }

    .top-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.08rem 0.1rem 0.2rem;
    }

    .center-title {
        font-size: 0.92rem;
        font-weight: 600;
        color: var(--text);
        margin: 0;
    }

    .center-subtitle {
        margin: 0.15rem 0 0 0;
        color: #8aa0b9;
        font-size: 0.82rem;
    }

    .hero-chip {
        margin: 0.45rem auto;
        width: fit-content;
        border: 1px solid #f0ca7e;
        background: #fff7e8;
        color: #d58a11;
        border-radius: 999px;
        padding: 0.34rem 0.92rem;
        font-size: 0.84rem;
        font-weight: 500;
    }

    .hero-title {
        text-align: center;
        font-size: 2.12rem;
        line-height: 1.12;
        color: #1d2a43;
        margin: 0.45rem 0 0.3rem;
        font-weight: 700;
    }

    .hero-subtitle {
        text-align: center;
        color: #657a96;
        font-size: 1.15rem;
        margin: 0;
        font-weight: 500;
    }

    .hero-note {
        text-align: center;
        color: #8ca0ba;
        margin-top: 0.25rem;
        font-size: 0.95rem;
    }

    .tile-card {
        border-radius: 14px;
        border: 1px solid var(--line);
        padding: 0.72rem 0.88rem;
        margin-bottom: 0.45rem;
    }

    .tile-row {
        display: flex;
        align-items: flex-start;
        gap: 0.55rem;
    }

    .tile-icon {
        font-family: 'Material Symbols Outlined';
        font-size: 1.1rem;
        line-height: 1;
        margin-top: 0.06rem;
        color: #d9840f;
    }

    .tile-title {
        margin: 0;
        font-size: 0.92rem;
        font-weight: 600;
        color: #2f425f;
    }

    .tile-subtitle {
        margin: 0.26rem 0 0 0;
        color: #7f95af;
        font-size: 0.83rem;
    }

    .chat-note {
        text-align: center;
        font-size: 0.74rem;
        color: #8ea1b8;
        margin-top: 0.45rem;
    }

    .user-bubble {
        background: #f8a600;
        color: white;
        border-radius: 16px;
        padding: 1rem 1.1rem;
        font-size: 0.9rem;
        font-weight: 500;
        margin-bottom: 0.7rem;
    }

    .assistant-bubble {
        border: 1px solid #d7dfe9;
        border-radius: 16px;
        padding: 1rem 1.1rem;
        background: #ffffff;
        color: #2f425f;
        font-size: 0.9rem;
    }

    .requests-empty {
        text-align: center;
        color: #8ba0b8;
        border: 1px dashed var(--line);
        border-radius: 12px;
        padding: 1.2rem;
        background: #fbfdff;
        margin-top: 0.8rem;
    }

    .request-row {
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 0.55rem 0.64rem;
        background: #ffffff;
        margin-bottom: 0.4rem;
    }

    .request-title {
        font-size: 0.88rem;
        font-weight: 500;
        color: #2a3e5b;
        margin: 0;
    }

    .request-meta {
        margin-top: 0.22rem;
        color: #87a0bd;
        font-size: 0.76rem;
    }

    .status-pill {
        display: inline-block;
        border-radius: 999px;
        padding: 0.2rem 0.55rem;
        font-size: 0.7rem;
        font-weight: 600;
        border: 1px solid;
        margin-top: 0.35rem;
    }

    .status-pending {
        color: #c77709;
        border-color: #f2cf8f;
        background: #fff8e9;
    }

    .status-in-review {
        color: #0d7db2;
        border-color: #93cde9;
        background: #eef8ff;
    }

    .status-resolved {
        color: #19855c;
        border-color: #9edfc3;
        background: #eefcf4;
    }

    .metric-card {
        border: 1px solid #cfd8e5;
        border-radius: 14px;
        padding: 0.78rem 0.3rem 0.56rem;
        text-align: center;
        background: #f4f8fc;
    }

    .metric-num {
        font-size: 1.2rem;
        font-weight: 700;
        margin: 0 0 0.18rem 0;
    }

    .metric-label {
        margin: 0.08rem 0 0 0;
        color: #8b9fb8;
        font-size: 0.95rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        font-weight: 600;
        white-space: nowrap;
    }

    .stButton > button {
        border-radius: 10px;
        border: 1px solid #d8e1ec;
        color: #3f5576;
        font-weight: 500;
        background: #fbfdff;
        font-size: 0.84rem;
        padding-top: 0.42rem;
        padding-bottom: 0.42rem;
    }

    .stButton > button:hover {
        border-color: #f2c25e;
        color: #bc790f;
        background: #fff9ed;
    }

    div[data-testid="stSelectbox"] > div[data-baseweb="select"] > div {
        border-radius: 12px;
        border: 1px solid #d6e0ec;
        background: #fbfdff;
        min-height: 46px;
    }

    div[data-testid="stSegmentedControl"] > div {
        border: 1px solid transparent;
        border-radius: 10px;
        background: transparent;
        gap: 0.35rem;
    }

    div[data-testid="stSegmentedControl"] label {
        border-radius: 10px !important;
        border: none !important;
        background: transparent !important;
        padding: 0.22rem 0.65rem !important;
        color: #667d98 !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }

    div[data-testid="stSegmentedControl"] label[aria-checked="true"] {
        background: #fff3d9 !important;
        color: #c7830f !important;
        border: 1px solid #f0ca7e !important;
    }

    .chat-input-wrap {
        margin-top: 0.15rem;
    }

    @media (max-width: 1200px) {
        .hero-title { font-size: 1.6rem; }
        .hero-subtitle { font-size: 1.0rem; }
        .hero-note { font-size: 0.85rem; }
    }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================================
# HELPERS
# ============================================================================

_employee_repo: EmployeeRepository | None = None

HOME_TILES = [
    (
        "Leave & Time Off",
        "Annual leave, sick days, parental leave",
        "event_note",
        "var(--tile-a)",
        "What leave policies does Acme offer?",
    ),
    (
        "Payroll & Pay",
        "Pay dates, payslips, expenses",
        "payments",
        "var(--tile-b)",
        "When is payday and how do I access payslips?",
    ),
    (
        "Benefits",
        "Health, pension, gym, perks",
        "favorite",
        "var(--tile-c)",
        "What benefits am I eligible for?",
    ),
    (
        "Company Policy",
        "Remote work, code of conduct, hours",
        "menu_book",
        "var(--tile-d)",
        "What is Acme's remote work policy?",
    ),
    (
        "Onboarding",
        "First day prep, probation, setup",
        "person_add",
        "var(--tile-e)",
        "What are onboarding and probation policies?",
    ),
    (
        "Documents",
        "Letters, payslips, tax forms",
        "description",
        "var(--tile-f)",
        "How do I get employment letters and tax documents?",
    ),
    (
        "Career & Growth",
        "Internal jobs, promotions, reviews",
        "work",
        "var(--tile-g)",
        "How does performance review and promotion work?",
    ),
    (
        "Wellbeing & Support",
        "EAP, mental health, occupational health",
        "health_and_safety",
        "var(--tile-h)",
        "What wellbeing resources does Acme provide?",
    ),
]


def _get_employee_repo() -> EmployeeRepository:
    global _employee_repo
    if _employee_repo is None:
        _employee_repo = EmployeeRepository()
    return _employee_repo


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _short_text(value: str, max_len: int = 58) -> str:
    text = (value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _format_relative(iso_value: str | None) -> str:
    if not iso_value:
        return "just now"
    try:
        dt = datetime.fromisoformat(iso_value)
    except ValueError:
        return "just now"

    delta = datetime.now() - dt
    sec = int(delta.total_seconds())
    if sec < 60:
        return "just now"
    minutes = sec // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days == 1:
        return "1 day ago"
    if days < 7:
        return f"{days} days ago"
    return dt.strftime("%b %d")


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    if parts:
        return parts[0][:2].upper()
    return "U"


def _empty_thread() -> dict:
    now = _now_iso()
    thread_id = str(uuid4())
    return {
        "id": thread_id,
        "title": "New conversation",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }


def _ensure_state_for_user(user_email: str) -> None:
    if "ui_threads_by_user" not in st.session_state:
        st.session_state.ui_threads_by_user = {}
    if "agents_by_thread" not in st.session_state:
        st.session_state.agents_by_thread = {}
    if "show_requests_panel" not in st.session_state:
        st.session_state.show_requests_panel = True
    if "request_filter" not in st.session_state:
        st.session_state.request_filter = "ALL"
    if "queued_prompt" not in st.session_state:
        st.session_state.queued_prompt = None

    store = st.session_state.ui_threads_by_user.get(user_email)
    if not store:
        thread = _empty_thread()
        st.session_state.ui_threads_by_user[user_email] = {
            "active_thread_id": thread["id"],
            "threads": [thread],
        }
        return

    if not store.get("threads"):
        thread = _empty_thread()
        store["threads"] = [thread]
        store["active_thread_id"] = thread["id"]
        return

    active_id = store.get("active_thread_id")
    if not any(t["id"] == active_id for t in store["threads"]):
        store["active_thread_id"] = store["threads"][0]["id"]


def _get_store(user_email: str) -> dict:
    return st.session_state.ui_threads_by_user[user_email]


def _get_active_thread(user_email: str) -> dict:
    store = _get_store(user_email)
    active_id = store["active_thread_id"]
    for thread in store["threads"]:
        if thread["id"] == active_id:
            return thread
    return store["threads"][0]


def _sort_threads(store: dict) -> None:
    store["threads"] = sorted(
        store["threads"],
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )


def _set_active_thread(user_email: str, thread_id: str) -> None:
    _get_store(user_email)["active_thread_id"] = thread_id


def _new_thread(user_email: str) -> str:
    store = _get_store(user_email)
    thread = _empty_thread()
    store["threads"].insert(0, thread)
    store["active_thread_id"] = thread["id"]
    return thread["id"]


def _active_agent(user_email: str, thread_id: str) -> HRAgentLangGraph:
    key = f"{user_email}:{thread_id}"
    agent = st.session_state.agents_by_thread.get(key)
    if agent is None:
        agent = HRAgentLangGraph(user_email=user_email, session_id=f"thread_{thread_id}")
        st.session_state.agents_by_thread[key] = agent
    return agent


def _append_message(thread: dict, role: str, content: str) -> None:
    now = _now_iso()
    thread["messages"].append({"role": role, "content": content, "created_at": now})
    thread["updated_at"] = now
    if role == "user" and thread["title"] == "New conversation":
        thread["title"] = _short_text(content, max_len=42)


def _reset_user_threads(user_email: str) -> None:
    if user_email in st.session_state.ui_threads_by_user:
        st.session_state.ui_threads_by_user[user_email] = {
            "active_thread_id": "",
            "threads": [],
        }
    stale_keys = [
        key for key in st.session_state.agents_by_thread.keys() if key.startswith(f"{user_email}:")
    ]
    for key in stale_keys:
        del st.session_state.agents_by_thread[key]
    _ensure_state_for_user(user_email)


def _status_class(status: str) -> str:
    if status == "IN_REVIEW":
        return "status-in-review"
    if status == "RESOLVED":
        return "status-resolved"
    return "status-pending"


def _process_prompt(user_email: str, thread: dict, prompt: str) -> None:
    _append_message(thread, "user", prompt)
    with st.spinner("Generating response..."):
        response = _active_agent(user_email, thread["id"]).chat(prompt)
    _append_message(thread, "assistant", response)


# ============================================================================
# DATA SETUP
# ============================================================================

repo = _get_employee_repo()
employee_service = get_employee_service()
escalation_service = get_escalation_service()

employees = repo.list_all_for_dropdown()
employee_options = {f"{row['legal_name']} • {row['title']}": row["email"] for row in employees}
employee_labels = list(employee_options.keys())
if not employee_labels:
    st.error("No employees found in seed data.")
    st.stop()

if "selected_employee_label" not in st.session_state:
    default_idx = 0
    for idx, label in enumerate(employee_labels):
        if "Alex Kim" in label:
            default_idx = idx
            break
    st.session_state.selected_employee_label = employee_labels[default_idx]

if st.session_state.selected_employee_label not in employee_labels:
    st.session_state.selected_employee_label = employee_labels[0]

current_label = st.session_state.selected_employee_label
current_email = employee_options[current_label]

_ensure_state_for_user(current_email)
store = _get_store(current_email)

thread_param = st.query_params.get("thread")
if thread_param and any(t["id"] == thread_param for t in store["threads"]):
    store["active_thread_id"] = thread_param

prompt_param = st.query_params.get("prompt")
if prompt_param is not None:
    try:
        tile_idx = int(prompt_param)
        if 0 <= tile_idx < len(HOME_TILES):
            st.session_state.queued_prompt = HOME_TILES[tile_idx][4]
    except ValueError:
        pass
    del st.query_params["prompt"]

toggle_requests_param = st.query_params.get("toggle_requests")
if toggle_requests_param == "1":
    st.session_state.show_requests_panel = not st.session_state.show_requests_panel
    del st.query_params["toggle_requests"]

active_thread = _get_active_thread(current_email)

emp_details = repo.get_details_with_manager(current_email) or {}
requester_context = employee_service.get_requester_context(current_email)
current_role = requester_context.get("role", "EMPLOYEE")
current_employee_id = requester_context.get("employee_id", 0)


# ============================================================================
# LAYOUT
# ============================================================================

if st.session_state.show_requests_panel:
    header_left, header_center, header_right = st.columns([3.0, 10.1, 4.5], gap="xxsmall")
    left_col, center_col, right_col = st.columns([3.0, 10.1, 4.5], gap="xxsmall")
else:
    header_left, header_center = st.columns([3.2, 14.2], gap="xxsmall")
    left_col, center_col = st.columns([3.2, 14.2], gap="xxsmall")
    header_right = None
    right_col = None


with header_left:
    st.markdown(
        """
        <div class="panel-top">
            <div class="left-head">
                <span class="logo-box">P</span>
                <span style="font-size:1.34rem;">PingHR</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with header_center:
    top_title = "PingHR"
    if active_thread["messages"]:
        top_title = f"← {_short_text(active_thread['title'], 70)}"
    safe_top_title = html.escape(top_title)
    st.markdown(
        f"""
        <div class="panel-top top-center-bar">
            <p class="top-center-title">{safe_top_title}</p>
            <a class="top-requests-link" target="_self" href="?thread={active_thread['id']}&toggle_requests=1">🗂️ My Requests</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

if header_right:
    with header_right:
        st.markdown(
            """
            <div class="panel-top">
                <p class="rail-title">My Requests</p>
                <span class="rail-close">×</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown('<div class="global-top-divider"></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# LEFT RAIL
# ---------------------------------------------------------------------------
with left_col:
    st.markdown('<div class="left-col-marker"></div>', unsafe_allow_html=True)
    st.markdown('<div class="new-convo-gap-top"></div>', unsafe_allow_html=True)
    if st.button("＋  New conversation", use_container_width=True, key="new_thread"):
        new_id = _new_thread(current_email)
        st.query_params["thread"] = new_id
        st.rerun()
    st.markdown('<div class="new-convo-gap-bottom"></div>', unsafe_allow_html=True)

    st.markdown('<div class="thin-divider"></div>', unsafe_allow_html=True)

    for thread in store["threads"]:
        is_active = thread["id"] == store["active_thread_id"]
        card_class = "thread-card thread-active" if is_active else "thread-card"
        st.markdown(
            f"""
            <a class="thread-link" target="_self" href="?thread={thread['id']}">
                <div class="{card_class}">
                    <div class="thread-row">
                        <span class="thread-icon">chat_bubble_outline</span>
                        <div>
                            <p class="thread-title">{_short_text(thread['title'], 28)}</p>
                            <div class="thread-meta">● {_format_relative(thread.get('updated_at'))}</div>
                        </div>
                    </div>
                </div>
            </a>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="thin-divider"></div>', unsafe_allow_html=True)

    display_name = emp_details.get("preferred_name") or emp_details.get("legal_name", "User")
    st.markdown(
        f"""
        <div class="profile-footer">
            <div class="profile-footer-row">
                <div class="profile-avatar">{_initials(display_name)}</div>
                <div>
                    <p class="profile-name">{display_name}</p>
                    <p class="profile-email">{current_email}</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# CENTER PANEL
# ---------------------------------------------------------------------------
with center_col:
    if st.session_state.queued_prompt:
        _process_prompt(current_email, active_thread, st.session_state.queued_prompt)
        _sort_threads(store)
        st.session_state.queued_prompt = None
        st.rerun()

    if not active_thread["messages"]:
        first_name = display_name.split()[0] if display_name else "there"
        st.markdown(
            f"""
            <div class="hero-chip">✨ Your HR assistant · Acme Corp</div>
            <h1 class="hero-title">Hi {first_name}, what can I help with?</h1>
            <p class="hero-subtitle">Ask me anything about Acme's HR policies — leave, payroll, benefits, and more.</p>
            <p class="hero-note">Sensitive queries are securely escalated to HR Ops.</p>
            """,
            unsafe_allow_html=True,
        )

        col_a, col_b = st.columns(2, gap="small")
        for idx, (title, subtitle, icon_name, bg_color, _question) in enumerate(HOME_TILES):
            target_col = col_a if idx % 2 == 0 else col_b
            with target_col:
                st.markdown(
                    f"""
                    <a class="thread-link" target="_self" href="?thread={active_thread['id']}&prompt={idx}">
                        <div class="tile-card" style="background:{bg_color};">
                            <div class="tile-row">
                                <span class="tile-icon">{icon_name}</span>
                                <div>
                                    <p class="tile-title">{title}</p>
                                    <p class="tile-subtitle">{subtitle}</p>
                                </div>
                            </div>
                        </div>
                    </a>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        for idx, message in enumerate(active_thread["messages"]):
            if message["role"] == "user":
                st.markdown(
                    f'<div class="user-bubble">{message["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="assistant-bubble">{message["content"]}</div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Escalate to HR",
                    key=f"escalate_msg_{active_thread['id']}_{idx}",
                ):
                    result = escalation_service.create_request(
                        requester_employee_id=current_employee_id,
                        requester_email=current_email,
                        thread_id=active_thread["id"],
                        source_message_excerpt=_short_text(message["content"], 240),
                    )
                    if result.get("success"):
                        st.toast(f"Escalated to HR (#{result['escalation_id']})")
                    else:
                        st.error(result.get("error", "Failed to escalate"))
                    st.rerun()

    st.markdown('<div class="chat-input-wrap"></div>', unsafe_allow_html=True)
    user_prompt = st.chat_input(
        "Ask anything about HR, leave, payroll, benefits...",
        key=f"chat_input_{active_thread['id']}",
    )
    if user_prompt:
        _process_prompt(current_email, active_thread, user_prompt)
        _sort_threads(store)
        st.rerun()

    st.markdown(
        '<div class="chat-note">Confident answers are grounded in policy. Low-confidence queries go to HR Ops.</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# RIGHT RAIL (REQUESTS)
# ---------------------------------------------------------------------------
if right_col and st.session_state.show_requests_panel:
    with right_col:
        counts = escalation_service.list_counts(current_email)
        st.markdown(
            f'<p class="rail-subtitle">{counts["total"]} escalated queries</p>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="height:0.2rem;"></div>', unsafe_allow_html=True)

        m1, m2, m3 = st.columns(3, gap="small")
        with m1:
            st.markdown(
                f"""
                <div class="metric-card">
                    <p class="metric-num" style="color:#e2901f;">{counts['pending']}</p>
                    <p class="metric-label">Pending</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f"""
                <div class="metric-card">
                    <p class="metric-num" style="color:#2098c5;">{counts['in_review']}</p>
                    <p class="metric-label">In Review</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f"""
                <div class="metric-card">
                    <p class="metric-num" style="color:#20a96f;">{counts['resolved']}</p>
                    <p class="metric-label">Resolved</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown('<div style="height:0.35rem;"></div>', unsafe_allow_html=True)

        status_choice = st.segmented_control(
            "Status Filter",
            ["ALL", "PENDING", "IN_REVIEW", "RESOLVED"],
            default=st.session_state.request_filter,
            format_func=lambda s: {
                "ALL": "All",
                "PENDING": "Pending",
                "IN_REVIEW": "In Review",
                "RESOLVED": "Resolved",
            }[s],
            label_visibility="collapsed",
        )
        if status_choice is None:
            status_choice = st.session_state.request_filter
        st.session_state.request_filter = status_choice

        status_filter = None if status_choice == "ALL" else status_choice
        requests = escalation_service.list_requests(
            viewer_email=current_email,
            status=status_filter,
            limit=100,
        )

        if not requests:
            st.markdown(
                """
                <div class="requests-empty">
                    <div style="font-size:1rem;font-weight:600;color:#6f87a3;">No requests found</div>
                    <div style="margin-top:0.2rem;">Escalated queries will appear here</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            can_triage = current_role in {"HR", "MANAGER"}
            for item in requests:
                status = item["status"]
                st.markdown(
                    f"""
                    <div class="request-row">
                        <p class="request-title">#{item['escalation_id']} · {_short_text(item['source_message_excerpt'], 82)}</p>
                        <div class="request-meta">{item['requester_email']} · {_format_relative(item['updated_at'])}</div>
                        <span class="status-pill {_status_class(status)}">{status.replace('_', ' ')}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if can_triage:
                    if status == "PENDING":
                        if st.button(
                            "Move to In Review",
                            key=f"triage_review_{item['escalation_id']}",
                            use_container_width=True,
                        ):
                            result = escalation_service.transition_status(
                                viewer_email=current_email,
                                actor_employee_id=current_employee_id,
                                escalation_id=item["escalation_id"],
                                new_status="IN_REVIEW",
                            )
                            if result.get("success"):
                                st.toast("Request moved to In Review")
                            else:
                                st.error(result.get("error", "Update failed"))
                            st.rerun()
                    elif status == "IN_REVIEW":
                        if st.button(
                            "Mark Resolved",
                            key=f"triage_resolve_{item['escalation_id']}",
                            use_container_width=True,
                        ):
                            result = escalation_service.transition_status(
                                viewer_email=current_email,
                                actor_employee_id=current_employee_id,
                                escalation_id=item["escalation_id"],
                                new_status="RESOLVED",
                            )
                            if result.get("success"):
                                st.toast("Request resolved")
                            else:
                                st.error(result.get("error", "Update failed"))
                            st.rerun()
                    else:
                        if st.button(
                            "Reopen",
                            key=f"triage_reopen_{item['escalation_id']}",
                            use_container_width=True,
                        ):
                            result = escalation_service.transition_status(
                                viewer_email=current_email,
                                actor_employee_id=current_employee_id,
                                escalation_id=item["escalation_id"],
                                new_status="IN_REVIEW",
                            )
                            if result.get("success"):
                                st.toast("Request reopened")
                            else:
                                st.error(result.get("error", "Update failed"))
                            st.rerun()
