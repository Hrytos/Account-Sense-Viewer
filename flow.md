User Input: site_id
     ↓
[1] Query view_account_site_size (site_id)
     → Get: account_id, company_name, site_size_value
     ↓
[2] Query account_sites (site_id) ← SITE LEVEL
     → Get: Location data
     ↓
[3] Query account_sites_assertion (site_id) ← SITE LEVEL
     → Get: Scores, timestamps
     → For each assertion_id, query assertions table
        → Get: Assertion text, type
     ↓
[4] Query account_event_operational (site_id) ← SITE LEVEL
     → Get: Operations, inventory
     ↓
[5] Query account_event_finance (account_id) ← ACCOUNT LEVEL
     → Get: Financials
     ↓
[6] Query account_event_business (account_id) ← ACCOUNT LEVEL
     → Get: Business activities
     ↓
[7] Query account_event_customer (account_id) ← ACCOUNT LEVEL
     → Get: Customer info
     ↓
Display all data in UI