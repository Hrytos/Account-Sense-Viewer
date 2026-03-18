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
    client = get_assertion_files_client()
    supporting_md = client.fetch_markdown(company_slug, site_id, assertion_id, "supporting")
    opposing_md = client.fetch_markdown(company_slug, site_id, assertion_id, "opposing")
    return {"supporting": supporting_md, "opposing": opposing_md}
