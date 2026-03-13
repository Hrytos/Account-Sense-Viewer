"""
Account Sense Viewer - Streamlit App

A web-based UI for viewing account and site analysis data.

Usage:
    streamlit run streamlit_app.py
"""

import streamlit as st
import pandas as pd
import html as html_lib
import re
from datetime import datetime
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure the root directory is in sys.path so we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.services.data_fetcher import get_site_data
from src.services.ai_summarizer import (
    generate_account_summary,
    generate_company_overview,
    generate_assertion_summary
)

# Configure the page
st.set_page_config(
    page_title="Account Sense Viewer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Authentication Check ─────────────────────────────────────────────────────
if not st.session_state.get('authenticated', False):
    # Show login form inline
    st.markdown(
        '<div style="text-align:center;padding-top:5rem;">'
        '<h1>🔐 Account Sense Viewer</h1>'
        '<p style="opacity:0.6;">Please log in to continue</p>'
        '</div>',
        unsafe_allow_html=True
    )
    
    # Get credentials from environment
    VALID_USERNAME = os.getenv("username", "admin")
    VALID_PASSWORD = os.getenv("password", "password")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submit = st.form_submit_button("Log In", type="primary", use_container_width=True)
            
            if submit:
                if not username or not password:
                    st.error("Please enter both username and password")
                elif username == VALID_USERNAME and password == VALID_PASSWORD:
                    st.session_state['authenticated'] = True
                    st.session_state['username'] = username
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    
    st.stop()  # Stop execution here if not authenticated

# ── Global CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Page chrome ── */
    .block-container { padding-top: 2rem; padding-bottom: 3rem; }

    /* ── Section headers ── */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin: 2rem 0 0.75rem;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid rgba(127,127,127,0.2);
    }
    .section-header h2 {
        margin: 0;
        font-size: 1.25rem;
        font-weight: 700;
        letter-spacing: -0.01em;
    }
    .section-icon { font-size: 1.1rem; }

    /* ── Metric cards ── */
    .metric-card {
        background: rgba(127,127,127,0.07);
        border: 1px solid rgba(127,127,127,0.18);
        border-radius: 0.6rem;
        padding: 0.9rem 1.1rem;
    }
    .metric-card .label {
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        opacity: 0.55;
        margin-bottom: 0.2rem;
    }
    .metric-card .value {
        font-size: 1.05rem;
        font-weight: 600;
        word-break: break-all;
    }

    /* ── Info pill / badge ── */
    .badge {
        display: inline-block;
        padding: 0.18rem 0.55rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        background: rgba(127,127,127,0.12);
    }

    /* ── Tables ── */
    .custom-table-wrapper {
        width: 100%;
        overflow-x: auto;
        border: 1px solid rgba(127,127,127,0.2);
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        font-size: 0.875rem;
        color: inherit;
    }
    .custom-table th, .custom-table td {
        border-bottom: 1px solid rgba(127,127,127,0.15);
        padding: 0.6rem 0.75rem;
        vertical-align: top;
        text-align: left;
        white-space: normal;
        word-break: break-word;
        overflow-wrap: anywhere;
        color: inherit;
        background: transparent;
        line-height: 1.45;
    }
    .custom-table th {
        font-weight: 600;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        background: rgba(127,127,127,0.08);
        opacity: 0.8;
    }
    .custom-table tbody tr:last-child td { border-bottom: none; }
    .custom-table tr:hover td { background: rgba(127,127,127,0.05); }

    /* ── Assertions table ── */
    .assertions-table-wrapper {
        width: 100%;
        overflow-x: auto;
        border: 1px solid rgba(127,127,127,0.2);
        border-radius: 0.5rem;
    }
    .assertions-table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        font-size: 0.875rem;
        color: inherit;
    }
    .assertions-table th, .assertions-table td {
        border-bottom: 1px solid rgba(127,127,127,0.15);
        padding: 0.6rem 0.75rem;
        vertical-align: top;
        text-align: left;
        white-space: normal;
        word-break: break-word;
        overflow-wrap: anywhere;
        color: inherit;
        background: transparent;
        line-height: 1.45;
    }
    .assertions-table th {
        font-weight: 600;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        background: rgba(127,127,127,0.08);
        opacity: 0.8;
    }
    .assertions-table tbody tr:last-child td { border-bottom: none; }
    .assertions-table tr:hover td { background: rgba(127,127,127,0.05); }

    /* Column widths */
    .assertions-table th:nth-child(1), .assertions-table td:nth-child(1) { width: 4%; }
    .assertions-table th:nth-child(2), .assertions-table td:nth-child(2) { width: 46%; }
    .assertions-table th:nth-child(3), .assertions-table td:nth-child(3) { width: 11%; }
    .assertions-table th:nth-child(4), .assertions-table td:nth-child(4) { width: 7%; }
    .assertions-table th:nth-child(5), .assertions-table td:nth-child(5) { width: 7%; }
    .assertions-table th:nth-child(6), .assertions-table td:nth-child(6) { width: 7%; }
    .assertions-table th:nth-child(7), .assertions-table td:nth-child(7) { width: 18%; }


    /* ── Empty state ── */
    .empty-state {
        text-align: center;
        padding: 2rem 1rem;
        opacity: 0.45;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def section_header(icon: str, title: str):
    st.markdown(
        f'<div class="section-header">'
        f'<span class="section-icon">{icon}</span>'
        f'<h2>{html_lib.escape(title)}</h2>'
        f'</div>',
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str):
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="label">{html_lib.escape(label)}</div>'
        f'<div class="value">{html_lib.escape(str(value))}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_custom_table(data, columns, widths=None):
    if not data:
        st.markdown('<div class="empty-state">No data available</div>', unsafe_allow_html=True)
        return

    width_styles = ""
    if widths:
        for i, w in enumerate(widths):
            width_styles += (
                f".custom-table th:nth-child({i+1}),"
                f".custom-table td:nth-child({i+1}) {{ width: {w}; }}\n"
            )

    rows_html = []
    for item in data:
        row_html = "<tr>"
        for col in columns:
            val = item.get(col, "")
            row_html += f"<td>{html_lib.escape(str(val))}</td>"
        row_html += "</tr>"
        rows_html.append(row_html)

    header_html = "".join([f"<th>{html_lib.escape(col)}</th>" for col in columns])
    body_html = "".join(rows_html)

    table_html = f"""<style>{width_styles}</style>
<div class="custom-table-wrapper">
  <table class="custom-table">
    <thead><tr>{header_html}</tr></thead>
    <tbody>{body_html}</tbody>
  </table>
</div>"""

    try:
        st.html(table_html)
    except AttributeError:
        st.markdown(table_html, unsafe_allow_html=True)


def parse_iso_timestamp(timestamp_str):
    if not timestamp_str:
        return None
    s = str(timestamp_str).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?([+-]\d{2}:\d{2})?$", s)
    if match:
        base, fraction, tz = match.groups()
        tz = tz or "+00:00"
        if fraction:
            fraction_digits = (fraction[1:] + "000000")[:6]
            s = f"{base}.{fraction_digits}{tz}"
        else:
            s = f"{base}{tz}"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None




# ── Page header ──────────────────────────────────────────────────────────────

header_col1, header_col2 = st.columns([6, 1])
with header_col1:
    st.markdown(
        '<h1 style="margin-bottom:0.1rem;">📊 Account Sense Viewer</h1>'
        '<p style="opacity:0.5;margin-top:0;margin-bottom:1.25rem;font-size:0.95rem;">'
        'View detailed account and site analysis data'
        '</p>',
        unsafe_allow_html=True,
    )
with header_col2:
    st.write("")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state['authenticated'] = False
        st.session_state['username'] = None
        st.rerun()

st.markdown("---")

col_input, col_btn = st.columns([5, 1])
with col_input:
    site_id = st.text_input(
        "Site ID",
        value="",
        help="Enter the UUID of the site you want to analyze",
        key="site_id_input",
        placeholder="e.g., d80e7532-2253-4c53-a31b-90e05dfb98d8",
        label_visibility="collapsed",
    )
with col_btn:
    load_button = st.button("Load →", type="primary", use_container_width=True)

st.markdown("---")

# ── Data loading ─────────────────────────────────────────────────────────────

if load_button:
    if not site_id.strip():
        st.warning("Please enter a Site ID before loading.")
    else:
        with st.spinner("Fetching data…"):
            try:
                data = get_site_data(site_id)
                st.session_state['data'] = data
                st.session_state['loaded'] = True
                st.success("Data loaded successfully.")
            except Exception as e:
                st.error(f"Error loading data: {e}")
                if "403" in str(e) or "Forbidden" in str(e):
                    st.warning(
                        "**403 Forbidden** — check Supabase RLS policies and that you're "
                        "using a `service_role` key with access to the required tables."
                    )
                st.session_state['loaded'] = False

# ── Main content ─────────────────────────────────────────────────────────────

if st.session_state.get('loaded', False):
    data = st.session_state['data']

    # ── Run Details ──────────────────────────────────────────────────────────
    section_header("🕐", "Run Details")

    latest_created = latest_updated = None
    if data['assertions']:
        created_dates = [a['created_at'] for a in data['assertions'] if a['created_at']]
        updated_dates = [a['updated_at'] for a in data['assertions'] if a['updated_at']]
        if created_dates:
            dt = parse_iso_timestamp(max(created_dates))
            latest_created = dt.strftime('%Y-%m-%d  %H:%M:%S UTC') if dt else None
        if updated_dates:
            dt = parse_iso_timestamp(max(updated_dates))
            latest_updated = dt.strftime('%Y-%m-%d  %H:%M:%S UTC') if dt else None

    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Total Assertions", str(len(data['assertions'])))
    with c2:
        metric_card("Created At", latest_created or "—")
    with c3:
        metric_card("Last Updated", latest_updated or "—")

    st.write("")

    # ── Account Summary ───────────────────────────────────────────────────────
    section_header("🏢", "Account Summary")

    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Company", data['company_name'] or "—")
    with c2:
        metric_card("Site ID", data['site_id'] or "—")
    with c3:
        metric_card("Account ID", data['account_id'] or "—")

    st.write("")

    with st.expander("🤖 AI-Generated Summary", expanded=True):
        with st.spinner("Generating summary…"):
            try:
                ai_summary = generate_account_summary(data)
                st.markdown(ai_summary)
            except Exception as e:
                st.error(f"Could not generate AI summary: {e}")
                st.info("Make sure OPENAI_API_KEY is set in your .env file")

    with st.expander("ℹ️ About the Company", expanded=True):
        with st.spinner("Generating company overview…"):
            try:
                company_overview = generate_company_overview(
                    data['company_name'],
                    data['location']['full_address']
                )
                st.markdown(company_overview)
            except Exception as e:
                st.error(f"Could not generate company overview: {e}")

    st.write("")

    # Financials
    st.subheader("Financials")
    finance_events = data['events']['finance']
    if finance_events:
        render_custom_table(
            [{'Type': e['event_type'], 'Value': e['event_type_value'] or 'Not Found'} for e in finance_events],
            ['Type', 'Value'],
            widths=['30%', '70%'],
        )
    else:
        st.markdown('<div class="empty-state">No financial data available</div>', unsafe_allow_html=True)

    # Key Business Activities
    st.subheader("Key Business Activities")
    business_events = data['events']['business']
    if business_events:
        render_custom_table(
            [{'Activity Type': e['event_type'], 'Details': e['event_type_value'] or 'No Information Found'} for e in business_events],
            ['Activity Type', 'Details'],
            widths=['30%', '70%'],
        )
    else:
        st.markdown('<div class="empty-state">No business activity data available</div>', unsafe_allow_html=True)

    st.divider()

    # ── Site Summary ──────────────────────────────────────────────────────────
    section_header("📍", "Site Summary")

    location = data['location']
    facility_type = (location.get('metadata') or {}).get('facility_type', '—')
    site_size_str = f"{data['site_size']:,.0f} sq ft" if data['site_size'] else "—"

    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Address", location['full_address'] or "—")
    with c2:
        metric_card("Facility Type", facility_type)
    with c3:
        metric_card("Size", site_size_str)

    st.write("")

    # Nature of Operations
    st.subheader("Nature of Operations")
    operational_events = data['events']['operational']
    if operational_events:
        render_custom_table(
            [{'Operation Type': e['event_type'], 'Details': str(e['event_type_value']) if e['event_type_value'] else 'Not available'} for e in operational_events],
            ['Operation Type', 'Details'],
            widths=['30%', '70%'],
        )
    else:
        st.markdown('<div class="empty-state">No operational data available</div>', unsafe_allow_html=True)

    # Customers
    st.subheader("Customers")
    customer_events = data['events']['customer']
    if customer_events:
        render_custom_table(
            [{'Type': e['event_type'], 'Details': e['event_type_value'] or 'No Information Found'} for e in customer_events],
            ['Type', 'Details'],
            widths=['30%', '70%'],
        )
    else:
        st.markdown('<div class="empty-state">No customer data available</div>', unsafe_allow_html=True)

    # Type of Inventory
    st.subheader("Type of Inventory")
    inventory_events = [e for e in operational_events if 'inventory' in e['event_type'].lower()]
    if inventory_events:
        render_custom_table(
            [{'Type': e['event_type'], 'Details': e['event_type_value'] or '—'} for e in inventory_events],
            ['Type', 'Details'],
            widths=['30%', '70%'],
        )
    else:
        st.markdown('<div class="empty-state">No inventory data available</div>', unsafe_allow_html=True)

    st.divider()

    # ── Assertions ────────────────────────────────────────────────────────────
    section_header("📋", "Assertions")

    if data['assertions']:
        with st.expander("📊 Assertion Analysis Summary", expanded=True):
            with st.spinner("Analysing assertions…"):
                try:
                    assertion_summary = generate_assertion_summary(data['assertions'])
                    st.markdown(assertion_summary)
                except Exception as e:
                    st.error(f"Could not generate assertion summary: {e}")

        st.write("")

    sorted_assertions = sorted(data['assertions'], key=lambda x: x['net_score'] or 0, reverse=True)

    assertion_rows_html = []
    for i, a in enumerate(sorted_assertions):
        support = f"{a['supporting_score']:.2f}" if a['supporting_score'] is not None else 'N/A'
        oppose  = f"{a['opposing_score']:.2f}"  if a['opposing_score']  is not None else 'N/A'
        net     = f"{a['net_score']:.2f}"        if a['net_score']       is not None else 'N/A'
        assertion_rows_html.append(
            f"<tr>"
            f"<td>{i+1}</td>"
            f"<td>{html_lib.escape(str(a['assertion_text']))}</td>"
            f"<td>{html_lib.escape(str(a['assertion_type']))}</td>"
            f"<td>{html_lib.escape(support)}</td>"
            f"<td>{html_lib.escape(oppose)}</td>"
            f"<td>{html_lib.escape(net)}</td>"
            f"<td>{html_lib.escape(str(a['classification'] or 'UNKNOWN'))}</td>"
            f"</tr>"
        )

    assertions_table_html = f"""<div class="assertions-table-wrapper">
  <table class="assertions-table">
    <thead>
      <tr>
        <th>#</th><th>Assertion</th><th>Type</th>
        <th>Support</th><th>Oppose</th><th>Net</th><th>Classification</th>
      </tr>
    </thead>
    <tbody>{''.join(assertion_rows_html)}</tbody>
  </table>
</div>"""

    try:
        st.html(assertions_table_html)
    except AttributeError:
        st.markdown(assertions_table_html, unsafe_allow_html=True)

else:
    st.markdown(
        '<div class="empty-state" style="padding:4rem 1rem;">'
        '⬆️  Enter a Site ID above and press <strong>Load →</strong> to begin'
        '</div>',
        unsafe_allow_html=True,
    )
