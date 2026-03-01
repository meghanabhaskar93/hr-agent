"""
HR Agent - Enterprise HR Assistant
A professional LangGraph-powered HR chatbot with Langfuse observability.
"""

import streamlit as st
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from hr_agent.seed import seed_if_needed
from hr_agent.agent.langgraph_agent import HRAgentLangGraph
from hr_agent.repositories.employee import EmployeeRepository

# Seed database if needed
seed_if_needed()

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="HR Assistant | ACME Corp",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "# HR Assistant\nPowered by LangGraph & LangChain"},
)

# ============================================================================
# ENTERPRISE CSS STYLING
# ============================================================================

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        --primary-color: #0066CC;
        --primary-dark: #004C99;
        --primary-light: #E6F0FF;
        --secondary-color: #2D3748;
        --accent-color: #00A86B;
        --warning-color: #F59E0B;
        --error-color: #DC2626;
        --background-color: #F8FAFC;
        --card-background: #FFFFFF;
        --border-color: #E2E8F0;
        --text-primary: #1A202C;
        --text-secondary: #64748B;
        --text-muted: #94A3B8;
    }

    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: var(--background-color);
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* Keep Streamlit header visible so the collapsed-sidebar toggle remains accessible. */
    header {visibility: visible;}

    .main .block-container {
        padding: 2rem 3rem;
        max-width: 1400px;
    }

    .enterprise-header {
        background: linear-gradient(135deg, #0066CC 0%, #004C99 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 102, 204, 0.1), 0 2px 4px -1px rgba(0, 102, 204, 0.06);
    }

    .enterprise-header h1 {
        margin: 0;
        font-size: 1.75rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .enterprise-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 0.95rem;
    }

    section[data-testid="stSidebar"] {
        background-color: var(--card-background);
        border-right: 1px solid var(--border-color);
    }

    section[data-testid="stSidebar"] > div {
        padding: 1.5rem 1rem;
    }

    .user-profile-card {
        background: linear-gradient(135deg, #F8FAFC 0%, #EDF2F7 100%);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1.5rem;
    }

    .user-profile-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }

    .user-avatar {
        width: 48px;
        height: 48px;
        background: linear-gradient(135deg, #0066CC 0%, #004C99 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
        font-size: 1.1rem;
    }

    .user-info h3 {
        margin: 0;
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .user-info p {
        margin: 0.25rem 0 0 0;
        font-size: 0.85rem;
        color: var(--text-secondary);
    }

    .user-details {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.75rem;
        font-size: 0.8rem;
    }

    .user-detail-item {
        display: flex;
        flex-direction: column;
    }

    .user-detail-label {
        color: var(--text-muted);
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .user-detail-value {
        color: var(--text-primary);
        font-weight: 500;
    }

    .quick-actions-header {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        margin-bottom: 0.75rem;
        font-weight: 600;
    }

    .stButton > button {
        background-color: var(--card-background);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        color: var(--text-primary);
        font-size: 0.85rem;
        font-weight: 500;
        padding: 0.6rem 1rem;
        transition: all 0.2s ease;
        text-align: left;
    }

    .stButton > button:hover {
        background-color: var(--primary-light);
        border-color: var(--primary-color);
        color: var(--primary-color);
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0, 102, 204, 0.1);
    }

    .chat-container {
        background-color: var(--card-background);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }

    .stChatMessage {
        background-color: transparent !important;
        border: none !important;
        padding: 1rem 0 !important;
    }

    [data-testid="stChatMessageContent"] {
        background-color: var(--background-color) !important;
        border-radius: 12px !important;
        padding: 1rem 1.25rem !important;
        border: 1px solid var(--border-color) !important;
    }

    [data-testid="stChatMessageContent"][class*="user"] {
        background-color: var(--primary-light) !important;
        border-color: #CCE0FF !important;
    }

    .stChatInput {
        border-radius: 12px;
    }

    .stChatInput > div {
        border-radius: 12px;
        border: 2px solid var(--border-color);
        background-color: var(--card-background);
    }

    .stChatInput > div:focus-within {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1);
    }

    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
    }

    .status-online {
        background-color: #D1FAE5;
        color: #065F46;
    }

    .status-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background-color: currentColor;
    }

    .divider {
        height: 1px;
        background-color: var(--border-color);
        margin: 1.5rem 0;
    }

    .section-header {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        margin-bottom: 1rem;
        font-weight: 600;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border-color);
    }

    .enterprise-footer {
        text-align: center;
        padding: 1.5rem;
        color: var(--text-muted);
        font-size: 0.8rem;
        border-top: 1px solid var(--border-color);
        margin-top: 2rem;
    }

    .stSelectbox > div > div {
        background-color: var(--card-background);
        border-color: var(--border-color);
        border-radius: 8px;
    }

    .stSpinner > div {
        border-color: var(--primary-color) transparent transparent transparent;
    }

    .welcome-message {
        background: linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 100%);
        border: 1px solid #BAE6FD;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }

    .welcome-message h3 {
        margin: 0 0 0.5rem 0;
        color: var(--primary-dark);
        font-size: 1.1rem;
    }

    .welcome-message p {
        margin: 0;
        color: var(--text-secondary);
        font-size: 0.9rem;
    }

    .capability-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1rem;
    }

    .capability-tag {
        background-color: white;
        border: 1px solid #BAE6FD;
        border-radius: 6px;
        padding: 0.375rem 0.75rem;
        font-size: 0.8rem;
        color: var(--primary-color);
    }

    .empty-state {
        border: 1px dashed var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        background: linear-gradient(135deg, #F8FAFC 0%, #EEF2FF 100%);
        color: var(--text-secondary);
    }

    .empty-state h3 {
        margin: 0 0 0.5rem 0;
        color: var(--primary-dark);
        font-size: 1.05rem;
    }

    .empty-state p {
        margin: 0.25rem 0 0 0;
        font-size: 0.9rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

_employee_repo = None


def _get_employee_repo() -> EmployeeRepository:
    global _employee_repo
    if _employee_repo is None:
        _employee_repo = EmployeeRepository()
    return _employee_repo


def get_user_initials(name: str) -> str:
    """Extract initials from a name."""
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    return name[0:2].upper()


def calculate_tenure(hire_date: str) -> str:
    """Calculate tenure from hire date."""
    try:
        hire = datetime.strptime(hire_date, "%Y-%m-%d")
        today = datetime.now()
        years = (today - hire).days // 365
        months = ((today - hire).days % 365) // 30
        if years > 0:
            return f"{years}y {months}m"
        return f"{months} months"
    except (ValueError, TypeError):
        return "N/A"


# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    # Logo and branding
    st.markdown(
        """
    <div style="text-align: center; padding: 1rem 0 1.5rem 0;">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🏢</div>
        <div style="font-size: 1.25rem; font-weight: 700; color: #1A202C;">ACME Corp</div>
        <div style="font-size: 0.8rem; color: #64748B;">HR Assistant Portal</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # User selection
    st.markdown(
        '<div class="section-header">👤 Switch User</div>', unsafe_allow_html=True
    )

    repo = _get_employee_repo()
    employees = repo.list_all_for_dropdown()
    employee_options = {
        f"{e['legal_name']} • {e['title']}": e["email"] for e in employees
    }

    # Find default selection
    default_idx = 0
    for idx, key in enumerate(employee_options.keys()):
        if "Alex Kim" in key:
            default_idx = idx
            break

    selected_employee = st.selectbox(
        "Select Employee",
        options=list(employee_options.keys()),
        index=default_idx,
        label_visibility="collapsed",
    )

    current_email = employee_options[selected_employee]

    # User profile card
    emp_details = repo.get_details_with_manager(current_email)

    if emp_details:
        name = emp_details["legal_name"]
        preferred_name = emp_details["preferred_name"]
        title = emp_details["title"]
        dept = emp_details["department"]
        location = emp_details["location"]
        hire_date = emp_details["hire_date"]
        manager = emp_details["manager_name"]
        display_name = preferred_name or name.split()[0]
        initials = get_user_initials(name)
        tenure = calculate_tenure(hire_date)

        st.markdown(
            f"""
        <div class="user-profile-card">
            <div class="user-profile-header">
                <div class="user-avatar">{initials}</div>
                <div class="user-info">
                    <h3>{name}</h3>
                    <p>{title}</p>
                </div>
            </div>
            <div class="user-details">
                <div class="user-detail-item">
                    <span class="user-detail-label">Department</span>
                    <span class="user-detail-value">{dept}</span>
                </div>
                <div class="user-detail-item">
                    <span class="user-detail-label">Location</span>
                    <span class="user-detail-value">{location}</span>
                </div>
                <div class="user-detail-item">
                    <span class="user-detail-label">Tenure</span>
                    <span class="user-detail-value">{tenure}</span>
                </div>
                <div class="user-detail-item">
                    <span class="user-detail-label">Manager</span>
                    <span class="user-detail-value">{manager or 'None'}</span>
                </div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Quick actions
    st.markdown(
        '<div class="section-header">⚡ Quick Actions</div>', unsafe_allow_html=True
    )

    quick_actions = {
        "📊 My Info": [
            ("What's my holiday balance?", "🏖️"),
            ("What's my current salary?", "💰"),
            ("How long have I been here?", "📅"),
        ],
        "👥 Team": [
            ("Who is my manager?", "👤"),
            ("Who are my teammates?", "👥"),
            ("Show org chart", "🏢"),
        ],
        "📋 Company": [
            ("What's the remote work policy?", "🏠"),
            ("Upcoming company events?", "📆"),
            ("Company holidays this year?", "🎉"),
        ],
    }

    for category, actions in quick_actions.items():
        with st.expander(category, expanded=False):
            for question, icon in actions:
                if st.button(
                    f"{icon} {question}", key=f"q_{question}", use_container_width=True
                ):
                    st.session_state.quick_question = question

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Session controls
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear", use_container_width=True, help="Clear chat history"):
            st.session_state.messages = []
            st.session_state.agent = None
            st.rerun()
    with col2:
        if st.button("🔄 Reset", use_container_width=True, help="Reset session"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # Status indicator
    st.markdown(
        """
    <div style="margin-top: 2rem; text-align: center;">
        <span class="status-badge status-online">
            <span class="status-dot"></span>
            System Online
        </span>
    </div>
    """,
        unsafe_allow_html=True,
    )

# ============================================================================
# MAIN CONTENT
# ============================================================================

# Header
greeting_name = ""
if emp_details:
    greeting_name = (
        emp_details["preferred_name"] or emp_details["legal_name"].split()[0]
    )

st.markdown(
    f"""
<div class="enterprise-header">
    <h1>🤖 HR Assistant</h1>
    <p>Hello, {greeting_name or 'there'}! I'm here to help with HR questions, time-off requests, policies, and more.</p>
</div>
""",
    unsafe_allow_html=True,
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if (
    "agent" not in st.session_state
    or st.session_state.get("current_email") != current_email
):
    st.session_state.agent = HRAgentLangGraph(current_email)
    st.session_state.current_email = current_email
    st.session_state.messages = []

# Chat container
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

# Welcome message when no chat history
if not st.session_state.messages:
    st.markdown(
        """
    <div class="empty-state">
        <h3>👋 Welcome to HR Assistant</h3>
        <p>Ask about time off, compensation, team info, policies, or company events.</p>
        <p>Try: "What's my holiday balance?" • "Who is my manager?" • "Remote work policy"</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(
        message["role"], avatar="👤" if message["role"] == "user" else "🤖"
    ):
        st.markdown(message["content"])

# Handle quick question
if "quick_question" in st.session_state:
    prompt = st.session_state.quick_question
    del st.session_state.quick_question

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Processing your request..."):
            response = st.session_state.agent.chat(prompt)
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# Chat input
if prompt := st.chat_input("Type your question here...", key="chat_input"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Processing your request..."):
            response = st.session_state.agent.chat(prompt)
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

# Footer
st.markdown(
    """
<div class="enterprise-footer">
    <div style="margin-bottom: 0.5rem;">
        <strong>HR Assistant</strong> • Powered by LangGraph & LangChain
    </div>
    <div>
        © 2026 ACME Corporation • Internal Use Only
    </div>
</div>
""",
    unsafe_allow_html=True,
)
