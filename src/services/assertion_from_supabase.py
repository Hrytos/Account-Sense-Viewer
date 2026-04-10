"""
Assertion Files Service
Fetches supporting/opposing markdown outputs for a given assertion from Supabase Storage.
"""

from __future__ import annotations

import os
from typing import Dict, Literal

from src.core.clients import get_supabase_client


class AssertionFilesClient:
    def __init__(self) -> None:
        # Supabase Storage bucket name. Keep the key paths identical to prior S3 keys.
        bucket = (
            os.getenv("ASSERTION_STORAGE_BUCKET")
            or os.getenv("ASSERTION_SUPABASE_BUCKET")
            or os.getenv("ASSERTION_FILES_BUCKET")
            or "assertions"
        )
        self.bucket = bucket
        self.supabase = get_supabase_client()

    def _build_key(
        self,
        company_slug: str,
        site_id: str,
        assertion_id: str,
        variant: Literal["supporting", "opposing"],
    ) -> str:
        site_id_underscored = site_id.replace("-", "_")
        assertion_id_underscored = assertion_id.replace("-", "_")

        if variant == "supporting":
            middle = "supporting_output"
            filename = f"{company_slug}_{site_id_underscored}_{assertion_id_underscored}_supporting.md"
        else:
            middle = "opposing_output"
            filename = f"{company_slug}_{site_id_underscored}_{assertion_id_underscored}_opposing.md"

        return (
            f"company_assertions/{company_slug}/{site_id}/outputs/{middle}/"
            f"{company_slug}/{filename}"
        )

    def fetch_markdown(
        self,
        company_slug: str,
        site_id: str,
        assertion_id: str,
        variant: Literal["supporting", "opposing"],
    ) -> str:
        key = self._build_key(company_slug, site_id, assertion_id, variant)
        print(f"[AssertionFiles] Fetching {variant} evidence from bucket '{self.bucket}': {key}")
        data = self.supabase.storage.from_(self.bucket).download(key)
        if isinstance(data, bytes):
            return data.decode("utf-8")
        return bytes(data).decode("utf-8")


_client: AssertionFilesClient | None = None


def get_assertion_files_client() -> AssertionFilesClient:
    global _client
    if _client is None:
        _client = AssertionFilesClient()
    return _client


def fetch_supporting_and_opposing(
    company_slug: str,
    site_id: str,
    assertion_id: str,
) -> Dict[str, str]:
    # Hardcoded slug overrides for specific site_ids
    SITE_SLUG_OVERRIDES = {
        "8ee0c462-d914-4d12-8085-c56986450221": "bda",
        "92000d6f-7321-434d-8ad0-cde1575c3c5b": "saltbox_ga",
        "bc669593-c315-4ab7-8c61-27a9e88820b0": "saltbox_ga",
        "8a726b0d-dc12-4e6b-ab09-db61bce5480b": "saltbox_ga",
        "6b7d2d8f-87bb-440a-8c3c-feac52f42fe2": "advance_auto_parts",
        "7ac021d3-62cb-4637-a42d-4835780fbd29": "leonard_s_express",
        "600a9c42-cc7c-4f85-830a-d035d8e97a93": "empire_office",
        "6791cf4f-87e8-4bfa-addb-105dee089966": "mclane_company",
    }
    
    # Override slug if site_id has a hardcoded mapping
    if site_id in SITE_SLUG_OVERRIDES:
        company_slug = SITE_SLUG_OVERRIDES[site_id]
    
    client = get_assertion_files_client()
    supporting_md = client.fetch_markdown(company_slug, site_id, assertion_id, "supporting")
    opposing_md = client.fetch_markdown(company_slug, site_id, assertion_id, "opposing")
    return {"supporting": supporting_md, "opposing": opposing_md}
