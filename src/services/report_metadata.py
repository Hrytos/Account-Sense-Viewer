"""
Operations report metadata from Supabase (account_sites_report.report_metadata).
Used for teaser generation and section parsing.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.core.clients import get_supabase_client


def normalize_report_metadata(raw: Any) -> Optional[Dict[str, Any]]:
    """Return a dict for JSON/JSONB or JSON string; None if invalid."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def split_section_body(body: str) -> Tuple[str, List[str]]:
    """
    Split section body into narrative prose and risk bullet lines.
    Bullets follow the first block that looks like '- ...' lines after a blank line gap.
    """
    if not body or not str(body).strip():
        return "", []

    text = str(body)
    parts = text.split("\n\n")
    bullet_start: Optional[int] = None

    def is_bullet_line(ln: str) -> bool:
        s = ln.strip()
        return bool(s) and s.startswith("-")

    for i, part in enumerate(parts):
        lines = [ln for ln in part.split("\n") if ln.strip()]
        if not lines:
            continue
        if all(is_bullet_line(ln) for ln in lines):
            bullet_start = i
            break

    if bullet_start is None:
        return text.strip(), []

    narrative = "\n\n".join(parts[:bullet_start]).strip()
    bullet_text = "\n\n".join(parts[bullet_start:])
    bullets: List[str] = []
    for ln in bullet_text.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if s.startswith("- "):
            bullets.append(s[2:].strip())
        elif s.startswith("-"):
            bullets.append(s[1:].strip())

    return narrative, bullets


_EPOCH_MIN = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _parse_generated_at(meta: Dict[str, Any]) -> datetime:
    raw = meta.get("generated_at")
    if not raw:
        return _EPOCH_MIN
    s = str(raw).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return _EPOCH_MIN


async def fetch_latest_report_metadata(site_id: str) -> Optional[Dict[str, Any]]:
    """
    Load report_metadata for the latest operations report for this site.
    Rows are ordered by generated_at inside the JSON when multiple rows exist.
    """
    site_id = (site_id or "").strip()
    if not site_id:
        return None

    supabase = get_supabase_client()

    def run_exec():
        return (
            supabase.table("account_sites_report")
            .select("report_metadata")
            .eq("site_id", site_id)
            .execute()
        )

    res = await asyncio.to_thread(run_exec)
    rows = res.data or []
    if not rows:
        return None

    best: Optional[Dict[str, Any]] = None
    best_dt: Optional[datetime] = None

    for row in rows:
        raw = row.get("report_metadata")
        meta = normalize_report_metadata(raw)
        if not meta:
            continue
        dt = _parse_generated_at(meta)
        if best is None or (best_dt is not None and dt > best_dt):
            best = meta
            best_dt = dt

    return best


def build_teaser_context_lines(metadata: Dict[str, Any]) -> List[str]:
    """Flatten metadata for the LLM: only `sections[]` (full content per section, no truncation)."""
    lines: List[str] = []
    sections = metadata.get("sections") or []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        sid = sec.get("id", "")
        heading = sec.get("heading", "")
        sub = sec.get("subheading", "")
        body = sec.get("body")
        if body is None:
            body = ""
        else:
            body = str(body)

        lines.append("")
        lines.append(f"## {heading}" + (f" ({sid})" if sid else ""))
        if sub:
            lines.append(sub)
        if body:
            lines.append(body)

        _known = {"id", "heading", "subheading", "body"}
        for key, val in sec.items():
            if key in _known or val is None:
                continue
            if isinstance(val, (dict, list)):
                lines.append(f"{key}: {json.dumps(val, ensure_ascii=False)}")
            else:
                lines.append(f"{key}: {val}")
    return lines
