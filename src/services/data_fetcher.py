"""
Data Fetcher Service
Fetches site and account data from Supabase in parallel.
Also exposes helpers for listing companies and sites.
"""

import asyncio
import re
from typing import List, Dict

from src.core.clients import get_supabase_client


def _parse_numeric_site_size(value) -> float | None:
    """
    Best-effort parse for site size values stored as text (e.g. "120000", "120,000",
    "120000 sq ft"). Returns float on success, else None.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().lower()
    if not s:
        return None
    # Remove common units/labels then extract the first numeric token.
    s = s.replace("sqft", " ").replace("sq ft", " ").replace("square feet", " ")
    m = re.search(r"(-?\d[\d,]*\.?\d*)", s)
    if not m:
        return None
    token = m.group(1).replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


async def _fetch_site_size_fallback(supabase, site_id: str) -> float | None:
    """
    Fallback lookup when we can't parse a numeric site size from events.
    Prefers `account_site_size` if it exists; otherwise uses `view_account_site_size`.
    """
    def run_exec(table_name: str):
        return (
            supabase.table(table_name)
            .select("site_size_value")
            .eq("site_id", site_id)
            .limit(1)
            .execute()
        )

    for table_name in ("account_site_size", "view_account_site_size"):
        try:
            res = await asyncio.to_thread(lambda: run_exec(table_name))
            if res.data:
                return res.data[0].get("site_size_value")
        except Exception:
            # Table/view may not exist in some deployments — try the next option.
            continue
    return None


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

    # Build assertion counts, OFI scores, and event-derived site sizes per site_id
    assertion_counts: Dict[str, int] = {}
    ofi_scores: Dict[str, float] = {}
    detector_sizes: Dict[str, float] = {}
    fallback_sizes: Dict[str, float] = {}
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

        def run_exec_size_detector():
            return (
                supabase.table("account_event_operational")
                .select("site_id, event_type, event_type_value")
                .in_("site_id", site_ids)
                .eq("event_type", "Site size detector")
                .execute()
            )

        detector_res = await asyncio.to_thread(run_exec_size_detector)
        for row in detector_res.data or []:
            sid = row.get("site_id")
            if not sid:
                continue
            parsed = _parse_numeric_site_size(row.get("event_type_value"))
            if parsed is None:
                continue
            detector_sizes[sid] = parsed

        # Fallback sizes (table/view) for any sites missing a valid detector size
        missing_for_fallback = [sid for sid in site_ids if sid not in detector_sizes]
        if missing_for_fallback:
            def run_exec_view_fallback(table_name: str):
                return (
                    supabase.table(table_name)
                    .select("site_id, site_size_value")
                    .in_("site_id", missing_for_fallback)
                    .execute()
                )

            used_any = False
            for table_name in ("account_site_size", "view_account_site_size"):
                try:
                    fb_res = await asyncio.to_thread(lambda: run_exec_view_fallback(table_name))
                    used_any = True
                    for r in fb_res.data or []:
                        sid = r.get("site_id")
                        val = r.get("site_size_value")
                        if not sid or val is None:
                            continue
                        fallback_sizes[sid] = val
                    break
                except Exception:
                    continue
            if not used_any:
                fallback_sizes = {}
        
    sites: List[Dict] = []
    for row in rows:
        site_id = row.get("site_id")
        full_address = row.get("full_address")
        metadata = row.get("metadata") or {}
        size_val = detector_sizes.get(site_id)
        if size_val is None and isinstance(metadata, dict):
            size_val = (
                metadata.get("site_size_value")
                or metadata.get("site_size")
                or metadata.get("square_footage")
            )
        if size_val is None:
            size_val = fallback_sizes.get(site_id)
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

    # Prefer event-derived site size when present and parseable
    try:
        detector_event = await asyncio.to_thread(
            lambda: supabase.table("account_event_operational")
            .select("event_type_value")
            .eq("site_id", site_id)
            .eq("event_type", "Site size detector")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if detector_event.data:
            site_size = _parse_numeric_site_size(detector_event.data[0].get("event_type_value"))
    except Exception:
        # If event table/query fails, fall back to existing sources.
        pass

    # Next: site metadata
    if site_size is None and isinstance(metadata, dict):
        site_size = (
            metadata.get("site_size_value")
            or metadata.get("site_size")
            or metadata.get("square_footage")
        )

    # Finally: fallback size table/view (what you called account_site_size)
    if site_size is None:
        site_size = await _fetch_site_size_fallback(supabase, site_id)

    # Optional enrichment from view_account_site_size for company name (keep prior behavior)
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
