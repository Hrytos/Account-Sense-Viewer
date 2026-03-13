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

    def run_exec():
        return (
            supabase.table("view_account_site_size")
            .select("account_id, company_name")
            .order("company_name")
            .execute()
        )

    res = await asyncio.to_thread(run_exec)
    rows = res.data or []

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
    Return all sites for a given account_id from view_account_site_size.
    Each site entry includes basic fields for UI cards.
    """
    supabase = get_supabase_client()

    def run_exec_sites():
        return (
            supabase.table("view_account_site_size")
            .select("site_id, account_id, company_name, site_size_value, metadata")
            .eq("account_id", account_id)
            .execute()
        )

    sites_res = await asyncio.to_thread(run_exec_sites)
    rows = sites_res.data or []

    # Build assertion counts per site_id using a single IN query on site_ids
    assertion_counts: Dict[str, int] = {}
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

    sites: List[Dict] = []
    for row in rows:
        metadata = row.get("metadata") or {}
        full_address = None
        if isinstance(metadata, dict):
            full_address = metadata.get("full_address")

        size_val = row.get("site_size_value")
        site_size_str = f"{size_val:,.0f} sq ft" if isinstance(size_val, (int, float)) else None

        site_id = row.get("site_id")
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
            }
        )

    return sites


async def get_site_data(site_id: str) -> dict:
    """
    Fetch all data for a given site_id from Supabase in parallel.
    Fully async — awaitable directly in FastAPI route handlers.
    """
    supabase = get_supabase_client()

    # Initial lookup is the dependency for all subsequent parallel queries
    site_view = await asyncio.to_thread(
        lambda: supabase.table("view_account_site_size")
        .select("site_id, account_id, company_name, site_size_value")
        .eq("site_id", site_id)
        .execute()
    )

    if not site_view.data:
        raise ValueError(f"Site {site_id} not found in view_account_site_size")

    site_info    = site_view.data[0]
    account_id   = site_info["account_id"]
    company_name = site_info["company_name"]
    site_size    = site_info["site_size_value"]

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
    location_res, assertions_raw, finance_res, business_res, operational_res, customer_res = results

    assertions = []
    for item in assertions_raw.data:
        detail = item["assertions"]
        assertions.append({
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
        "company_name": company_name,
        "site_size":    site_size,
        "location":     location_res.data,
        "assertions":   assertions,
        "events": {
            "finance":     finance_res.data,
            "business":    business_res.data,
            "operational": operational_res.data,
            "customer":    customer_res.data,
        },
    }
