"""
Data Fetcher Service
Fetches site and account data from Supabase in parallel.
Also exposes helpers for listing companies and sites.
"""

import asyncio
from typing import List, Dict

from src.core.clients import get_supabase_client


async def list_companies() -> List[Dict]:
    """
    Return a de-duplicated, alphabetically sorted list of companies.
    Each entry has: account_id, company_name.
    """
    supabase = get_supabase_client()

    # Supabase/PostgREST commonly caps rows per request; page through all companies.
    page_size = 1000
    start = 0
    rows: List[Dict] = []
    while True:
        end = start + page_size - 1
        def run_exec_page():
            return (
                supabase.table("account_sites")
                .select("account_id, company_name")
                .eq("is_archived", False)
                .order("company_name")
                .range(start, end)
                .execute()
            )

        res = await asyncio.to_thread(run_exec_page)
        batch = res.data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    # De-duplicate by account_id, keep first occurrence (already ordered by name)
    seen = {}
    for row in rows:
        acc_id = row.get("account_id")
        name = row.get("company_name")
        if not acc_id or not name:
            continue
        if acc_id not in seen:
            seen[acc_id] = {"account_id": acc_id, "company_name": name}

    return list(seen.values())


async def list_sites_for_account(account_id: str) -> List[Dict]:
    """
    Return all active sites for a given account_id from account_sites.
    Each site entry includes basic fields for UI cards.
    """
    supabase = get_supabase_client()

    def run_exec_sites():
        return (
            supabase.table("account_sites")
            .select("site_id, account_id, company_name, full_address, metadata")
            .eq("is_archived", False)
            .eq("account_id", account_id)
            .order("created_at", desc=True)
            .execute()
        )

    sites_res = await asyncio.to_thread(run_exec_sites)
    rows = sites_res.data or []

    # Build assertion counts and OFI scores per site_id using single IN queries
    assertion_counts: Dict[str, int] = {}
    ofi_scores: Dict[str, float] = {}
    site_ids = [row.get("site_id") for row in rows if row.get("site_id")]
    
    if site_ids:
        def run_exec_assertions():
            return (
                supabase.table("account_sites_assertion")
                .select("site_id")
                .in_("site_id", site_ids)
                .execute()
            )

        assertions_res = await asyncio.to_thread(run_exec_assertions)
        
        for row in assertions_res.data or []:
            sid = row.get("site_id")
            if not sid:
                continue
            assertion_counts[sid] = assertion_counts.get(sid, 0) + 1

        def run_exec_scores():
            return (
                supabase.table("account_sites_report")
                .select("site_id, ofi_score")
                .in_("site_id", site_ids)
                .eq("is_archived", False)
                .execute()
            )

        scores_res = await asyncio.to_thread(run_exec_scores)
        for row in scores_res.data or []:
            sid = row.get("site_id")
            score = row.get("ofi_score")
            if not sid or score is None:
                continue
            ofi_scores[sid] = score
        
    sites: List[Dict] = []
    for row in rows:
        site_id = row.get("site_id")
        full_address = row.get("full_address")
        metadata = row.get("metadata") or {}
        size_val = None
        if isinstance(metadata, dict):
            size_val = (
                metadata.get("site_size_value")
                or metadata.get("site_size")
                or metadata.get("square_footage")
            )
        site_size_str = f"{size_val:,.0f} sq ft" if isinstance(size_val, (int, float)) else None

        assertion_count = assertion_counts.get(site_id, 0)

        sites.append(
            {
                "site_id": site_id,
                "account_id": row.get("account_id"),
                "company_name": row.get("company_name"),
                "full_address": full_address,
                "site_size_value": size_val,
                "site_size_str": site_size_str,
                "assertion_count": assertion_count,
                "ofi_score": ofi_scores.get(site_id),
            }
        )

    return sites


