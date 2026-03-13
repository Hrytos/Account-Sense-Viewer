"""
Account Sense Viewer - FastAPI Application

Routes:
    GET  /          → login page (or redirect to /dashboard if already logged in)
    POST /login     → verify credentials, set session cookie
    GET  /logout    → clear session, redirect to /
    GET  /dashboard → main app page (requires auth)
    POST /lookup    → fetch site data + AI summaries, return rendered dashboard

Usage (local):
    uvicorn api.main:app --reload --app-dir .
"""

import os
import re
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.services.data_fetcher import get_site_data
from src.services.ai_summarizer import (
    generate_account_summary,
    generate_company_overview,
    generate_assertion_summary,
)

load_dotenv()

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Account Sense Viewer")

# Session middleware — secret key just needs to be random & stable per deploy
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "account-sense-secret-key-change-me"),
)

# Static files & templates — paths relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ── Auth helpers ───────────────────────────────────────────────────────────────

def get_credentials():
    return (
        os.getenv("username", "admin"),
        os.getenv("password", "password"),
    )


def require_auth(request: Request):
    """Dependency: redirect to login if not authenticated."""
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=303, headers={"Location": "/"})
    return request.session.get("username")


# ── Utility ────────────────────────────────────────────────────────────────────

def parse_iso_timestamp(timestamp_str: Optional[str]) -> Optional[datetime]:
    if not timestamp_str:
        return None
    s = str(timestamp_str).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    match = re.match(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?([+-]\d{2}:\d{2})?$", s
    )
    if match:
        base, fraction, tz = match.groups()
        tz = tz or "+00:00"
        if fraction:
            fraction_digits = (fraction[1:] + "000000")[:6]
            s = f"{base}.{fraction_digits}{tz}"
        else:
            s = f"{base}{tz}"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def build_view_model(data: dict) -> dict:
    """
    Transform raw fetched data into a flat view-model dict
    ready to be passed directly into the Jinja template.
    """
    # ── Run details ──
    assertions = data["assertions"]
    latest_created = latest_updated = None
    if assertions:
        created_dates = [a["created_at"] for a in assertions if a["created_at"]]
        updated_dates = [a["updated_at"] for a in assertions if a["updated_at"]]
        if created_dates:
            dt = parse_iso_timestamp(max(created_dates))
            latest_created = dt.strftime("%Y-%m-%d %H:%M:%S UTC") if dt else None
        if updated_dates:
            dt = parse_iso_timestamp(max(updated_dates))
            latest_updated = dt.strftime("%Y-%m-%d %H:%M:%S UTC") if dt else None

    # ── Location ── (defensive: handle string, list, or dict)
    location_raw = data["location"]
    if isinstance(location_raw, str):
        location = {"full_address": location_raw, "metadata": None}
    elif isinstance(location_raw, list):
        location = location_raw[0] if location_raw else {}
    elif isinstance(location_raw, dict):
        location = location_raw
    else:
        location = {}
    
    # Now location is guaranteed to be a dict
    metadata = location.get("metadata") or {}
    facility_type = metadata.get("facility_type", "—") if isinstance(metadata, dict) else "—"
    site_size_str = f"{data['site_size']:,.0f} sq ft" if data["site_size"] else "—"

    # ── Assertions ──
    sorted_assertions = sorted(assertions, key=lambda x: x["net_score"] or 0, reverse=True)
    assertion_rows = []
    for i, a in enumerate(sorted_assertions):
        assertion_rows.append({
            "num":            i + 1,
            "assertion_text": a["assertion_text"],
            "assertion_type": a["assertion_type"],
            "support":        f"{a['supporting_score']:.2f}" if a["supporting_score"] is not None else "N/A",
            "oppose":         f"{a['opposing_score']:.2f}"  if a["opposing_score"]  is not None else "N/A",
            "net":            f"{a['net_score']:.2f}"        if a["net_score"]       is not None else "N/A",
            "classification": a["classification"] or "UNKNOWN",
        })

    # ── Event tables ── (defensive: handle null event_type / event_type_value)
    finance_rows = [
        {"Type": e.get("event_type") or "—", "Value": e.get("event_type_value") or "Not Found"}
        for e in data["events"]["finance"]
    ]
    business_rows = [
        {"Activity Type": e.get("event_type") or "—", "Details": e.get("event_type_value") or "No Information Found"}
        for e in data["events"]["business"]
    ]
    operational_events = data["events"]["operational"]
    operational_rows = [
        {"Operation Type": e.get("event_type") or "—", "Details": str(e.get("event_type_value")) if e.get("event_type_value") else "Not available"}
        for e in operational_events
    ]
    customer_rows = [
        {"Type": e.get("event_type") or "—", "Details": e.get("event_type_value") or "No Information Found"}
        for e in data["events"]["customer"]
    ]
    inventory_rows = [
        {"Type": e.get("event_type") or "—", "Details": e.get("event_type_value") or "—"}
        for e in operational_events
        if e.get("event_type") and "inventory" in e["event_type"].lower()
    ]

    return {
        # meta
        "site_id":        data["site_id"],
        "account_id":     data["account_id"],
        "company_name":   data["company_name"],
        # run details
        "total_assertions": len(assertions),
        "latest_created":   latest_created or "—",
        "latest_updated":   latest_updated or "—",
        # location / size
        "full_address":  location.get("full_address") or "—",
        "facility_type": facility_type,
        "site_size_str": site_size_str,
        # event tables
        "finance_rows":      finance_rows,
        "business_rows":     business_rows,
        "operational_rows":  operational_rows,
        "customer_rows":     customer_rows,
        "inventory_rows":    inventory_rows,
        # assertions
        "assertion_rows": assertion_rows,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    valid_username, valid_password = get_credentials()
    if username == valid_username and password == valid_password:
        request.session["authenticated"] = True
        request.session["username"] = username
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid username or password"},
        status_code=401,
    )


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "view": None, "error": None, "site_id": ""},
    )


@app.post("/lookup", response_class=HTMLResponse)
async def lookup(
    request: Request,
    site_id: str = Form(...),
):
    if not request.session.get("authenticated"):
        return RedirectResponse("/", status_code=302)

    site_id = site_id.strip()
    if not site_id:
        return templates.TemplateResponse(
            "dashboard.html",
            {"request": request, "view": None, "error": "Please enter a Site ID.", "site_id": ""},
        )

    try:
        data = await get_site_data(site_id)
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_msg:
            error_msg = "403 Forbidden — check Supabase RLS policies and your service_role key."
        return templates.TemplateResponse(
            "dashboard.html",
            {"request": request, "view": None, "error": error_msg, "site_id": site_id},
        )

    view = build_view_model(data)

    # ── AI summaries (generated here, passed into template) ──
    try:
        view["ai_summary"] = generate_account_summary(data)
    except Exception as e:
        view["ai_summary"] = f"Could not generate summary: {e}"

    try:
        view["company_overview"] = generate_company_overview(
            data["company_name"], data["location"]["full_address"]
        )
    except Exception as e:
        view["company_overview"] = f"Could not generate company overview: {e}"

    try:
        view["assertion_summary"] = generate_assertion_summary(data["assertions"])
    except Exception as e:
        view["assertion_summary"] = f"Could not generate assertion summary: {e}"

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "view": view, "error": None, "site_id": site_id},
    )
