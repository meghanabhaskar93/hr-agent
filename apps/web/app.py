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

_css_version = "v5"  # bump to bust browser cache
st.markdown(
    f"""
<style data-version="{_css_version}">
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL@20..48,100..700,0..1');

    /* ── RESET & GLOBALS ── */
    html {{ font-size: 15px; }}

    :root {{
        --bg: #f0f2f5;
        --panel: #ffffff;
        --sidebar-bg: #f7f8fa;
        --line: #e2e8f0;
        --text: #1e293b;
        --muted: #64748b;
        --brand: #f59e0b;
        --brand-bg: #fffbeb;
        --brand-border: #fde68a;
        --brand-text: #b45309;
        --accent: #3b82f6;
        --green: #10b981;
        --danger: #ef4444;
        --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
        --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05);
        --radius: 12px;
        --header-h: 3.25rem;
        --shell-gap: 1.1rem;
        --chat-w: 44rem;
    }}

    .stApp {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
        background: var(--bg) !important;
        color: var(--text);
        font-size: 0.875rem;
        padding: 0 !important;
        margin: 0 !important;
    }}

    html, body {{
        margin: 0 !important;
        padding: 0 !important;
        overflow-x: hidden;
    }}

    /* ── HIDE STREAMLIT CHROME ── */
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stStatusWidget"],
    [data-testid="stBottom"],
    [data-testid="stDecoration"],
    #MainMenu, footer, header {{
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        max-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }}

    /* ── FULL-BLEED CONTAINER ── */
    [data-testid="stAppViewContainer"] {{
        background: var(--bg) !important;
        padding: 0 !important;
        margin: 0 !important;
    }}

    [data-testid="stAppViewContainer"] > .main {{
        padding: var(--shell-gap) !important;
        margin: 0 !important;
        height: 100vh !important;
        overflow: hidden !important;
        box-sizing: border-box;
    }}

    .main .block-container,
    [data-testid="stMainBlockContainer"] {{
        max-width: none !important;
        width: 100% !important;
        min-height: calc(100vh - (var(--shell-gap) * 2));
        margin: 0 !important;
        padding: 0 !important;
        border: 1px solid var(--line) !important;
        border-radius: 14px !important;
        background: var(--bg) !important;
        overflow: hidden;
        box-shadow: 0 1px 2px rgb(15 23 42 / 0.04);
    }}

    .main .block-container > div[data-testid="stVerticalBlock"],
    [data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"] {{
        gap: 0 !important;
        padding: 0 !important;
        min-height: 100%;
    }}

    [data-testid="stAppViewContainer"] > .main > .block-container {{
        padding-top: 0 !important;
    }}

    /* ── SHELL ROW LAYOUT (ONLY TOP-LEVEL ROWS) ── */
    .main .block-container > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"]:has(.top-left-marker),
    .main .block-container > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"]:has(.left-col-marker),
    [data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"]:has(.top-left-marker),
    [data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"]:has(.left-col-marker) {{
        gap: 0 !important;
        column-gap: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        align-items: stretch;
    }}

    /* ── HIDDEN MARKERS ── */
    .left-col-marker, .center-col-marker, .right-col-marker,
    .top-left-marker, .top-center-marker, .top-right-marker {{
        display: none !important;
    }}

    div[data-testid="stMarkdown"]:has(.left-col-marker),
    div[data-testid="stMarkdownContainer"]:has(.left-col-marker),
    div[data-testid="stMarkdown"]:has(.center-col-marker),
    div[data-testid="stMarkdownContainer"]:has(.center-col-marker),
    div[data-testid="stMarkdown"]:has(.right-col-marker),
    div[data-testid="stMarkdownContainer"]:has(.right-col-marker),
    div[data-testid="stMarkdown"]:has(.top-left-marker),
    div[data-testid="stMarkdownContainer"]:has(.top-left-marker),
    div[data-testid="stMarkdown"]:has(.top-center-marker),
    div[data-testid="stMarkdownContainer"]:has(.top-center-marker),
    div[data-testid="stMarkdown"]:has(.top-right-marker),
    div[data-testid="stMarkdownContainer"]:has(.top-right-marker) {{
        display: none !important;
    }}

    /* ── HEADER ROW ── */
    div[data-testid="stHorizontalBlock"]:has(.top-left-marker) {{
        min-height: var(--header-h);
        height: var(--header-h);
        border-bottom: 1px solid var(--line);
        background: var(--panel);
        box-shadow: var(--shadow-sm);
        position: relative;
        z-index: 10;
    }}

    div[data-testid="stColumn"]:has(.top-left-marker),
    div[data-testid="stColumn"]:has(.top-center-marker),
    div[data-testid="stColumn"]:has(.top-right-marker) {{
        background: var(--panel) !important;
        min-height: var(--header-h);
        overflow: visible;
    }}

    div[data-testid="stColumn"]:has(.top-left-marker) div[data-testid="stMarkdownContainer"]:has(.panel-top),
    div[data-testid="stColumn"]:has(.top-center-marker) div[data-testid="stMarkdownContainer"]:has(.panel-top),
    div[data-testid="stColumn"]:has(.top-right-marker) div[data-testid="stMarkdownContainer"]:has(.panel-top),
    div[data-testid="stColumn"]:has(.top-left-marker) div[data-testid="stMarkdown"]:has(.panel-top),
    div[data-testid="stColumn"]:has(.top-center-marker) div[data-testid="stMarkdown"]:has(.panel-top),
    div[data-testid="stColumn"]:has(.top-right-marker) div[data-testid="stMarkdown"]:has(.panel-top) {{
        margin: 0 !important;
        padding: 0 !important;
        width: 100% !important;
        height: var(--header-h) !important;
    }}

    /* ── COLUMN BACKGROUNDS ── */
    div[data-testid="stColumn"]:has(.left-col-marker) {{
        background: var(--sidebar-bg) !important;
    }}

    div[data-testid="stColumn"]:has(.center-col-marker) {{
        background: var(--bg) !important;
    }}

    div[data-testid="stColumn"]:has(.right-col-marker) {{
        background: var(--panel) !important;
    }}

    /* ── COLUMN BORDERS ── */
    div[data-testid="stColumn"]:has(.top-left-marker),
    div[data-testid="stColumn"]:has(.left-col-marker) {{
        border-right: 1px solid var(--line) !important;
    }}

    div[data-testid="stColumn"]:has(.top-center-marker),
    div[data-testid="stColumn"]:has(.center-col-marker) {{
        border-right: 1px solid var(--line) !important;
    }}

    div[data-testid="stColumn"]:has(.top-right-marker),
    div[data-testid="stColumn"]:has(.right-col-marker),
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-child {{
        border-right: none !important;
    }}

    /* ── COLUMN INNER PADDING ── */
    div[data-testid="stColumn"]:has(.top-left-marker) > div[data-testid="stVerticalBlock"],
    div[data-testid="stColumn"]:has(.top-center-marker) > div[data-testid="stVerticalBlock"],
    div[data-testid="stColumn"]:has(.top-right-marker) > div[data-testid="stVerticalBlock"] {{
        min-height: var(--header-h) !important;
        height: var(--header-h) !important;
        overflow: visible;
        justify-content: center;
    }}

    div[data-testid="stColumn"]:has(.top-center-marker) > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"],
    div[data-testid="stColumn"]:has(.top-right-marker) > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {{
        height: var(--header-h) !important;
        align-items: center !important;
        margin: 0 !important;
    }}

    div[data-testid="stColumn"]:has(.top-center-marker) > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
    div[data-testid="stColumn"]:has(.top-right-marker) > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
        display: flex !important;
        align-items: center !important;
    }}

    div[data-testid="stColumn"]:has(.top-left-marker) > div[data-testid="stVerticalBlock"] {{
        padding: 0 0.7rem;
    }}

    div[data-testid="stColumn"]:has(.left-col-marker) > div[data-testid="stVerticalBlock"] {{
        padding: 0.55rem 0.7rem 0.75rem;
    }}

    div[data-testid="stColumn"]:has(.top-center-marker) > div[data-testid="stVerticalBlock"] {{
        padding: 0 0.95rem;
    }}

    div[data-testid="stColumn"]:has(.center-col-marker) > div[data-testid="stVerticalBlock"] {{
        padding: 0.55rem 1.05rem 0.85rem;
    }}

    div[data-testid="stColumn"]:has(.top-right-marker) > div[data-testid="stVerticalBlock"] {{
        padding: 0 0.85rem;
    }}

    div[data-testid="stColumn"]:has(.right-col-marker) > div[data-testid="stVerticalBlock"] {{
        padding: 0.55rem 0.85rem 0.85rem;
    }}

    /* ── PER-PANEL SCROLLING ── */
    div[data-testid="stColumn"]:has(.left-col-marker) > div[data-testid="stVerticalBlock"],
    div[data-testid="stColumn"]:has(.center-col-marker) > div[data-testid="stVerticalBlock"],
    div[data-testid="stColumn"]:has(.right-col-marker) > div[data-testid="stVerticalBlock"] {{
        max-height: calc(100vh - (var(--shell-gap) * 2) - var(--header-h) - 2px);
        overflow-y: auto;
        overflow-x: hidden;
    }}

    div[data-testid="stColumn"]:has(.left-col-marker) > div[data-testid="stVerticalBlock"] {{
        display: flex;
        flex-direction: column;
    }}

    div[data-testid="stColumn"]:has(.left-col-marker) > div[data-testid="stVerticalBlock"] > div:has(.left-rail-spacer) {{
        flex: 1 1 auto;
        min-height: 0;
    }}

    div[data-testid="stColumn"]:has(.left-col-marker) > div[data-testid="stVerticalBlock"] > div:has(.profile-footer) {{
        position: sticky;
        bottom: 0.35rem;
        z-index: 6;
        margin-top: auto;
        background: var(--sidebar-bg);
    }}

    /* ── PANEL TOP BAR ── */
    .panel-top {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: var(--header-h);
        height: var(--header-h);
        box-sizing: border-box;
        padding: 0 0.75rem;
        background: transparent;
        width: 100%;
    }}

    .global-top-divider {{
        display: none;
    }}

    .post-top-gap {{
        height: 0;
    }}

    /* ── LOGO & LEFT HEAD ── */
    .left-head {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0;
    }}

    .logo-box {{
        width: 30px;
        height: 30px;
        border: none;
        border-radius: 8px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #f59e0b, #d97706);
        color: #ffffff;
        font-size: 0.8rem;
        font-weight: 700;
        box-shadow: 0 2px 4px rgb(245 158 11 / 0.3);
    }}

    /* ── CENTER HEADER ── */
    .top-center-bar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        width: 100%;
        min-width: 0;
        padding-right: 0;
    }}

    .top-center-title {{
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text);
        margin: 0;
        line-height: 1.3;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    .top-center-subtitle {{
        font-size: 0.7rem;
        color: var(--muted);
        margin: 0.1rem 0 0 0;
    }}

    .top-bar-info {{
        flex: 1;
        min-width: 0;
        overflow: hidden;
    }}

    .back-arrow {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2rem;
        height: 2rem;
        color: var(--muted);
        text-decoration: none !important;
        border-radius: 8px;
        transition: all 0.15s ease;
        flex-shrink: 0;
    }}

    .back-arrow:hover {{
        color: var(--text);
        background: var(--bg);
    }}

    /* ── MY REQUESTS BUTTON ── */
    .top-requests-link {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.35rem;
        text-decoration: none !important;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--panel);
        color: var(--muted);
        font-size: 0.75rem;
        font-weight: 500;
        padding: 0.4rem 0.75rem;
        white-space: nowrap;
        line-height: 1;
        flex-shrink: 0;
        align-self: center;
        margin-left: auto;
        margin-right: 0.1rem;
        transition: all 0.2s ease;
    }}

    .top-requests-link:hover {{
        color: var(--text);
        border-color: #cbd5e1;
        box-shadow: var(--shadow-sm);
    }}

    .top-requests-link.active {{
        background: var(--brand-bg);
        border-color: var(--brand-border);
        color: var(--brand-text);
        box-shadow: 0 0 0 1px var(--brand-border);
    }}

    .top-requests-icon {{
        font-family: 'Material Symbols Outlined';
        font-size: 0.875rem;
        line-height: 1;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }}

    .header-requests-action-marker,
    .header-requests-close-marker {{
        display: none !important;
    }}

    div[data-testid="stColumn"]:has(.header-requests-action-marker) > div[data-testid="stVerticalBlock"],
    div[data-testid="stColumn"]:has(.header-requests-close-marker) > div[data-testid="stVerticalBlock"] {{
        padding: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: flex-end !important;
        min-height: var(--header-h) !important;
        height: var(--header-h) !important;
        gap: 0 !important;
    }}

    /* Collapse the Streamlit wrapper around the marker so it takes no space */
    div[data-testid="stColumn"]:has(.header-requests-action-marker) > div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMarkdown"] .header-requests-action-marker),
    div[data-testid="stColumn"]:has(.header-requests-close-marker) > div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMarkdown"] .header-requests-close-marker) {{
        height: 0 !important;
        min-height: 0 !important;
        overflow: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
    }}

    div[data-testid="stColumn"]:has(.header-requests-action-marker),
    div[data-testid="stColumn"]:has(.header-requests-close-marker) {{
        display: flex !important;
        align-items: center !important;
        justify-content: flex-end !important;
    }}

    div[data-testid="stColumn"]:has(.header-requests-action-marker) {{
        padding-right: 0.55rem !important;
    }}

    div[data-testid="stColumn"]:has(.header-requests-action-marker) .stButton {{
        width: auto !important;
        margin: 0 !important;
    }}

    div[data-testid="stColumn"]:has(.header-requests-action-marker) .stButton > button {{
        border-radius: 10px;
        border: 1px solid #cbd5e1;
        background: #f8fafc;
        color: #64748b;
        font-size: 0.875rem;
        font-weight: 600;
        min-height: 2rem;
        padding: 0.35rem 0.8rem 0.35rem 0.55rem;
        line-height: 1;
        box-shadow: none;
        margin: 0 !important;
        transform: none !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 0.3rem !important;
    }}

    /* Icon via ::before pseudo-element */
    div[data-testid="stColumn"]:has(.header-requests-action-marker) .stButton > button::before {{
        content: 'assignment';
        font-family: 'Material Symbols Outlined';
        font-size: 1rem;
        line-height: 1;
        display: inline-flex;
        align-items: center;
        -webkit-font-smoothing: antialiased;
    }}

    div[data-testid="stColumn"]:has(.header-requests-action-marker) .stButton > button:hover {{
        color: #475569;
        border-color: #cbd5e1;
        background: #f1f5f9;
        box-shadow: none !important;
        transform: none !important;
    }}

    /* Keep same style when panel is open — no blue highlight */
    div[data-testid="stColumn"]:has(.header-requests-action-marker.active) .stButton > button {{
        background: #f8fafc;
        border-color: #cbd5e1;
        color: #64748b;
        box-shadow: none;
    }}

    /* Override Streamlit's default focus / active blue ring */
    div[data-testid="stColumn"]:has(.header-requests-action-marker) .stButton > button:focus,
    div[data-testid="stColumn"]:has(.header-requests-action-marker) .stButton > button:active,
    div[data-testid="stColumn"]:has(.header-requests-action-marker) .stButton > button:focus:not(:active) {{
        background: #f8fafc !important;
        border-color: #cbd5e1 !important;
        color: #64748b !important;
        box-shadow: none !important;
        outline: none !important;
    }}

    div[data-testid="stColumn"]:has(.header-requests-close-marker) .stButton > button {{
        border-radius: 8px;
        border: 1px solid transparent;
        background: transparent;
        color: var(--muted);
        min-height: 2rem;
        padding: 0;
        box-shadow: none;
        font-size: 1rem;
        font-weight: 500;
        line-height: 1;
        margin: 0 !important;
        width: 2rem;
        min-width: 2rem;
        height: 2rem;
        transform: none !important;
    }}

    div[data-testid="stColumn"]:has(.header-requests-close-marker) {{
        padding-right: 0.3rem !important;
    }}

    div[data-testid="stColumn"]:has(.header-requests-close-marker) .stButton > button:hover {{
        color: var(--text);
        background: var(--bg);
        border-color: var(--line);
        box-shadow: none !important;
        transform: none !important;
    }}

    /* ── RIGHT RAIL ── */
    .rail-title {{
        font-weight: 600;
        font-size: 0.875rem;
        color: var(--text);
        margin: 0;
    }}

    .rail-subtitle {{
        margin: 0.25rem 0 0.5rem 0;
        color: var(--muted);
        font-size: 0.75rem;
    }}

    .rail-close {{
        color: var(--muted);
        text-decoration: none !important;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.75rem;
        height: 1.75rem;
        border-radius: 8px;
        transition: all 0.15s ease;
    }}

    .rail-close:hover {{
        color: var(--text);
        background: var(--bg);
    }}

    /* ── LEFT SIDEBAR ── */
    .new-convo-gap-top {{
        height: 0.95rem;
    }}

    .new-convo-gap-bottom {{
        height: 0.35rem;
    }}

    .thin-divider {{
        border: none;
        border-top: 1px solid var(--line);
        margin: 0.25rem 0;
    }}

    .thread-link {{
        text-decoration: none !important;
        color: inherit !important;
        display: block;
    }}

    .thread-card {{
        border: 1px solid transparent;
        border-radius: 10px;
        padding: 0.5rem 0.6rem;
        background: transparent;
        margin-bottom: 2px;
        cursor: pointer;
        transition: all 0.15s ease;
    }}

    .thread-card:hover {{
        background: rgba(0, 0, 0, 0.04);
    }}

    .thread-row {{
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
    }}

    .thread-icon {{
        font-family: 'Material Symbols Outlined';
        font-size: 1rem;
        color: #94a3b8;
        line-height: 1;
        margin-top: 1px;
    }}

    .thread-title {{
        font-size: 0.8rem;
        font-weight: 500;
        color: #475569;
        margin: 0;
        line-height: 1.4;
    }}

    .thread-meta {{
        margin-top: 2px;
        font-size: 0.65rem;
        color: #94a3b8;
    }}

    .thread-active {{
        border-color: var(--brand-border) !important;
        background: var(--brand-bg) !important;
    }}

    .thread-active .thread-title {{
        color: var(--brand-text);
        font-weight: 600;
    }}

    .thread-active .thread-icon {{
        color: var(--brand);
    }}

    /* ── PROFILE FOOTER ── */
    .profile-footer {{
        margin-top: 0;
        padding-top: 0.6rem;
        border-top: 1px solid var(--line);
        background: var(--sidebar-bg);
    }}

    .left-rail-spacer {{
        height: 100%;
    }}

    .profile-footer-row {{
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 0.6rem;
        border-radius: 10px;
        transition: background 0.15s ease;
    }}

    .profile-footer-row:hover {{
        background: rgba(0, 0, 0, 0.04);
    }}

    .profile-avatar {{
        width: 32px;
        height: 32px;
        border-radius: 50%;
        border: none;
        background: linear-gradient(135deg, #f59e0b, #d97706);
        color: #ffffff;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.8rem;
        flex-shrink: 0;
        box-shadow: 0 2px 4px rgb(245 158 11 / 0.25);
    }}

    .profile-name {{
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--text);
        margin: 0;
        line-height: 1.2;
    }}

    .profile-email {{
        font-size: 0.7rem;
        color: var(--muted);
        margin: 0.1rem 0 0 0;
    }}

    /* ── HERO SECTION ── */
    .hero-chip {{
        margin: 0.5rem auto;
        width: fit-content;
        border: 1px solid var(--brand-border);
        background: var(--brand-bg);
        color: var(--brand-text);
        border-radius: 999px;
        padding: 0.3rem 0.85rem;
        font-size: 0.75rem;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
    }}

    .home-hero {{
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
    }}

    .hero-title {{
        text-align: center;
        font-size: 2rem;
        line-height: 1.15;
        color: var(--text);
        margin: 0.6rem 0 0.5rem;
        font-weight: 800;
        letter-spacing: -0.03em;
    }}

    .hero-subtitle {{
        text-align: center;
        color: var(--muted);
        font-size: 0.9rem;
        margin: 0;
        font-weight: 400;
        line-height: 1.6;
    }}

    .hero-note {{
        text-align: center;
        color: #94a3b8;
        margin-top: 0.25rem;
        font-size: 0.75rem;
    }}

    /* ── TOPIC TILES ── */
    .home-tiles-marker {{
        display: none !important;
    }}

    div[data-testid="stColumn"]:has(.center-col-marker) > div[data-testid="stVerticalBlock"]:has(.home-tiles-marker) > div[data-testid="stHorizontalBlock"] {{
        max-width: var(--chat-w);
        width: 100%;
        margin: 0 auto !important;
        gap: 0.65rem !important;
        column-gap: 0.65rem !important;
    }}

    div[data-testid="stColumn"]:has(.center-col-marker) > div[data-testid="stVerticalBlock"]:has(.home-tiles-marker) > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
        padding: 0 !important;
    }}

    .tile-card {{
        border-radius: var(--radius);
        border: 1px solid;
        padding: 0.875rem 1rem;
        margin-bottom: 0.5rem;
        transition: all 0.2s ease;
        cursor: pointer;
    }}

    .tile-card:hover {{
        transform: translateY(-1px);
        box-shadow: var(--shadow-md);
    }}

    .tile-row {{
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
    }}

    .tile-icon {{
        font-family: 'Material Symbols Outlined';
        font-size: 1.1rem;
        line-height: 1;
        margin-top: 2px;
    }}

    .tile-title {{
        margin: 0;
        font-size: 0.875rem;
        font-weight: 600;
        color: #334155;
        line-height: 1.4;
    }}

    .tile-subtitle {{
        margin: 2px 0 0 0;
        color: var(--muted);
        font-size: 0.75rem;
        line-height: 1.4;
    }}

    /* ── CHAT ── */
    .chat-messages-container {{
        max-width: var(--chat-w);
        margin: 0 auto;
        padding: 1.5rem 1.5rem 0.5rem;
    }}

    .msg-row {{
        display: flex;
        align-items: flex-start;
        gap: 0.65rem;
        margin-bottom: 0.8rem;
    }}

    .msg-user {{
        justify-content: flex-end;
    }}

    .msg-assistant {{
        justify-content: flex-start;
    }}

    .msg-avatar {{
        width: 2rem;
        height: 2rem;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 1px solid var(--line);
        flex-shrink: 0;
        color: #64748b;
        background: #f8fafc;
        font-size: 1rem;
        line-height: 1;
    }}

    .assistant-avatar {{
        border-color: var(--brand-border);
        color: var(--brand-text);
        background: var(--brand-bg);
        border-radius: 10px;
        width: 2.1rem;
        height: 2.1rem;
    }}

    .chat-input-wrap {{
        margin-top: 0.15rem;
        max-width: var(--chat-w);
        margin-left: auto;
        margin-right: auto;
    }}

    .chat-note {{
        text-align: center;
        font-size: 0.65rem;
        color: #94a3b8;
        margin-top: 0.5rem;
        padding-bottom: 0.5rem;
    }}

    .user-bubble {{
        background: linear-gradient(135deg, #f59e0b, #d97706);
        color: white;
        border-radius: 18px 4px 18px 18px;
        padding: 0.8rem 1.1rem;
        font-size: 0.875rem;
        font-weight: 400;
        margin-bottom: 0.75rem;
        line-height: 1.6;
        box-shadow: 0 2px 8px rgb(245 158 11 / 0.2);
        max-width: 36rem;
        width: fit-content;
    }}

    .assistant-bubble {{
        border: 1px solid var(--line);
        border-radius: 4px 18px 18px 18px;
        padding: 0.9rem 1.1rem;
        background: var(--panel);
        color: var(--text);
        font-size: 0.875rem;
        line-height: 1.6;
        box-shadow: var(--shadow-sm);
        margin-bottom: 0.75rem;
        max-width: 40rem;
        width: fit-content;
    }}

    /* ── REQUESTS PANEL ── */
    .requests-empty {{
        text-align: center;
        color: var(--muted);
        border: 2px dashed var(--line);
        border-radius: var(--radius);
        padding: 2.5rem 1rem;
        background: transparent;
        margin-top: 0.5rem;
    }}

    .request-row {{
        border: 1px solid var(--line);
        border-radius: var(--radius);
        padding: 0.875rem 1rem;
        background: var(--panel);
        margin-bottom: 0.5rem;
        box-shadow: var(--shadow-sm);
        transition: box-shadow 0.15s ease;
    }}

    .request-row:hover {{
        box-shadow: var(--shadow-md);
    }}

    .request-title {{
        font-size: 0.813rem;
        font-weight: 500;
        color: var(--text);
        margin: 0;
        line-height: 1.4;
    }}

    .request-meta {{
        margin-top: 0.35rem;
        color: var(--muted);
        font-size: 0.65rem;
    }}

    .status-pill {{
        display: inline-block;
        border-radius: 999px;
        padding: 0.2rem 0.6rem;
        font-size: 0.65rem;
        font-weight: 600;
        border: 1px solid;
        margin-top: 0.35rem;
        letter-spacing: 0.02em;
    }}

    .status-pending {{
        color: #d97706;
        border-color: var(--brand-border);
        background: var(--brand-bg);
    }}

    .status-in-review {{
        color: #0284c7;
        border-color: #bae6fd;
        background: #f0f9ff;
    }}

    .status-resolved {{
        color: #059669;
        border-color: #a7f3d0;
        background: #ecfdf5;
    }}

    /* ── METRICS ── */
    .metric-card {{
        border: 1px solid var(--line);
        border-radius: var(--radius);
        padding: 0.6rem 0.5rem;
        text-align: center;
        background: var(--panel);
        box-shadow: var(--shadow-sm);
    }}

    .metric-num {{
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0 0 0.12rem 0;
    }}

    .metric-label {{
        margin: 2px 0 0 0;
        color: var(--muted);
        font-size: 0.6rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        font-weight: 600;
        white-space: nowrap;
    }}

    /* ── STREAMLIT WIDGET OVERRIDES ── */
    .stButton > button {{
        border-radius: 10px;
        border: 1px solid var(--line);
        color: #475569;
        font-weight: 500;
        background: var(--panel);
        font-size: 0.813rem;
        line-height: 1.25;
        min-height: 2.25rem;
        padding: 0.45rem 0.75rem;
        transition: all 0.2s ease;
        box-shadow: var(--shadow-sm);
    }}

    .stButton > button:hover {{
        border-color: var(--brand-border);
        color: var(--brand-text);
        background: var(--brand-bg);
        box-shadow: var(--shadow-md);
        transform: translateY(-1px);
    }}

    div[data-testid="stSelectbox"] > div[data-baseweb="select"] > div {{
        border-radius: var(--radius);
        border: 1px solid var(--line);
        background: var(--panel);
        min-height: 44px;
        box-shadow: var(--shadow-sm);
    }}

    div[data-testid="stSegmentedControl"] > div {{
        border: 1px solid var(--line);
        border-radius: var(--radius);
        background: var(--sidebar-bg);
        gap: 0.25rem;
        padding: 0.2rem;
    }}

    div[data-testid="stSegmentedControl"] label {{
        border-radius: 8px !important;
        border: 1px solid transparent !important;
        background: transparent !important;
        padding: 0.3rem 0.625rem !important;
        color: var(--muted) !important;
        font-weight: 500 !important;
        font-size: 0.75rem !important;
        transition: all 0.15s ease !important;
    }}

    div[data-testid="stSegmentedControl"] label:hover {{
        color: var(--text) !important;
        background: var(--panel) !important;
    }}

    div[data-testid="stSegmentedControl"] label[aria-checked="true"] {{
        background: var(--panel) !important;
        color: var(--brand-text) !important;
        border: 1px solid var(--brand-border) !important;
        box-shadow: var(--shadow-sm) !important;
    }}

    /* ── CHAT INPUT ── */
    div[data-testid="stChatInput"] {{
        border: 1px solid var(--line);
        border-radius: 16px;
        background: var(--panel);
        box-shadow: var(--shadow-md);
        max-width: var(--chat-w);
        margin: 0.2rem auto 0.1rem !important;
    }}

    div[data-testid="stChatInput"] > div {{
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }}

    div[data-testid="stChatInput"]:focus-within {{
        border-color: var(--brand);
        box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15), var(--shadow-md);
    }}

    /* ── RESPONSIVE ── */
    @media (max-width: 1200px) {{
        .hero-title {{ font-size: 1.5rem; }}
        .hero-subtitle {{ font-size: 0.8125rem; }}
        .hero-note {{ font-size: 0.6875rem; }}
        [data-testid="stAppViewContainer"] > .main {{ padding: 0.55rem !important; }}
        .main .block-container,
        [data-testid="stMainBlockContainer"] {{ border-radius: 10px !important; }}
    }}

    /* ── SCROLLBARS (WebKit) ── */
    ::-webkit-scrollbar {{
        width: 6px;
        height: 6px;
    }}
    ::-webkit-scrollbar-track {{
        background: transparent;
    }}
    ::-webkit-scrollbar-thumb {{
        background: rgba(148, 163, 184, 0.35);
        border-radius: 10px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: rgba(100, 116, 139, 0.5);
    }}
    ::-webkit-scrollbar-corner {{
        background: transparent;
    }}

    /* ── SCROLLBARS (Firefox) ── */
    * {{
        scrollbar-width: thin;
        scrollbar-color: rgba(148,163,184,0.35) transparent;
    }}

    /* ── SMOOTH TRANSITIONS ── */
    div[data-testid="stColumn"] {{
        transition: width 0.3s ease, flex 0.3s ease;
    }}
</style>
""",
    unsafe_allow_html=True,
)