async def get_site_data(site_id: str) -> dict:
    """
    Fetch all data for a given site_id from Supabase in parallel.
    Fully async — awaitable directly in FastAPI route handlers.
    """
    supabase = get_supabase_client()

    site_info = None
    account_id = None
    company_name = None
    site_size = None

    # Primary source: account_sites
    site_base = await asyncio.to_thread(
        lambda: supabase.table("account_sites")
        .select("site_id, account_id, company_name, metadata")
        .eq("site_id", site_id)
        .limit(1)
        .execute()
    )
    if not site_base.data:
        raise ValueError(f"Site {site_id} not found in account_sites")

    site_info = site_base.data[0]
    account_id = site_info.get("account_id")
    company_name = site_info.get("company_name")
    metadata = site_info.get("metadata") or {}
    if isinstance(metadata, dict):
        site_size = (
            metadata.get("site_size_value")
            or metadata.get("site_size")
            or metadata.get("square_footage")
        )

    # Optional enrichment from view_account_site_size
    site_view = await asyncio.to_thread(
        lambda: supabase.table("view_account_site_size")
        .select("site_id, account_id, company_name, site_size_value")
        .eq("site_id", site_id)
        .limit(1)
        .execute()
    )
    if site_view.data:
        site_view_row = site_view.data[0]
        company_name = site_view_row.get("company_name")
        if site_size is None:
            site_size = site_view_row.get("site_size_value")

    # Optional site-level score from account_sites_report
    site_report = await asyncio.to_thread(
        lambda: supabase.table("account_sites_report")
        .select("ofi_score")
        .eq("site_id", site_id)
        .eq("is_archived", False)
        .limit(1)
        .execute()
    )
    ofi_score = None
    if site_report.data:
        ofi_score = site_report.data[0].get("ofi_score")

    if not account_id:
        raise ValueError(f"Site {site_id} has no account_id in source data")

    async def fetch_query(table_name, select_val, filter_col=None, filter_val=None, single=False):
        def run_exec():
            q = supabase.table(table_name).select(select_val)
            if filter_col and filter_val:
                q = q.eq(filter_col, filter_val)
            if single:
                q = q.single()
            return q.execute()
        return await asyncio.to_thread(run_exec)

    tasks = [
        # Location (site-level)
        fetch_query("account_sites", "street, city, state, zip, country, full_address, metadata", "site_id", site_id, single=True),
        # Account (account-level)
        fetch_query("accounts", "linkedin_url, account_domain", "account_id", account_id, single=True),
        # Assertions (site-level)
        fetch_query("account_sites_assertion", "*, assertions(*)", "site_id", site_id),
        # Finance events (account-level)
        fetch_query("account_event_finance", "event_type, event_type_value, verified, metadata", "account_id", account_id),
        # Business events (account-level)
        fetch_query("account_event_business", "event_type, event_type_value, verified, metadata", "account_id", account_id),
        # Operational events (site-level)
        fetch_query("account_event_operational", "event_type, event_type_value, verified, metadata", "site_id", site_id),
        # Customer events (account-level)
        fetch_query("account_event_customer", "event_type, event_type_value, verified, metadata", "account_id", account_id),
    ]

    results = await asyncio.gather(*tasks)
    location_res, account_res, assertions_raw, finance_res, business_res, operational_res, customer_res = results
    account_data = account_res.data or {}
    account_domain = account_data.get("account_domain")
    resolved_company_name = (
        company_name
        or "Unknown Company"
    )

    assertions = []
    for item in (assertions_raw.data or []):
        detail = item["assertions"]
        assertions.append({
            "assertion_id":     item.get("assertion_id"),
            "assertion_text":  detail["Assertion"],
            "assertion_type":  detail["assertion_type"],
            "supporting_score": item["supporting_score"],
            "opposing_score":   item["opposing_score"],
            "net_score":        item["net_statement_score"],
            "classification":   item["statement_support_classification"],
            "created_at":       item["created_at"],
            "updated_at":       item["updated_at"],
        })

    return {
        "site_id":      site_id,
        "account_id":   account_id,
        "company_name": resolved_company_name,
        "site_size":    site_size,
        "ofi_score":    ofi_score,
        "location":     location_res.data,
        "linkedin_url": (account_res.data or {}).get("linkedin_url"),
        "account_domain": account_domain,
        "assertions":   assertions,
        "events": {
            "finance":     finance_res.data,
            "business":    business_res.data,
            "operational": operational_res.data,
            "customer":    customer_res.data,
        },
    }
