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
from textwrap import dedent
from datetime import datetime
from data_fetcher import get_site_data
from ai_summarizer import generate_account_summary
from about_account import generate_company_overview
from assertion_summary import generate_assertion_summary

# Configure the page
st.set_page_config(
    page_title="Account Sense Viewer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"  # Hide sidebar by default
)

# Add custom CSS for word wrapping in tables
st.markdown("""
<style>
    /* Word wrap for all table cells */
    .stDataFrame div[data-testid="stDataFrameResizable"] div[data-testid="stDataFrameCell"] {
        white-space: normal !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        line-height: 1.4 !important;
        padding: 8px !important;
    }
    
    /* Ensure table cells don't overflow */
    .stDataFrame table {
        table-layout: fixed !important;
    }
    
    .stDataFrame td, .stDataFrame th {
        white-space: normal !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        word-break: break-word !important;
    }
    
    /* Specific styling for assertion column to ensure wrapping */
    .stDataFrame [data-testid="stDataFrameCell"]:nth-child(2) {
        white-space: pre-wrap !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }
</style>
""", unsafe_allow_html=True)


def parse_iso_timestamp(timestamp_str):
    """
    Parse ISO timestamp safely even when fractional seconds are irregular.
    Returns a datetime object or None if parsing fails.
    """
    if not timestamp_str:
        return None

    s = str(timestamp_str).strip()
    if not s:
        return None

    # Normalize Zulu timestamps
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    # Normalize fractional seconds to max 6 digits for datetime.fromisoformat
    # Handles forms like: YYYY-MM-DDTHH:MM:SS(.fraction)?(+/-HH:MM)?
    match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?([+-]\d{2}:\d{2})?$", s)
    if match:
        base, fraction, tz = match.groups()
        tz = tz or "+00:00"
        if fraction:
            fraction_digits = fraction[1:]  # remove dot
            fraction_digits = (fraction_digits + "000000")[:6]  # pad/truncate to 6
            s = f"{base}.{fraction_digits}{tz}"
        else:
            s = f"{base}{tz}"

    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None

# Title - clean and simple
st.title("Account Sense Viewer")
st.markdown("View detailed account and site analysis data")

# Site ID input at the top (no sidebar)
st.markdown("---")
col1, col2 = st.columns([4, 1])
with col1:
    site_id = st.text_input(
        "Enter Site ID",
        value="",
        help="Enter the UUID of the site you want to analyze",
        key="site_id_input",
        placeholder="e.g., d80e7532-2253-4c53-a31b-90e05dfb98d8"
    )
with col2:
    st.write("")  # Spacing
    st.write("")  # Spacing to align button
    load_button = st.button("Load Site Data", type="primary", use_container_width=True)

# Button to fetch data
if load_button:
    with st.spinner("Fetching data from Supabase..."):
        try:
            # Fetch data
            data = get_site_data(site_id)
            
            # Store in session state
            st.session_state['data'] = data
            st.session_state['loaded'] = True
            st.success("✓ Data loaded successfully!")
            
        except Exception as e:
            st.error(f"Error loading data: {e}")
            
            # Show more detailed error information
            if "403" in str(e) or "Forbidden" in str(e):
                st.warning("""
                **403 Forbidden Error - Possible Causes:**
                
                1. **Row Level Security (RLS) Policies**: The Supabase tables may have RLS enabled that's blocking access
                2. **API Key Permissions**: The API key may not have sufficient permissions
                3. **Table Access**: The service role key should bypass RLS, but policies may need to be updated
                
                **Solutions:**
                - Check Supabase dashboard → Authentication → Policies
                - Verify the API key is a `service_role` key (not `anon` key)
                - Disable RLS temporarily for testing, or add policies to allow service_role access
                - Contact your Supabase admin to grant access to these tables:
                  - `view_account_site_size`
                  - `account_sites`
                  - `account_sites_assertion`
                  - `assertions`
                  - `account_event_finance`
                  - `account_event_business`
                  - `account_event_operational`
                  - `account_event_customer`
                """)
            
            st.session_state['loaded'] = False