# ── Client-side JS for polish ──
st.markdown(
    """
<script>
(function() {
    // Debounced resize handler for responsive adjustments
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            document.querySelectorAll('.tile-card').forEach(function(card) {
                if (window.innerWidth < 900) {
                    card.style.padding = '0.65rem 0.75rem';
                } else {
                    card.style.padding = '';
                }
            });
        }, 150);
    });

    // Smooth scroll for chat container
    const observer = new MutationObserver(function(mutations) {
        const chatContainer = document.querySelector('.chat-messages-container');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    });

    const target = document.querySelector('[data-testid="stAppViewContainer"]');
    if (target) {
        observer.observe(target, { childList: true, subtree: true });
    }
})();
</script>
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
        "#fffbeb",
        "#fde68a",
        "#d97706",
        "What leave policies does Acme offer?",
    ),
    (
        "Payroll & Pay",
        "Pay dates, payslips, expenses",
        "payments",
        "#ecfdf5",
        "#a7f3d0",
        "#059669",
        "When is payday and how do I access payslips?",
    ),
    (
        "Benefits",
        "Health, pension, gym, perks",
        "favorite",
        "#f0f9ff",
        "#bae6fd",
        "#0284c7",
        "What benefits am I eligible for?",
    ),
    (
        "Company Policy",
        "Remote work, code of conduct, hours",
        "menu_book",
        "#fff7ed",
        "#fed7aa",
        "#ea580c",
        "What is Acme's remote work policy?",
    ),
    (
        "Onboarding",
        "First day prep, probation, setup",
        "person_add",
        "#fff1f2",
        "#fecdd3",
        "#e11d48",
        "What are onboarding and probation policies?",
    ),
    (
        "Documents",
        "Letters, payslips, tax forms",
        "description",
        "#f0fdfa",
        "#99f6e4",
        "#0d9488",
        "How do I get employment letters and tax documents?",
    ),
    (
        "Career & Growth",
        "Internal jobs, promotions, reviews",
        "work",
        "#f5f3ff",
        "#ddd6fe",
        "#7c3aed",
        "How does performance review and promotion work?",
    ),
    (
        "Wellbeing & Support",
        "EAP, mental health, occupational health",
        "health_and_safety",
        "#fffbeb",
        "#fde68a",
        "#b45309",
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
        st.session_state.show_requests_panel = False
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
        agent = HRAgentLangGraph(
            user_email=user_email, session_id=f"thread_{thread_id}"
        )
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
        key
        for key in st.session_state.agents_by_thread.keys()
        if key.startswith(f"{user_email}:")
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
    with st.spinner("Thinking..."):
        response = _active_agent(user_email, thread["id"]).chat(prompt)
    _append_message(thread, "assistant", response)


# ============================================================================
# DATA SETUP
# ============================================================================

repo = _get_employee_repo()
employee_service = get_employee_service()
escalation_service = get_escalation_service()

employees = repo.list_all_for_dropdown()
employee_options = {
    f"{row['legal_name']} • {row['title']}": row["email"] for row in employees
}
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
current_store = _get_store(current_email)

thread_param = st.query_params.get("thread")
if thread_param and any(t["id"] == thread_param for t in current_store["threads"]):
    current_store["active_thread_id"] = thread_param

prompt_param = st.query_params.get("prompt")
if prompt_param is not None:
    try:
        tile_idx = int(prompt_param)
        if 0 <= tile_idx < len(HOME_TILES):
            st.session_state.queued_prompt = HOME_TILES[tile_idx][6]
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
    header_left, header_center, header_right = st.columns([2.8, 10.4, 4.3], gap=None)
    left_col, center_col, right_col = st.columns([2.8, 10.4, 4.3], gap=None)
else:
    header_left, header_center = st.columns([2.8, 14.7], gap=None)
    left_col, center_col = st.columns([2.8, 14.7], gap=None)
    header_right = None
    right_col = None


with header_left:
    st.markdown('<div class="top-left-marker"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="panel-top">
            <div class="left-head">
                <span class="logo-box">P</span>
                <span style="font-size:0.938rem;font-weight:700;letter-spacing:-0.03em;color:#1e293b;">PingHR</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with header_center:
    st.markdown('<div class="top-center-marker"></div>', unsafe_allow_html=True)
    center_info_col, center_action_col = st.columns([10.2, 2.0], gap=None)

    has_messages = bool(active_thread["messages"])
    top_title = _short_text(active_thread["title"], 70) if has_messages else "PingHR"
    safe_top_title = html.escape(top_title)

    back_arrow_html = ""
    subtitle_html = ""
    if has_messages:
        back_arrow_html = (
            f'<a class="back-arrow" target="_self" href="?thread={active_thread["id"]}" title="Back to home">'
            '<span class="material-symbols-outlined" style="font-size:1.1rem;">arrow_back</span>'
            "</a>"
        )
        subtitle_html = '<p class="top-center-subtitle">Employee HR Assistant</p>'

    with center_info_col:
        # Build the HTML as a single string without blank lines to prevent
        # Streamlit's Markdown parser from breaking the HTML block.
        header_center_html = (
            '<div class="panel-top top-center-bar">'
            + back_arrow_html
            + '<div class="top-bar-info">'
            + f'<p class="top-center-title">{safe_top_title}</p>'
            + subtitle_html
            + "</div>"
            + "</div>"
        )
        st.markdown(header_center_html, unsafe_allow_html=True)

    with center_action_col:
        active_marker = " active" if st.session_state.show_requests_panel else ""
        st.markdown(
            f'<div class="header-requests-action-marker{active_marker}"></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "My Requests",
            key="toggle_requests_header_btn",
        ):
            st.session_state.show_requests_panel = (
                not st.session_state.show_requests_panel
            )
            st.rerun()

if header_right:
    with header_right:
        st.markdown('<div class="top-right-marker"></div>', unsafe_allow_html=True)
        right_title_col, right_action_col = st.columns([8.8, 1.2], gap=None)
        with right_title_col:
            st.markdown(
                """
                <div class="panel-top">
                    <p class="rail-title">My Requests</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with right_action_col:
            st.markdown(
                '<div class="header-requests-close-marker"></div>',
                unsafe_allow_html=True,
            )
            if st.button(
                "✕",
                key="toggle_requests_close_btn",
                use_container_width=True,
            ):
                st.session_state.show_requests_panel = False
                st.rerun()

st.markdown('<div class="global-top-divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="post-top-gap"></div>', unsafe_allow_html=True)


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

    for t_item in current_store["threads"]:
        is_active = t_item["id"] == current_store["active_thread_id"]
        card_class = "thread-card thread-active" if is_active else "thread-card"
        st.markdown(
            f"""
            <a class="thread-link" target="_self" href="?thread={t_item['id']}">
                <div class="{card_class}">
                    <div class="thread-row">
                        <span class="thread-icon">chat_bubble_outline</span>
                        <div>
                            <p class="thread-title">{_short_text(t_item['title'], 28)}</p>
                            <div class="thread-meta">● {_format_relative(t_item.get('updated_at'))}</div>
                        </div>
                    </div>
                </div>
            </a>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="thin-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="left-rail-spacer"></div>', unsafe_allow_html=True)

    display_name = emp_details.get("preferred_name") or emp_details.get(
        "legal_name", "User"
    )
    st.markdown(
        f"""
        <div class="profile-footer">
            <div class="profile-footer-row">
                <div class="profile-avatar">{display_name[0].upper() if display_name else "U"}</div>
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
    st.markdown('<div class="center-col-marker"></div>', unsafe_allow_html=True)
    if st.session_state.queued_prompt:
        _process_prompt(current_email, active_thread, st.session_state.queued_prompt)
        _sort_threads(current_store)
        st.session_state.queued_prompt = None
        st.rerun()

    if not active_thread["messages"]:
        first_name = display_name.split()[0] if display_name else "there"
        st.markdown(
            f"""
            <div class="chat-messages-container home-hero" style="padding-top:3rem;">
                <div class="hero-chip">✨ Your HR assistant · Acme Corp</div>
                <h1 class="hero-title">Hi {first_name}, what can I help with?</h1>
                <p class="hero-subtitle">Ask me anything about Acme's HR policies — leave, payroll, benefits, and more.</p>
                <p class="hero-note">Sensitive queries are securely escalated to HR Ops.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="home-tiles-marker"></div>', unsafe_allow_html=True)
        col_a, col_b = st.columns(2, gap="small")
        for idx, (
            title,
            subtitle,
            icon_name,
            bg_color,
            border_color,
            icon_color,
            _question,
        ) in enumerate(HOME_TILES):
            target_col = col_a if idx % 2 == 0 else col_b
            with target_col:
                st.markdown(
                    f"""
                    <a class="thread-link" target="_self" href="?thread={active_thread['id']}&prompt={idx}">
                        <div class="tile-card" style="background:{bg_color};border-color:{border_color};">
                            <div class="tile-row">
                                <span class="tile-icon" style="color:{icon_color};">{icon_name}</span>
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
        st.markdown('<div class="chat-messages-container">', unsafe_allow_html=True)
        for idx, message in enumerate(active_thread["messages"]):
            if message["role"] == "user":
                st.markdown(
                    (
                        '<div class="msg-row msg-user">'
                        + f'<div class="user-bubble">{message["content"]}</div>'
                        + '<span class="msg-avatar material-symbols-outlined">person</span>'
                        + "</div>"
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    (
                        '<div class="msg-row msg-assistant">'
                        + '<span class="msg-avatar assistant-avatar material-symbols-outlined">smart_toy</span>'
                        + f'<div class="assistant-bubble">{message["content"]}</div>'
                        + "</div>"
                    ),
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
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="chat-input-wrap"></div>', unsafe_allow_html=True)
    user_prompt = st.chat_input(
        "Ask anything about HR, leave, payroll, benefits...",
        key=f"chat_input_{active_thread['id']}",
    )
    if user_prompt:
        _process_prompt(current_email, active_thread, user_prompt)
        _sort_threads(current_store)
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
        st.markdown('<div class="right-col-marker"></div>', unsafe_allow_html=True)
        counts = escalation_service.list_counts(current_email)
        st.markdown(
            f'<p class="rail-subtitle">{counts["total"]} escalated queries</p>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="height:0.2rem;"></div>', unsafe_allow_html=True)

        m1, m2, m3 = st.columns(3, gap="xsmall")
        with m1:
            st.markdown(
                f"""
                <div class="metric-card">
                    <p class="metric-num" style="color:#f59e0b;">{counts['pending']}</p>
                    <p class="metric-label">Pending</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f"""
                <div class="metric-card">
                    <p class="metric-num" style="color:#0ea5e9;">{counts['in_review']}</p>
                    <p class="metric-label">In Review</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f"""
                <div class="metric-card">
                    <p class="metric-num" style="color:#10b981;">{counts['resolved']}</p>
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
                    <div style="font-size:0.75rem;font-weight:500;color:#64748b;">No requests found</div>
                    <div style="margin-top:0.25rem;font-size:10px;color:#94a3b8;">Escalated queries will appear here</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            can_triage = current_role in {"HR", "MANAGER"}
            for item in requests:
                item_status = item["status"]
                st.markdown(
                    f"""
                    <div class="request-row">
                        <p class="request-title">#{item['escalation_id']} · {_short_text(item['source_message_excerpt'], 82)}</p>
                        <div class="request-meta">{item['requester_email']} · {_format_relative(item['updated_at'])}</div>
                        <span class="status-pill {_status_class(item_status)}">{item_status.replace('_', ' ')}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if can_triage:
                    if item_status == "PENDING":
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
                    elif item_status == "IN_REVIEW":
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
