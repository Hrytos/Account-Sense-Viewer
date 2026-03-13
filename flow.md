# Account Sense Viewer: System Flow

## [1] User Input
User enters a `site_id` in the Streamlit UI (app/streamlit_app.py).

## [2] Data Fetching (src/services/data_fetcher.py)
The app calls `get_site_data`, which executes the following flow:

### A. Initial Lookup (Sequential)
1. Query `view_account_site_size` to resolve `account_id`, `company_name`, and `site_size`.

### B. Concurrent Fetching (asyncio.gather)
The following tables are queried in parallel to minimize latency:
1. `account_sites` (Location details)
2. `account_sites_assertion` (Assertion scores & metadata)
3. `account_event_operational` (Operational & inventory data)
4. `account_event_finance` (Financial KPIs)
5. `account_event_business` (Business highlights)
6. `account_event_customer` (Customer/3PL status)

## [3] AI Analysis (src/services/ai_summarizer.py)
Once data is retrieved, the app triggers three asynchronous AI tasks using GPT-4o mini:
1. **Account Summary**: Overall business analysis.
2. **Company Overview**: General background based on name/location.
3. **Assertion Analysis**: Narrative explaining the evidence patterns.

## [4] UI Rendering
The processed data and AI insights are displayed in the interactive Streamlit dashboard.