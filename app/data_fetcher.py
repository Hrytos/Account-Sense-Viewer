"""
Data Fetcher Module
This module fetches all the data we need from Supabase for a given site_id.
All operations are READ-ONLY - we never modify the database.
"""

from supabase import create_client
import os
from dotenv import load_dotenv


def get_supabase_client():
    """
    Create and return a Supabase client using credentials from .env file.
    This client is used to query the database.
    """
    # Load environment variables from .env file
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(env_path)
    
    # Get credentials from environment variables
    supabase_url = os.getenv('supabase_url') or os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('supabase_key') or os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        raise ValueError("Missing Supabase credentials in .env file. Please check supabase_url and supabase_key are set.")
    
    # Create and return the Supabase client
    # With the latest versions (httpx >= 0.26, supabase >= 2.0), this should work
    return create_client(supabase_url, supabase_key)


def get_site_data(site_id):
    """
    Fetch all data for a given site_id from Supabase.
    
    This function:
    1. Looks up the site in view_account_site_size to get account_id and size
    2. Gets location details from account_sites
    3. Gets all assertions with their scores
    4. Gets all events (finance, business, operational, customer)
    
    Args:
        site_id (str): The UUID of the site to look up
        
    Returns:
        dict: A dictionary containing all the site data organized by category
    """
    # Initialize Supabase client
    supabase = get_supabase_client()
    
    print(f"Fetching data for site_id: {site_id}")
    
    # STEP 1: Get site_id, account_id, and size from the view
    # This is our primary lookup table
    print("  → Looking up site in view_account_site_size...")
    site_view = supabase.table('view_account_site_size') \
        .select('site_id, account_id, company_name, site_size_value') \
        .eq('site_id', site_id) \
        .execute()
    
    if not site_view.data:
        raise ValueError(f"Site {site_id} not found in view_account_site_size")
    
    site_info = site_view.data[0]
    account_id = site_info['account_id']
    company_name = site_info['company_name']
    site_size = site_info['site_size_value']
    
    print(f"  ✓ Found: {company_name}")
    print(f"  ✓ Account ID: {account_id}")
    print(f"  ✓ Site Size: {site_size} sq ft" if site_size else "  ✓ Site Size: Not available")
    
    # STEP 2: Get location details from account_sites
    print("  → Fetching location details...")
    location = supabase.table('account_sites') \
        .select('street, city, state, zip, country, full_address, metadata') \
        .eq('site_id', site_id) \
        .single() \
        .execute()
    
    # STEP 3: Get all assertions for this site with their details
    # We join with the assertions table to get the assertion text and type
    print("  → Fetching assertions...")
    assertions_raw = supabase.table('account_sites_assertion') \
        .select('*, assertions(*)') \
        .eq('site_id', site_id) \
        .execute()
    
    # Transform assertions into a cleaner format
    assertions = []
    for item in assertions_raw.data:
        assertion_detail = item['assertions']
        assertions.append({
            'assertion_text': assertion_detail['Assertion'],
            'assertion_type': assertion_detail['assertion_type'],
            'supporting_score': item['supporting_score'],
            'opposing_score': item['opposing_score'],
            'net_score': item['net_statement_score'],
            'classification': item['statement_support_classification'],
            'created_at': item['created_at'],
            'updated_at': item['updated_at']
        })
    
    print(f"  ✓ Found {len(assertions)} assertions")
    
    # STEP 4: Get finance events (account level)
    print("  → Fetching finance events...")
    finance_events = supabase.table('account_event_finance') \
        .select('event_type, event_type_value, verified, metadata') \
        .eq('account_id', account_id) \
        .execute()
    
    # STEP 5: Get business events (account level)
    print("  → Fetching business events...")
    business_events = supabase.table('account_event_business') \
        .select('event_type, event_type_value, verified, metadata') \
        .eq('account_id', account_id) \
        .execute()
    
    # STEP 6: Get operational events (site level)
    print("  → Fetching operational events...")
    operational_events = supabase.table('account_event_operational') \
        .select('event_type, event_type_value, verified, metadata') \
        .eq('site_id', site_id) \
        .execute()
    
    # STEP 7: Get customer events (account level)
    print("  → Fetching customer events...")
    customer_events = supabase.table('account_event_customer') \
        .select('event_type, event_type_value, verified, metadata') \
        .eq('account_id', account_id) \
        .execute()
    
    print("✓ All data fetched successfully!\n")
    
    # Return all data in an organized dictionary
    return {
        'site_id': site_id,
        'account_id': account_id,
        'company_name': company_name,
        'site_size': site_size,
        'location': location.data,
        'assertions': assertions,
        'events': {
            'finance': finance_events.data,
            'business': business_events.data,
            'operational': operational_events.data,
            'customer': customer_events.data
        }
    }