# Check if data is loaded
if st.session_state.get('loaded', False):
    data = st.session_state['data']
    
    # ==================== RUN DETAILS ====================
    st.header("Run Details")
    
    # Initialize variables
    latest_created = None
    latest_updated = None
    
    # Get assertion timestamps
    if data['assertions']:
        created_dates = [a['created_at'] for a in data['assertions'] if a['created_at']]
        updated_dates = [a['updated_at'] for a in data['assertions'] if a['updated_at']]
        
        if created_dates:
            latest_created = max(created_dates)
            created_dt = parse_iso_timestamp(latest_created)
            if created_dt:
                latest_created = created_dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                latest_created = None
        
        if updated_dates:
            latest_updated = max(updated_dates)
            updated_dt = parse_iso_timestamp(latest_updated)
            if updated_dt:
                latest_updated = updated_dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                latest_updated = None
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Total Assertions:** {len(data['assertions'])}")
        if latest_created:
            st.write(f"**Created At:** {latest_created}")
    
    with col2:
        if latest_updated:
            st.write(f"**Updated At:** {latest_updated}")
    
    st.divider()
    
    # ==================== ACCOUNT SUMMARY ====================
    st.header("Account Summary")
    
    # Show company, site_id, account_id
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Company:** {data['company_name']}")
    with col2:
        st.write(f"**Site ID:** {data['site_id']}")
    with col3:
        st.write(f"**Account ID:** {data['account_id']}")
    
    st.write("")  # Add spacing
    
    # ==================== AI SUMMARY ====================
    st.subheader("🤖 AI-Generated Summary")
    
    with st.spinner("Generating AI summary with GPT-4o mini..."):
        try:
            ai_summary = generate_account_summary(data)
            st.markdown(ai_summary)
        except Exception as e:
            st.error(f"Could not generate AI summary: {e}")
            st.info("Make sure OPENAI_API_KEY is set in your .env file")
    
    st.write("")  # Add spacing
    
    # ==================== ABOUT THE COMPANY ====================
    st.subheader("ℹ️ About the Company")
    
    with st.spinner("Generating company overview..."):
        try:
            company_overview = generate_company_overview(
                data['company_name'],
                data['location']['full_address']
            )
            st.markdown(company_overview)
        except Exception as e:
            st.error(f"Could not generate company overview: {e}")
    
    st.write("")  # Add spacing
    
    # Financials
    st.subheader("Financials")
    finance_events = data['events']['finance']
    
    if finance_events:
        # Create DataFrame for financials
        finance_df = pd.DataFrame([
            {
                'Type': event['event_type'],
                'Value': event['event_type_value'] or 'Not Found'
            }
            for event in finance_events
        ])
        st.dataframe(finance_df, use_container_width=True, hide_index=True)
    else:
        st.info("No financial data available")
    
    # Business Activities
    st.subheader("Key Business Activities")
    business_events = data['events']['business']
    
    if business_events:
        # Create DataFrame for business activities
        business_df = pd.DataFrame([
            {
                'Activity Type': event['event_type'],
                'Details': event['event_type_value'] or 'No Information Found'
            }
            for event in business_events
        ])
        st.dataframe(business_df, use_container_width=True, hide_index=True)
    else:
        st.info("No business activity data available")
    
    st.divider()
    
    # ==================== SITE SUMMARY ====================
    st.header("Site Summary")
    
    # Location
    st.subheader("Location")
    location = data['location']
    st.write(f"**Address:** {location['full_address']}")
    if location['metadata'] and 'facility_type' in location['metadata']:
        st.write(f"**Facility Type:** {location['metadata']['facility_type']}")
    
    # Size
    st.subheader("Size")
    if data['site_size']:
        st.write(f"{data['site_size']:,.0f} square feet")
    else:
        st.write("Size data not available")
    
    # Nature of Operations - SHOW ALL EVENTS
    st.subheader("Nature of Operations")
    operational_events = data['events']['operational']
    
    if operational_events:
        # Show ALL operational events in a table
        ops_df = pd.DataFrame([
            {
                'Operation Type': event['event_type'],
                'Details': str(event['event_type_value']) if event['event_type_value'] else 'Not available'
            }
            for event in operational_events
        ])
        st.dataframe(ops_df, use_container_width=True, hide_index=True, height=400)
    else:
        st.write("No operational data available")
    
    # Customers
    st.subheader("Customers")
    customer_events = data['events']['customer']
    
    if customer_events:
        # Display 3PL status
        for event in customer_events:
            if event['metadata'] and 'is_3pl' in event['metadata']:
                is_3pl = event['metadata']['is_3pl']
                st.write(f"**3PL Status:** {'Yes' if is_3pl else 'No'}")
                break
        
        # Display key customers if available
        key_customers = []
        for event in customer_events:
            if event['metadata'] and 'key_customers' in event['metadata']:
                key_customers = event['metadata']['key_customers']
                break
        
        if key_customers:
            st.write("")  # Add spacing
            st.write("**Key Customers:**")
            
            # Create a DataFrame for key customers
            customers_df = pd.DataFrame([
                {
                    'Company': customer.get('company_name', 'N/A'),
                    'Category': customer.get('category', 'N/A').upper()
                }
                for customer in key_customers
            ])
            st.dataframe(customers_df, use_container_width=True, hide_index=True)
    else:
        st.write("No customer data available")
    
    # Type of Inventory
    st.subheader("Type of Inventory")
    inventory_events = [e for e in operational_events if 'inventory' in e['event_type'].lower()]
    
    if inventory_events:
        for event in inventory_events:
            st.write(f"**{event['event_type']}:** {event['event_type_value']}")
    else:
        st.write("No inventory data available")
    
    st.divider()
    
    # ==================== ASSERTIONS - LIST VIEW ====================
    st.header("Assertions - List View")
    
    # ==================== ASSERTION SUMMARY ====================
    if data['assertions']:
        st.subheader("📊 Assertion Analysis Summary")
        
        with st.spinner("Analyzing assertions with GPT-4o mini..."):
            try:
                assertion_summary = generate_assertion_summary(data['assertions'])
                st.markdown(assertion_summary)
            except Exception as e:
                st.error(f"Could not generate assertion summary: {e}")
        
        st.write("")  # Add spacing
        st.markdown("---")
        st.write("")  # Add spacing
    
    # Sort assertions by net score
    sorted_assertions = sorted(data['assertions'], key=lambda x: x['net_score'] or 0, reverse=True)
    
    # Create DataFrame for assertions
    assertions_df = pd.DataFrame([
        {
            '#': i + 1,
            'Assertion': a['assertion_text'],
            'Type': a['assertion_type'],
            'Support': f"{a['supporting_score']:.2f}" if a['supporting_score'] is not None else 'N/A',
            'Oppose': f"{a['opposing_score']:.2f}" if a['opposing_score'] is not None else 'N/A',
            'Net': f"{a['net_score']:.2f}" if a['net_score'] is not None else 'N/A',
            'Classification': a['classification'] or 'UNKNOWN'
        }
        for i, a in enumerate(sorted_assertions)
    ])
    
    # Display assertions with wrapped text while keeping Streamlit-like colors.
    assertion_rows_html = []
    for _, row in assertions_df.iterrows():
        assertion_rows_html.append(
            f"<tr>"
            f"<td>{html_lib.escape(str(row['#']))}</td>"
            f"<td>{html_lib.escape(str(row['Assertion']))}</td>"
            f"<td>{html_lib.escape(str(row['Type']))}</td>"
            f"<td>{html_lib.escape(str(row['Support']))}</td>"
            f"<td>{html_lib.escape(str(row['Oppose']))}</td>"
            f"<td>{html_lib.escape(str(row['Net']))}</td>"
            f"<td>{html_lib.escape(str(row['Classification']))}</td>"
            f"</tr>"
        )

    assertions_table_html = dedent(f"""
    <style>
        .assertions-table-wrapper {{
            width: 100%;
            overflow-x: auto;
            border: 1px solid rgba(127, 127, 127, 0.25);
            border-radius: 0.5rem;
        }}
        .assertions-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            font-size: 0.875rem;
            color: inherit;
        }}
        .assertions-table th, .assertions-table td {{
            border-bottom: 1px solid rgba(127, 127, 127, 0.2);
            padding: 0.55rem 0.6rem;
            vertical-align: top;
            text-align: left;
            white-space: normal;
            word-break: break-word;
            overflow-wrap: anywhere;
            color: inherit;
            background: transparent;
            line-height: 1.35;
        }}
        .assertions-table th {{
            font-weight: 600;
            background: rgba(127, 127, 127, 0.08);
        }}
        .assertions-table tr:hover td {{
            background: rgba(127, 127, 127, 0.06);
        }}
        .assertions-table th:nth-child(1), .assertions-table td:nth-child(1) {{ width: 4%; }}
        .assertions-table th:nth-child(2), .assertions-table td:nth-child(2) {{ width: 49%; }}
        .assertions-table th:nth-child(3), .assertions-table td:nth-child(3) {{ width: 10%; }}
        .assertions-table th:nth-child(4), .assertions-table td:nth-child(4) {{ width: 8%; }}
        .assertions-table th:nth-child(5), .assertions-table td:nth-child(5) {{ width: 8%; }}
        .assertions-table th:nth-child(6), .assertions-table td:nth-child(6) {{ width: 6%; }}
        .assertions-table th:nth-child(7), .assertions-table td:nth-child(7) {{ width: 15%; }}
    </style>
    <div class="assertions-table-wrapper">
        <table class="assertions-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Assertion</th>
                    <th>Type</th>
                    <th>Support</th>
                    <th>Oppose</th>
                    <th>Net</th>
                    <th>Classification</th>
                </tr>
            </thead>
            <tbody>
                {''.join(assertion_rows_html)}
            </tbody>
        </table>
    </div>
    """)
    st.markdown(assertions_table_html, unsafe_allow_html=True)

else:
    # Show instructions when no data is loaded
    st.info("Enter a Site ID in the sidebar and click 'Load Site Data' to begin")
