#!/usr/bin/env python3
"""
Batch-generate operations report teasers for one or more site IDs.

Uses the same logic as the app: latest account_sites_report per site + OpenAI.

Usage:
  # account_site_ids.csv in repo root (columns include site_id, teaser) — fill teaser column:
  python scripts/generate_teasers_for_sites.py --account-csv --in-place
  python scripts/generate_teasers_for_sites.py --account-csv -o account_site_ids.csv

  # Another account-style CSV (same columns): fill teaser in place on that file
  python scripts/generate_teasers_for_sites.py -f hm_missing_teasers.csv --in-place

  # If ./account_site_ids.csv exists and you pass no IDs and no -f, that file is used automatically.
  # Account CSV: each site_id is one Supabase read + one LLM call; with --in-place or -o, the file
  # is rewritten after each site so progress is saved if the run stops early.

  python scripts/generate_teasers_for_sites.py --csv
      # legacy: reads ./sites.md → two columns site-id, teaser to stdout

  python scripts/generate_teasers_for_sites.py --csv -o teasers.csv
  python scripts/generate_teasers_for_sites.py <site_uuid> [<site_uuid> ...] --csv
  python scripts/generate_teasers_for_sites.py -f path/to/list.txt --csv

With no positional IDs and no -f: prefers ./account_site_ids.csv (site_id column) if present;
otherwise ./sites.md (one site id per line; markdown list lines like "- uuid" are OK).

Requires env: SUPABASE_URL/SUPABASE_KEY, OPENAI_API_KEY (same as the app).
Loads .env from the project root if present.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SITES_FILE = os.path.join(ROOT, "sites.md")
DEFAULT_ACCOUNT_SITE_IDS_CSV = os.path.join(ROOT, "account_site_ids.csv")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from src.services.report_metadata import fetch_latest_report_metadata
from src.services.ai_summarizer import generate_operations_teaser_variations


async def teaser_for_site(site_id: str) -> dict:
    site_id = (site_id or "").strip()
    if not site_id:
        return {"site_id": "", "error": "empty site_id", "teaser": []}

    meta = await fetch_latest_report_metadata(site_id)
    if not meta:
        return {"site_id": site_id, "error": "no report_metadata for this site", "teaser": []}
    if not meta.get("sections"):
        return {"site_id": site_id, "error": "report has no sections", "teaser": []}

    try:
        texts = generate_operations_teaser_variations(meta)
    except Exception as e:
        return {"site_id": site_id, "error": str(e), "teaser": []}

    return {"site_id": site_id, "teaser": texts}


def _line_to_site_id(line: str) -> str:
    s = line.strip()
    if not s or s.startswith("#"):
        return ""
    if s.startswith("- "):
        s = s[2:].strip()
    elif s.startswith("* "):
        s = s[2:].strip()
    else:
        m = re.match(r"^\d+\.\s+(.*)$", s)
        if m:
            s = m.group(1).strip()
    return s


def read_site_ids_from_file(path: str) -> list[str]:
    out: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            sid = _line_to_site_id(line)
            if sid:
                out.append(sid)
    return out


def _find_header_col(fieldnames: list[str], logical: str) -> str | None:
    want = logical.lower()
    for f in fieldnames or []:
        if f and f.strip().lower() == want:
            return f
    return None


def csv_file_has_site_id_column(path: str) -> bool:
    try:
        with open(path, encoding="utf-8", newline="") as f:
            first = f.readline()
    except OSError:
        return False
    try:
        row = next(csv.reader([first]))
    except StopIteration:
        return False
    return any((c or "").strip().lower() == "site_id" for c in row)


def read_account_site_csv(path: str) -> tuple[list[dict], list[str], str]:
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        site_key = _find_header_col(fieldnames, "site_id")
        if not site_key:
            raise ValueError(f"No site_id column in {path!r}")
        rows = list(reader)
    return rows, fieldnames, site_key


def check_site_ids_unique(rows: list[dict], site_key: str, path: str) -> None:
    """Exit with error if any non-empty site_id appears more than once."""
    counts: dict[str, int] = {}
    for r in rows:
        s = (r.get(site_key) or "").strip()
        if not s:
            continue
        counts[s] = counts.get(s, 0) + 1
    dups = sorted(s for s, n in counts.items() if n > 1)
    if dups:
        print(
            f"Duplicate site_id values in {path!r} (each site_id must appear only once):",
            file=sys.stderr,
        )
        for s in dups:
            print(f"  {s} ({counts[s]} rows)", file=sys.stderr)
        sys.exit(2)


def site_ids_in_row_order(rows: list[dict], site_key: str) -> list[str]:
    """Non-empty site_ids in CSV row order (caller must ensure uniqueness)."""
    return [(r.get(site_key) or "").strip() for r in rows if (r.get(site_key) or "").strip()]


def ensure_teaser_column(fieldnames: list[str]) -> tuple[list[str], str]:
    tk = _find_header_col(fieldnames, "teaser")
    if tk:
        return fieldnames, tk
    return fieldnames + ["teaser"], "teaser"


def write_account_csv_atomic(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                extrasaction="ignore",
                lineterminator="\n",
            )
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)
    except Exception:
        try:
            if os.path.isfile(tmp):
                os.unlink(tmp)
        except OSError:
            pass
        raise


async def main_async(site_ids: list[str]) -> list[dict]:
    results = []
    for sid in site_ids:
        results.append(await teaser_for_site(sid))
    return results


def _teaser_cell(row: dict) -> str:
    err = row.get("error")
    if err:
        return f"[error] {err}"
    teasers = row.get("teaser") or []
    if not isinstance(teasers, list):
        return str(teasers)
    parts = [t.strip() for t in teasers if isinstance(t, str) and t.strip()]
    return " ".join(parts) if parts else ""


def write_csv(results: list[dict], out) -> None:
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["site-id", "teaser"])
    for row in results:
        w.writerow([row.get("site_id", ""), _teaser_cell(row)])


def write_account_csv_stream(rows: list[dict], fieldnames: list[str], out) -> None:
    w = csv.DictWriter(
        out,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )
    w.writeheader()
    w.writerows(rows)


async def _account_csv_fill_and_save_each(
    rows: list[dict],
    fieldnames_out: list[str],
    site_key: str,
    teaser_key: str,
    site_ids_ordered: list[str],
    dest_path: str | None,
) -> None:
    """
    One Supabase + one OpenAI completion per site_id. After each site, if dest_path
    is set, rewrite the full CSV so progress is saved on disk.
    """
    for sid in site_ids_ordered:
        res = await teaser_for_site(sid)
        text = _teaser_cell(res)
        for row in rows:
            if (row.get(site_key) or "").strip() == sid:
                row[teaser_key] = text
        if dest_path:
            write_account_csv_atomic(dest_path, rows, fieldnames_out)


def run_account_csv_flow(account_path: str, output_path: str | None, in_place: bool) -> None:
    rows, fieldnames, site_key = read_account_site_csv(account_path)
    check_site_ids_unique(rows, site_key, account_path)
    fieldnames_out, teaser_key = ensure_teaser_column(fieldnames)
    site_ids_ordered = site_ids_in_row_order(rows, site_key)
    if not site_ids_ordered:
        print(f"No site_id values in {account_path!r}.", file=sys.stderr)
        sys.exit(2)

    dest_path: str | None
    if output_path:
        dest_path = output_path
    elif in_place:
        dest_path = account_path
    else:
        dest_path = None

    asyncio.run(
        _account_csv_fill_and_save_each(
            rows,
            fieldnames_out,
            site_key,
            teaser_key,
            site_ids_ordered,
            dest_path,
        )
    )

    if not dest_path:
        write_account_csv_stream(rows, fieldnames_out, sys.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate operations teasers for site IDs.")
    parser.add_argument(
        "site_ids",
        nargs="*",
        help="Site UUID(s) (space-separated); ignored when using account CSV mode",
    )
    parser.add_argument(
        "-f",
        "--file",
        metavar="PATH",
        help="Text file (one site_id per line) or account CSV with a site_id column",
    )
    parser.add_argument(
        "--account-csv",
        nargs="?",
        const=DEFAULT_ACCOUNT_SITE_IDS_CSV,
        default=None,
        metavar="PATH",
        help="Use account-style CSV (site_id column, optional teaser). Default: ./account_site_ids.csv",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Write enriched CSV back to the input file (with -f path/to.csv, --account-csv, or default account_site_ids.csv)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Legacy two-column CSV: site-id, teaser (not used in account CSV mode)",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help="Write output to this file",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON (legacy mode only)",
    )
    args = parser.parse_args()

    account_path: str | None = None
    if args.account_csv is not None:
        account_path = args.account_csv
    elif args.file and csv_file_has_site_id_column(args.file):
        account_path = os.path.abspath(args.file)
    elif (
        not args.site_ids
        and not args.file
        and os.path.isfile(DEFAULT_ACCOUNT_SITE_IDS_CSV)
        and csv_file_has_site_id_column(DEFAULT_ACCOUNT_SITE_IDS_CSV)
    ):
        account_path = DEFAULT_ACCOUNT_SITE_IDS_CSV

    if account_path:
        if args.pretty:
            print("--pretty applies to legacy mode only; account CSV output is always CSV.", file=sys.stderr)
        out_path = args.output
        if out_path and args.in_place:
            print("Using -o; --in-place ignored.", file=sys.stderr)
        run_account_csv_flow(account_path, out_path, args.in_place and not out_path)
        return

    ids: list[str] = list(args.site_ids)
    if args.file:
        ids.extend(read_site_ids_from_file(args.file))
    elif not args.site_ids:
        if not os.path.isfile(DEFAULT_SITES_FILE):
            print(
                f"No site IDs on the command line, no account_site_ids.csv with site_id, "
                f"and no {DEFAULT_SITES_FILE!r} found.",
                file=sys.stderr,
            )
            sys.exit(2)
        ids.extend(read_site_ids_from_file(DEFAULT_SITES_FILE))

    seen = set()
    unique: list[str] = []
    for i in ids:
        i = i.strip()
        if not i or i in seen:
            continue
        seen.add(i)
        unique.append(i)

    if not unique:
        print(
            "No site IDs found. Add UUIDs to sites.md, use -f, or pass IDs on the command line.",
            file=sys.stderr,
        )
        sys.exit(2)

    results = asyncio.run(main_async(unique))

    if args.output:
        newline = "" if args.csv else None
        with open(args.output, "w", encoding="utf-8", newline=newline) as f:
            if args.csv:
                write_csv(results, f)
            elif args.pretty:
                f.write(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
            else:
                for row in results:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
    elif args.csv:
        write_csv(results, sys.stdout)
    elif args.pretty:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for row in results:
            print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
