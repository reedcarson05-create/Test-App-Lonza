"""FastAPI application for operator login, batch setup, data entry, and correction flows."""

# Standard-library imports used for path resolution, timestamp helpers, and JSON sheet payloads.
import base64
import binascii
from pathlib import Path
from datetime import datetime
import json
import os
import socket
from uuid import uuid4

# FastAPI framework imports used for route declarations, form parsing, and HTML responses.
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# Database helpers used by routes to create, read, update, and audit plant records.
from db import (
    init_db,  # Builds tables and applies lightweight schema migrations at startup.
    validate_user,  # Authenticates an employee number and password pair.
    get_user_initials,  # Loads the initials displayed and reused in forms.
    get_user_preferences,  # Loads persisted per-user UI preferences.
    update_user_preferences,  # Saves persisted per-user UI preferences.
    create_run,  # Creates a new batch/run record.
    get_run,  # Fetches a single batch/run record by id.
    list_runs,  # Lists recent runs for the batch selection screen.
    mark_run_complete,  # Finalizes a run after review.
    update_run,  # Saves edits to the active run header data.
    get_extraction_entry,  # Loads a saved extraction entry for corrections.
    update_extraction,  # Persists extraction corrections.
    get_filtration_entry,  # Loads a saved filtration entry and its child rows.
    update_filtration,  # Persists filtration corrections.
    get_evaporation_entry,  # Loads a saved evaporation entry and its child rows.
    get_latest_evaporation_for_run,  # Finds the current run's latest evaporation sheet.
    update_evaporation,  # Persists evaporation corrections.
    get_sheet_entry,  # Loads a saved generic stage sheet.
    get_latest_sheet_entry_for_run_stage,  # Finds the latest generic sheet for a run/stage pair.
    update_sheet_entry,  # Persists generic stage corrections.
    insert_extraction,  # Creates a new extraction entry.
    insert_filtration,  # Creates a new filtration entry and child rows.
    insert_evaporation,  # Creates a new evaporation entry and child rows.
    insert_sheet_entry,  # Creates a new generic stage entry.
    insert_field_change_log,  # Records field-level correction details.
    insert_audit,  # Records higher-level create/update/finalize events.
    get_field_change_history,  # Reads correction history for dashboards.
    last_12_hour_activity,  # Builds the recent-activity dashboard feed.
)

# Stage metadata controls the generic forms and dashboard navigation links.
from stage_defs import GENERIC_STAGE_DEFS, STAGE_LINKS, PROCESS_STAGE_LINKS

# Main ASGI application object served by Uvicorn or another ASGI server.
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="lonza-secret-key-change-me")

# Base directory used to resolve the bundled static assets and Jinja templates.
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SIGNATURE_DIR = UPLOAD_DIR / "signatures"
SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def asset_version() -> str:
    """Return a cache-busting version based on the latest UI asset timestamp."""
    candidate_paths = (
        BASE_DIR / "static" / "style.css",
        BASE_DIR / "static" / "settings.js",
        BASE_DIR / "static" / "signature_session.js",
        BASE_DIR / "static" / "form_corrections.js",
    )
    latest_stamp = 0
    for path in candidate_paths:
        try:
            latest_stamp = max(latest_stamp, path.stat().st_mtime_ns)
        except OSError:
            continue
    return str(latest_stamp or int(datetime.now().timestamp()))


def configured_host() -> str:
    """Return the bind host used by the local launcher scripts and `python app.py`."""
    return os.getenv("PLANT_APP_HOST", "0.0.0.0").strip() or "0.0.0.0"


def configured_port() -> int:
    """Return the configured local port, falling back safely when the env var is invalid."""
    raw_value = os.getenv("PLANT_APP_PORT", "8000")
    try:
        port = int(raw_value)
    except (TypeError, ValueError):
        return 8000
    return port if 1 <= port <= 65535 else 8000

# Ensure the local SQLite schema exists before any request handlers run.
init_db()


# ------------------------
# HELPERS
# ------------------------

def logged_in(request: Request) -> bool:
    """Return True when the session already contains an authenticated user."""
    return bool(request.session.get("user"))


def current_user(request: Request) -> str:
    """Return the employee number stored in the current session."""
    return request.session.get("user", "")


def current_initials(request: Request) -> str:
    """Return the operator initials stored in the current session."""
    return request.session.get("initials", "")


def current_signature_initials(request: Request) -> str:
    """Return the initials most recently signed in this login session, if any."""
    return request.session.get("signature_initials", "")


def current_signature_signed_at(request: Request) -> str:
    """Return the timestamp for the active initials signature in this session."""
    return request.session.get("signature_signed_at", "")


def current_signature_data(request: Request) -> str:
    """Return the captured initials-stroke image for the current session, if any."""
    return request.session.get("signature_data", "")


def signature_session_ready(request: Request) -> bool:
    """Return True when the login session already has initials, signed time, and drawing data."""
    return bool(current_signature_initials(request) and current_signature_signed_at(request) and current_signature_data(request))


def signature_asset_public_path(file_path: Path) -> str:
    """Return the public static URL used to re-open a saved signature image."""
    return f"/static/uploads/signatures/{file_path.name}"


def signature_asset_file_path(signature_reference: str) -> Path | None:
    """Resolve a saved signature URL back to its on-disk PNG path when it belongs to this app."""
    cleaned = clean_value(signature_reference)
    prefix = "/static/uploads/signatures/"
    if not cleaned.startswith(prefix):
        return None
    filename = cleaned.rsplit("/", 1)[-1].strip()
    if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        return None
    return SIGNATURE_DIR / filename


def delete_signature_asset(signature_reference: str) -> None:
    """Delete a previously saved signature PNG when it belongs to the local uploads folder."""
    file_path = signature_asset_file_path(signature_reference)
    if not file_path:
        return
    try:
        if file_path.exists():
            file_path.unlink()
    except OSError:
        pass


def persist_signature_image(signature_data: str) -> str:
    """Store a drawn signature PNG under `static/uploads/signatures` and return its public URL."""
    cleaned = clean_value(signature_data)
    if not cleaned:
        return ""

    existing_file = signature_asset_file_path(cleaned)
    if existing_file:
        return cleaned

    prefix = "data:image/png;base64,"
    if not cleaned.startswith(prefix):
        return ""

    try:
        raw_bytes = base64.b64decode(cleaned[len(prefix):], validate=True)
    except (ValueError, binascii.Error):
        return ""

    if not raw_bytes:
        return ""

    file_path = SIGNATURE_DIR / f"signature-{uuid4().hex}.png"
    file_path.write_bytes(raw_bytes)
    return signature_asset_public_path(file_path)


def update_signature_session(request: Request, initials: str, signature_data: str, signed_at: str) -> bool:
    """Persist the active signature metadata for the login session and move image bytes to disk."""
    signed_initials = clean_value(initials).upper()
    saved_signature = persist_signature_image(signature_data)
    saved_at = clean_value(signed_at)
    if not signed_initials or not saved_signature or not saved_at:
        return False

    previous_signature = clean_value(request.session.get("signature_data", ""))
    if previous_signature and previous_signature != saved_signature:
        delete_signature_asset(previous_signature)

    request.session["signature_initials"] = signed_initials
    request.session["signature_data"] = saved_signature
    request.session["signature_signed_at"] = saved_at
    return True


def clear_signature_session(request: Request) -> None:
    """Remove any saved signature PNG for the session and clear its signature-specific keys."""
    delete_signature_asset(clean_value(request.session.get("signature_data", "")))
    request.session.pop("signature_initials", None)
    request.session.pop("signature_data", None)
    request.session.pop("signature_signed_at", None)


def current_theme(request: Request) -> str:
    """Return the saved theme stored in the current session."""
    return request.session.get("theme", "light")


def current_font_scale(request: Request) -> str:
    """Return the saved font scale stored in the current session."""
    return request.session.get("font_scale", "1")


def current_run_id(request: Request):
    """Return the active production run id from the current session, if one exists."""
    return request.session.get("run_id")


def today_str() -> str:
    """Return today's date in the same format used by the HTML forms."""
    return datetime.now().strftime("%Y-%m-%d")


def local_ipv4_addresses() -> list[str]:
    """Collect non-loopback IPv4 addresses that other devices on the LAN can reach."""
    addresses: list[str] = []

    def remember(address: str) -> None:
        if not address or address.startswith("127.") or ":" in address or address in addresses:
            return
        addresses.append(address)

    try:
        for _, _, _, _, sockaddr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            remember(sockaddr[0])
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            remember(sock.getsockname()[0])
    except OSError:
        pass

    return addresses


def local_access_urls(request: Request) -> list[str]:
    """Build the same-Wi-Fi URLs shown in the UI for phones, tablets, and other PCs."""
    scheme = request.url.scheme if request.url.scheme in {"http", "https"} else "http"
    port = request.url.port or configured_port()
    return [f"{scheme}://{address}:{port}" for address in local_ipv4_addresses()]


def blank_stamp(entry_date: str = "", initials: str = "") -> str:
    """Build the stamp text shown when a saved cell was intentionally left blank."""
    parts = [clean_value(entry_date) or today_str(), clean_value(initials).upper()]
    return " | ".join(part for part in parts if part)


def is_blank_value(value) -> bool:
    """Return True when a saved value should render as an intentional blank."""
    return clean_value(value) == ""


def blank_display(value, entry_date: str = "", initials: str = "") -> str:
    """Return either the saved value or a slash-stamped blank marker for display."""
    return clean_value(value) if not is_blank_value(value) else blank_stamp(entry_date, initials)


def save_signature_session(request: Request, form) -> None:
    """Persist a freshly captured handwritten signature into the server session."""
    signed_initials = clean_value(form.get("__session_signature_initials", "")).upper()
    signature_data = clean_value(form.get("__session_signature_data", ""))
    signed_at = clean_value(form.get("__session_signature_signed_at", ""))
    update_signature_session(request, signed_initials, signature_data, signed_at)


def require_handwritten_signature(request: Request, form):
    """Return a validation error until the current login session has a saved handwritten signature."""
    save_signature_session(request, form)
    if signature_session_ready(request):
        return None
    return PlainTextResponse(
        "Please sign once by hand with your initials, date, and time before saving this sheet. "
        "That signature will be reused until you log out.",
        status_code=400,
    )


def active_run(request: Request):
    """Return the active run record for the session, or None when no run is selected."""
    run_id = current_run_id(request)
    return get_run(run_id) if run_id else None


def require_login(request: Request):
    """Redirect anonymous users back to the login page."""
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)
    return None


def require_run(request: Request):
    """Redirect users to run selection until an active batch/run is chosen."""
    if not current_run_id(request):
        return RedirectResponse("/run/select", status_code=303)
    return None


def get_generic_stage(stage_key: str):
    """Look up a generic stage configuration by its route key."""
    return GENERIC_STAGE_DEFS.get(stage_key)


def render_page(request: Request, template_name: str, **context):
    """Render a template with the standard navigation/session context already included."""
    # Shared template values used by most pages for nav badges and defaults.
    page_context = {
        "request": request,
        "user": current_user(request),
        "initials": current_initials(request),
        "default_initials": current_initials(request),
        "session_signature_initials": current_signature_initials(request),
        "session_signature_signed_at": current_signature_signed_at(request),
        "session_signature_data": current_signature_data(request),
        "signature_session_ready": signature_session_ready(request),
        "settings_theme": current_theme(request),
        "settings_font_scale": current_font_scale(request),
        "settings_persist": logged_in(request),
        "asset_version": asset_version(),
        "today": today_str(),
        "run": active_run(request),
        "local_access_urls": local_access_urls(request),
        "local_port": request.url.port or configured_port(),
        "blank_display": blank_display,
        "blank_stamp": blank_stamp,
        "is_blank_value": is_blank_value,
    }
    page_context.update(context)
    return templates.TemplateResponse(template_name, page_context)


def clean_value(value) -> str:
    """Normalize optional form values into trimmed strings for comparisons and logging."""
    if value is None:
        return ""
    return str(value).strip()


def image_upload_response(status_code: int, message: str):
    """Return a small JSON error payload for image upload failures."""
    return JSONResponse({"error": message}, status_code=status_code)


def collect_field_changes(form, old_values: dict, changed_by: str, correction_reason: str):
    """Build field-level change records for correction pages and validate initials coverage."""
    # `changes` becomes the audit payload saved into `field_change_log`.
    changes = []
    # `missing_details` tracks edited fields that still need operator initials.
    missing_details = []

    for key, value in form.multi_items():
        if key == "correction_reason":
            continue
        if key.startswith("__session_signature_"):
            continue
        if key.startswith("__change__") or key.startswith("__original__") or key.startswith("__corrected__"):
            continue

        new_value = clean_value(value)
        old_value = clean_value(old_values.get(key, ""))
        if new_value == old_value:
            continue

        original_value = clean_value(form.get(f"__original__{key}", "")) or old_value
        corrected_value = clean_value(form.get(f"__corrected__{key}", "")) or new_value
        change_initials = clean_value(form.get(f"__change__{key}", "")).upper()
        if not change_initials:
            missing_details.append(key)
            continue

        # Each dictionary describes one corrected field exactly as it will be stored in SQLite.
        changes.append(
            {
                "field_name": key,
                "field_value": new_value,
                "original_value": original_value,
                "corrected_value": corrected_value,
                "correction_reason": correction_reason,
                "change_initials": change_initials,
                "changed_by_employee": changed_by,
            }
        )

    return changes, missing_details, []


def correction_error_response(prefix: str, fields: list[str]):
    """Return a compact plain-text validation error listing the affected fields."""
    field_list = ", ".join(fields[:8])
    if len(fields) > 8:
        field_list += ", ..."
    return PlainTextResponse(
        f"{prefix}: {field_list}",
        status_code=400,
    )


def correction_missing_response(fields: list[str]):
    """Specialized validation error for edited fields that are missing initials."""
    return correction_error_response("Please add initials for each edited field", fields)


def display_sheet_name(entry_table: str, section: str = "", stage_title: str = "") -> str:
    """Choose the most user-friendly label for dashboards and change-history rows."""
    if stage_title:
        return stage_title
    if section:
        return section
    # Fallback labels for tables that do not already carry a friendlier stage title.
    labels = {
        "extraction_entries": "Extraction",
        "filtration_entries": "Filtration",
        "evaporation_entries": "Evaporation",
        "sheet_entries": "Batch Sheet",
        "production_runs": "Batch",
    }
    return labels.get(entry_table, entry_table.replace("_", " ").title())


def process_dashboard_rows(rows=None):
    """Filter recent activity down to the standalone extraction and filtration sections."""
    source_rows = rows if rows is not None else last_12_hour_activity()
    return [row for row in source_rows if row["section"] in {"Extraction", "Filtration"}]


def build_filtration_row_map(rows):
    """Convert filtration child rows into template-friendly keys such as main_1 or dia_2."""
    row_map = {}
    for row in rows:
        prefix = "dia" if row["row_group"] == "dia" else "main"
        row_map[f"{prefix}_{row['row_no']}"] = row
    return row_map


def build_evaporation_row_map(rows):
    """Convert evaporation child rows into template-friendly keys such as row1 and row2."""
    return {f"row{row['row_no']}": row for row in rows}


def build_extraction_payload(form, operator_initials: str):
    """Map the extraction form fields into the database payload expected by `insert_extraction`."""
    # Keys in this object are intentionally aligned with the columns in `extraction_entries`.
    return {
        "run_id": None,
        "operator_initials": operator_initials,
        "entry_date": form.get("entry_date", ""),
        "entry_time": form.get("entry_time", ""),
        "location": form.get("location", "") or "Pile",
        "time_on_pile": form.get("time_on_pile", "") or form.get("time_on_pipe_or_pile", ""),
        "start_time": form.get("start_time", ""),
        "stop_time": form.get("stop_time", ""),
        "psf1_speed": form.get("psf1_speed", ""),
        "psf1_load": form.get("psf1_load", ""),
        "psf1_blowback": form.get("psf1_blowback", ""),
        "psf2_speed": form.get("psf2_speed", ""),
        "psf2_load": form.get("psf2_load", ""),
        "psf2_blowback": form.get("psf2_blowback", ""),
        "press_speed": form.get("press_speed", ""),
        "press_load": form.get("press_load", ""),
        "press_blowback": form.get("press_blowback", ""),
        "pressate_ri": form.get("pressate_ri", ""),
        "chip_bin_steam": form.get("chip_bin_steam", ""),
        "chip_chute_temp": form.get("chip_chute_temp", ""),
        "comments": form.get("comments", "") or form.get("notes", ""),
        "photo_path": form.get("photo_path", ""),
    }


def build_filtration_rows(form):
    """Build normalized filtration row payloads for both the main and diafiltration tables."""
    # Main filtration readings keep flow columns because those rows represent the primary process path.
    main_rows = []
    for i in range(1, 4):
        main_rows.append(
            {
                "row_group": "main",
                "row_no": i,
                "row_time": form.get(f"row{i}_time", ""),
                "feed_ri": form.get(f"row{i}_feed_ri", ""),
                "retentate_ri": form.get(f"row{i}_retentate_ri", ""),
                "permeate_ri": form.get(f"row{i}_permeate_ri", ""),
                "perm_flow_c": form.get(f"row{i}_perm_flow_c", ""),
                "perm_flow_d": form.get(f"row{i}_perm_flow_d", ""),
            }
        )

    # Diafiltration rows use a smaller schema and intentionally leave flow columns blank.
    dia_rows = []
    for i in range(1, 3):
        dia_rows.append(
            {
                "row_group": "dia",
                "row_no": i,
                "row_time": form.get(f"dia_row{i}_time", ""),
                "feed_ri": form.get(f"dia_row{i}_feed_ri", ""),
                "retentate_ri": form.get(f"dia_row{i}_retentate_ri", ""),
                "permeate_ri": form.get(f"dia_row{i}_permeate_ri", ""),
                "perm_flow_c": "",
                "perm_flow_d": "",
            }
        )
    return main_rows + dia_rows


def build_filtration_payload(form, operator_initials: str):
    """Map the filtration form fields into the database payload expected by `insert_filtration`."""
    # The parent record fields live beside the child `rows` collection in one payload object.
    return {
        "run_id": None,
        "operator_initials": operator_initials,
        "entry_date": form.get("entry_date", ""),
        "clarification_sequential_no": form.get("clarification_sequential_no", ""),
        "retentate_flow_set_point": form.get("retentate_flow_set_point", ""),
        "zero_refract": form.get("zero_refract", ""),
        "startup_time": form.get("startup_time", ""),
        "shutdown_time": form.get("shutdown_time", ""),
        "start_time": form.get("start_time", ""),
        "stop_time": form.get("stop_time", ""),
        "comments": form.get("comments", "") or form.get("notes", ""),
        "photo_path": form.get("photo_path", ""),
        "rows": build_filtration_rows(form),
    }


def build_evaporation_rows(form):
    """Build normalized evaporation row payloads for the repeating timed-reading table."""
    rows = []
    for i in range(1, 4):
        # Each row maps directly to one record in the `evaporation_rows` child table.
        rows.append(
            {
                "row_no": i,
                "row_time": form.get(f"row{i}_time", ""),
                "feed_rate": form.get(f"row{i}_feed_rate", ""),
                "evap_temp": form.get(f"row{i}_evap_temp", ""),
                "row_vacuum": form.get(f"row{i}_vacuum", ""),
                "row_concentrate_ri": form.get(f"row{i}_concentrate_ri", ""),
            }
        )
    return rows


def build_evaporation_payload(form, run_id: int | None, operator_initials: str):
    """Map the evaporation form fields into the database payload expected by `insert_evaporation`."""
    # Unlike extraction/filtration, evaporation is always tied to a selected batch run.
    return {
        "run_id": run_id,
        "operator_initials": operator_initials,
        "entry_date": form.get("entry_date", ""),
        "evaporator_no": form.get("evaporator_no", ""),
        "startup_time": form.get("startup_time", ""),
        "shutdown_time": form.get("shutdown_time", ""),
        "feed_ri": form.get("feed_ri", ""),
        "concentrate_ri": form.get("concentrate_ri", ""),
        "steam_pressure": form.get("steam_pressure", ""),
        "vacuum": form.get("vacuum", ""),
        "sump_level": form.get("sump_level", ""),
        "product_temp": form.get("product_temp", ""),
        "comments": form.get("comments", "") or form.get("notes", ""),
        "photo_path": form.get("photo_path", ""),
        "rows": build_evaporation_rows(form),
    }


def process_dashboard_items(rows=None):
    """Prepare recent extraction/filtration rows with the edit links used by the dashboard."""
    items = []
    source_rows = rows if rows is not None else process_dashboard_rows()
    for row in source_rows:
        # Edit links depend on section because each stage has a dedicated correction route.
        href = ""
        if row["section"] == "Extraction":
            href = f"/edit/extraction/{row['record_id']}"
        elif row["section"] == "Filtration":
            href = f"/edit/filtration/{row['record_id']}"
        items.append({**dict(row), "edit_href": href, "display_section": display_sheet_name(row["entry_table"], row["section"])})
    return items


def dashboard_batch_packs(rows=None):
    """Group recent batch-pack activity by batch number for the review dashboard."""
    # `packs` is keyed by batch number so multiple saved sheets collapse into one dashboard card.
    packs = {}
    source_rows = rows if rows is not None else last_12_hour_activity()
    for row in source_rows:
        batch_number = row["batch_number"] or "No batch"
        pack = packs.setdefault(
            batch_number,
            {
                "batch_number": batch_number,
                "entries": [],
                "latest_time": row["activity_time"],
                "run_numbers": set(),
                "blend_numbers": set(),
            },
        )
        edit_href = ""
        if row["section"] == "Evaporation":
            edit_href = f"/edit/evaporation/{row['record_id']}"
        elif row["entry_table"] == "sheet_entries":
            edit_href = f"/edit/generic/{row['record_id']}"
        # Each entry remains available individually so the dashboard can still open the right correction page.
        pack["entries"].append(
            {
                **dict(row),
                "edit_href": edit_href,
                "display_section": display_sheet_name(row["entry_table"], row["section"]),
            }
        )
        if row["activity_time"] > pack["latest_time"]:
            pack["latest_time"] = row["activity_time"]
        if row["run_number"]:
            pack["run_numbers"].add(row["run_number"])
        if row["blend_number"]:
            pack["blend_numbers"].add(row["blend_number"])

    results = sorted(packs.values(), key=lambda pack: pack["latest_time"], reverse=True)
    for pack in results:
        pack["run_numbers"] = ", ".join(sorted(pack["run_numbers"]))
        pack["blend_numbers"] = ", ".join(sorted(pack["blend_numbers"]))
        pack["entry_count"] = len(pack["entries"])
    return results


def build_batch_review(run_id: int):
    """Gather the latest saved batch-pack sheets so the final review page can summarize them."""
    run = get_run(run_id)
    evaporation_entry, evaporation_rows = get_latest_evaporation_for_run(run_id)

    # Generic stage entries are discovered from configuration instead of hard-coded one by one.
    generic_entries = []
    for stage_key, stage in GENERIC_STAGE_DEFS.items():
        entry = get_latest_sheet_entry_for_run_stage(run_id, stage_key)
        if not entry:
            continue
        payload = json.loads(entry["payload_json"] or "{}")
        generic_entries.append(
            {
                "stage_key": stage_key,
                "title": stage["title"],
                "sheet_name": stage["sheet_name"],
                "entry": entry,
                "payload": payload,
                "stage": stage,
            }
        )

    # This return object is passed straight into `batch_review.html`.
    return {
        "run": run,
        "evaporation_entry": evaporation_entry,
        "evaporation_rows": evaporation_rows,
        "generic_entries": generic_entries,
        "has_entries": bool(evaporation_entry or generic_entries),
    }


# ------------------------
# BASIC
# ------------------------

@app.get("/health", response_class=PlainTextResponse)
def health():
    """Simple health-check endpoint for smoke tests and deployment checks."""
    return "OK"


# ------------------------
# LOGIN
# ------------------------

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    """Render the login form or jump straight home when a session already exists."""
    if logged_in(request):
        return RedirectResponse("/home", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": "",
            "settings_theme": "light",
            "settings_font_scale": "1",
            "settings_persist": False,
            "asset_version": asset_version(),
            "local_access_urls": local_access_urls(request),
            "local_port": request.url.port or configured_port(),
        },
    )


@app.post("/login")
def login(
    request: Request,
    employee: str = Form(...),
    password: str = Form(...),
):
    """Authenticate an operator and seed the session with their identity data."""
    employee = employee.strip()

    if validate_user(employee, password):
        preferences = get_user_preferences(employee)
        # Session values power nav badges, default initials, and route guards.
        clear_signature_session(request)
        request.session.clear()
        request.session["user"] = employee
        request.session["initials"] = get_user_initials(employee)
        request.session["theme"] = preferences["theme"]
        request.session["font_scale"] = preferences["font_scale"]
        return RedirectResponse("/home", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": "Invalid employee number or password.",
            "settings_theme": "light",
            "settings_font_scale": "1",
            "settings_persist": False,
            "asset_version": asset_version(),
            "local_access_urls": local_access_urls(request),
            "local_port": request.url.port or configured_port(),
        },
        status_code=400,
    )


@app.get("/logout")
def logout(request: Request):
    """Clear the session and return the operator to the login page."""
    clear_signature_session(request)
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.post("/signature-session")
async def save_signature_session_api(request: Request):
    """Save the handwritten signature for the current login session and return its reusable URL."""
    redirect = require_login(request)
    if redirect:
        return JSONResponse({"error": "Please log in again before saving a signature."}, status_code=401)

    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "The signature payload was not valid JSON."}, status_code=400)

    initials = clean_value(payload.get("initials", "")).upper()
    signature_data = clean_value(payload.get("signature_data", ""))
    signed_at = clean_value(payload.get("signed_at", ""))
    if not initials or not signature_data or not signed_at:
        return JSONResponse({"error": "Initials, signed time, and a handwritten signature are all required."}, status_code=400)

    if not update_signature_session(request, initials, signature_data, signed_at):
        return JSONResponse({"error": "The app could not save that signature image. Please try again."}, status_code=400)

    return JSONResponse(
        {
            "ok": True,
            "initials": current_signature_initials(request),
            "signed_at": current_signature_signed_at(request),
            "signature_data": current_signature_data(request),
        }
    )


@app.post("/settings")
def save_settings(
    request: Request,
    theme: str = Form(...),
    font_scale: str = Form(...),
):
    """Persist the current user's display preferences and refresh the session copy."""
    redirect = require_login(request)
    if redirect:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    preferences = update_user_preferences(current_user(request), theme, font_scale)
    request.session["theme"] = preferences["theme"]
    request.session["font_scale"] = preferences["font_scale"]
    return JSONResponse(preferences)


@app.get("/settings")
def get_settings(request: Request):
    """Return the logged-in user's latest saved display preferences."""
    redirect = require_login(request)
    if redirect:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    preferences = get_user_preferences(current_user(request))
    request.session["theme"] = preferences["theme"]
    request.session["font_scale"] = preferences["font_scale"]
    return JSONResponse(preferences)


@app.post("/upload-image")
async def upload_image(request: Request, files: list[UploadFile] = File(...)):
    """Save uploaded device images into the app's static folder and return their URLs."""
    redirect = require_login(request)
    if redirect:
        return image_upload_response(401, "Not authenticated")

    saved_files = []
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
    user_folder = UPLOAD_DIR / current_user(request)
    user_folder.mkdir(parents=True, exist_ok=True)

    for upload in files:
        if not upload.filename:
            continue

        suffix = Path(upload.filename).suffix.lower() or ".jpg"
        if suffix not in allowed_suffixes and upload.content_type not in allowed_types:
            return image_upload_response(400, f"Unsupported image type for {upload.filename}")

        safe_suffix = suffix if suffix in allowed_suffixes else ".jpg"
        file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex}{safe_suffix}"
        destination = user_folder / file_name
        file_bytes = await upload.read()
        if not file_bytes:
            continue
        destination.write_bytes(file_bytes)
        saved_files.append(
            {
                "name": upload.filename,
                "url": f"/static/uploads/{current_user(request)}/{file_name}",
            }
        )

    if not saved_files:
        return image_upload_response(400, "No image files were uploaded")

    return JSONResponse({"files": saved_files})


# ------------------------
# HOME
# ------------------------

@app.get("/home", response_class=HTMLResponse)
def home(request: Request):
    """Render the landing page for starting work, resuming a batch, or reviewing data."""
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "home.html")


# ------------------------
# RUN SELECTION
# ------------------------

@app.get("/run/select", response_class=HTMLResponse)
def run_select_page(request: Request):
    """Render the run selection and creation page with recent saved runs."""
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "run_select.html", runs=list_runs())


@app.post("/run/select")
async def run_select(
    request: Request,
    batch_number: str = Form(""),
    split_batch_number: str = Form(""),
    blend_number: str = Form(""),
    run_number: str = Form(""),
    batch_type: str = Form("standard"),
    reused_batch: str = Form("0"),
    product_name: str = Form(""),
    shift_name: str = Form(""),
    notes: str = Form(""),
):
    """Create a new production run from the batch setup form and store it in session."""
    redirect = require_login(request)
    if redirect:
        return redirect

    form = await request.form()
    save_signature_session(request, form)

    try:
        # The run header is saved first so every later batch-pack sheet can point back to this id.
        run_id = create_run(
            batch_number=batch_number,
            split_batch_number=split_batch_number,
            blend_number=blend_number,
            run_number=run_number,
            batch_type=batch_type,
            reused_batch=1 if reused_batch == "1" else 0,
            product_name=product_name,
            shift_name=shift_name,
            operator_id=current_user(request),
            notes=notes,
        )
    except Exception as exc:
        return PlainTextResponse(f"Run save failed: {type(exc).__name__}: {exc}", status_code=500)

    request.session["run_id"] = run_id
    return RedirectResponse("/stages", status_code=303)


@app.get("/run/use/{run_id}")
def use_run(request: Request, run_id: int):
    """Switch the current session to an existing run selected from the recent list."""
    redirect = require_login(request)
    if redirect:
        return redirect

    request.session["run_id"] = run_id
    return RedirectResponse("/stages", status_code=303)


@app.get("/batch/edit", response_class=HTMLResponse)
def batch_edit_page(request: Request):
    """Render the batch header edit form for the currently selected run."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    return render_page(request, "batch_edit.html")


@app.post("/batch/edit")
async def batch_edit_submit(
    request: Request,
    batch_number: str = Form(""),
    split_batch_number: str = Form(""),
    blend_number: str = Form(""),
    run_number: str = Form(""),
    batch_type: str = Form("standard"),
    reused_batch: str = Form("0"),
    product_name: str = Form(""),
    shift_name: str = Form(""),
    notes: str = Form(""),
    final_edit_initials: str = Form(""),
    final_edit_notes: str = Form(""),
):
    """Persist edits to the run header and record the change in the audit log."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    form = await request.form()
    save_signature_session(request, form)
    final_edit_initials = (final_edit_initials or current_signature_initials(request) or current_initials(request)).strip().upper()

    # These fields mirror the run-setup form, with two extra final-review accountability fields.
    update_run(
        run_id=current_run_id(request),
        batch_number=batch_number,
        split_batch_number=split_batch_number,
        blend_number=blend_number,
        run_number=run_number,
        batch_type=batch_type,
        reused_batch=1 if reused_batch == "1" else 0,
        product_name=product_name,
        shift_name=shift_name,
        notes=notes,
        final_edit_initials=final_edit_initials,
        final_edit_notes=final_edit_notes,
    )

    insert_audit(
        table_name="production_runs",
        record_id=current_run_id(request),
        action_type="update",
        changed_by=current_user(request),
        old_data="",
        new_data="batch edited and initialed",
    )

    return RedirectResponse("/stages", status_code=303)


# ------------------------
# PROCESS DASHBOARD
# ------------------------

@app.get("/process-dashboard", response_class=HTMLResponse)
def process_dashboard(request: Request):
    """Render the standalone extraction and filtration dashboard."""
    redirect = require_login(request)
    if redirect:
        return redirect

    activity_rows = process_dashboard_rows(last_12_hour_activity())
    return render_page(request, "process_dashboard.html", stage_links=PROCESS_STAGE_LINKS, items=process_dashboard_items(activity_rows))


# ------------------------
# STAGE SELECTION
# ------------------------

@app.get("/stages", response_class=HTMLResponse)
def stages(request: Request):
    """Render the batch stage picker for the currently selected run."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    return render_page(request, "stages.html", stage_links=STAGE_LINKS)


@app.get("/batch/review", response_class=HTMLResponse)
def batch_review_page(request: Request):
    """Render the final batch-pack review page for the active run."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    review = build_batch_review(current_run_id(request))
    return render_page(request, "batch_review.html", **review)


@app.post("/batch/review/finalize")
async def finalize_batch_review(request: Request):
    """Mark the active run complete once at least one batch-pack entry exists."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    form = await request.form()
    save_signature_session(request, form)

    review = build_batch_review(current_run_id(request))
    if not review["has_entries"]:
        return PlainTextResponse("Add at least one batch data entry before finalizing the batch pack.", status_code=400)

    mark_run_complete(current_run_id(request), current_user(request))
    insert_audit(
        table_name="production_runs",
        record_id=current_run_id(request),
        action_type="finalize",
        changed_by=current_user(request),
        old_data="",
        new_data="batch pack reviewed and finalized",
    )
    return RedirectResponse("/dashboard", status_code=303)


# ------------------------
# EXTRACTION
# ------------------------

@app.get("/stage/extraction", response_class=HTMLResponse)
def extraction_page(request: Request):
    """Render the standalone extraction entry form."""
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "extraction.html", run=None)


@app.post("/submit/extraction")
async def submit_extraction(request: Request):
    """Save a new extraction entry and audit the create action."""
    redirect = require_login(request)
    if redirect:
        return redirect

    form = await request.form()
    signature_error = require_handwritten_signature(request, form)
    if signature_error:
        return signature_error
    operator_initials = (form.get("operator_initials") or current_signature_initials(request) or current_initials(request)).strip().upper()

    try:
        entry_id = insert_extraction(current_user(request), build_extraction_payload(form, operator_initials))

        insert_audit(
            table_name="extraction_entries",
            record_id=entry_id,
            action_type="create",
            changed_by=current_user(request),
            old_data="",
            new_data="extraction entry created",
        )
    except Exception as exc:
        return PlainTextResponse(f"Extraction save failed: {type(exc).__name__}: {exc}", status_code=500)

    return RedirectResponse("/process-dashboard", status_code=303)


# ------------------------
# FILTRATION
# ------------------------

@app.get("/stage/filtration", response_class=HTMLResponse)
def filtration_page(request: Request):
    """Render the standalone filtration entry form."""
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "filtration.html", run=None)


@app.post("/submit/filtration")
async def submit_filtration(request: Request):
    """Save a new filtration entry and audit the create action."""
    redirect = require_login(request)
    if redirect:
        return redirect

    form = await request.form()
    signature_error = require_handwritten_signature(request, form)
    if signature_error:
        return signature_error

    try:
        operator_initials = (form.get("operator_initials") or current_signature_initials(request) or current_initials(request)).strip().upper()
        entry_id = insert_filtration(current_user(request), build_filtration_payload(form, operator_initials))

        insert_audit(
            table_name="filtration_entries",
            record_id=entry_id,
            action_type="create",
            changed_by=current_user(request),
            old_data="",
            new_data="filtration entry created",
        )
    except Exception as exc:
        return PlainTextResponse(f"Filtration save failed: {type(exc).__name__}: {exc}", status_code=500)

    return RedirectResponse("/process-dashboard", status_code=303)


# ------------------------
# EVAPORATION
# ------------------------

@app.get("/stage/evaporation", response_class=HTMLResponse)
def evaporation_page(request: Request):
    """Render the evaporation sheet or its saved read-only view for the active run."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    entry, rows = get_latest_evaporation_for_run(current_run_id(request))
    row_map = build_evaporation_row_map(rows) if rows else {}
    return render_page(
        request,
        "evaporation.html",
        entry=entry,
        row_map=row_map,
        view_only=entry is not None,
        edit_href=f"/edit/evaporation/{entry['id']}" if entry else "",
    )


@app.post("/submit/evaporation")
async def submit_evaporation(request: Request):
    """Save a new evaporation entry for the active run and audit the create action."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    form = await request.form()
    signature_error = require_handwritten_signature(request, form)
    if signature_error:
        return signature_error
    try:
        operator_initials = (form.get("operator_initials") or current_signature_initials(request) or current_initials(request)).strip().upper()
        entry_id = insert_evaporation(
            current_user(request),
            build_evaporation_payload(form, current_run_id(request), operator_initials),
        )

        insert_audit(
            table_name="evaporation_entries",
            record_id=entry_id,
            action_type="create",
            changed_by=current_user(request),
            old_data="",
            new_data="evaporation entry created",
        )
    except Exception as exc:
        return PlainTextResponse(f"Evaporation save failed: {type(exc).__name__}: {exc}", status_code=500)

    return RedirectResponse("/stages", status_code=303)


# ------------------------
# GENERIC SHEETS
# ------------------------

@app.get("/stage/generic/{stage_key}", response_class=HTMLResponse)
def generic_stage_page(request: Request, stage_key: str):
    """Render a generic batch-pack sheet driven entirely by `stage_defs.py`."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    stage = get_generic_stage(stage_key)
    if not stage:
        return RedirectResponse("/stages", status_code=303)

    entry = get_latest_sheet_entry_for_run_stage(current_run_id(request), stage_key)
    payload = json.loads(entry["payload_json"] or "{}") if entry else {}
    return render_page(
        request,
        "generic_sheet.html",
        stage_key=stage_key,
        stage=stage,
        entry=entry,
        entry_values=payload,
        view_only=entry is not None,
        edit_href=f"/edit/generic/{entry['id']}" if entry else "",
    )


@app.post("/submit/generic/{stage_key}")
async def submit_generic_stage(request: Request, stage_key: str):
    """Save a generic stage entry for the active run and audit the create action."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    stage = get_generic_stage(stage_key)
    if not stage:
        return RedirectResponse("/stages", status_code=303)

    form = await request.form()
    signature_error = require_handwritten_signature(request, form)
    if signature_error:
        return signature_error
    # Generic sheets store their dynamic cells as JSON because each stage has different fields.
    payload = {key: value for key, value in form.multi_items() if not key.startswith("__session_signature_")}

    entry_id = insert_sheet_entry(
        current_user(request),
        {
            "run_id": current_run_id(request),
            "stage_key": stage_key,
            "stage_title": stage["title"],
            "operator_initials": (form.get("operator_initials") or current_signature_initials(request) or current_initials(request)).strip().upper(),
            "entry_date": form.get("entry_date", ""),
            "comments": form.get("comments", ""),
            "payload_json": json.dumps(payload),
        },
    )

    insert_audit(
        table_name="sheet_entries",
        record_id=entry_id,
        action_type="create",
        changed_by=current_user(request),
        old_data="",
        new_data=f"{stage['title']} entry created",
    )

    return RedirectResponse("/stages", status_code=303)


# ------------------------
# EDIT DATA
# ------------------------

@app.get("/edit/extraction/{entry_id}", response_class=HTMLResponse)
def edit_extraction_page(request: Request, entry_id: int):
    """Render the extraction correction form for a saved entry."""
    redirect = require_login(request)
    if redirect:
        return redirect

    entry = get_extraction_entry(entry_id)
    return render_page(
        request,
        "extraction.html",
        run=None,
        entry=entry,
        is_edit=True,
        form_action=f"/edit/extraction/{entry_id}",
        submit_label="Save Extraction Changes",
    )


@app.post("/edit/extraction/{entry_id}")
async def edit_extraction_submit(request: Request, entry_id: int):
    """Validate and save extraction corrections while logging field-level changes."""
    redirect = require_login(request)
    if redirect:
        return redirect
    entry = get_extraction_entry(entry_id)
    form = await request.form()
    signature_error = require_handwritten_signature(request, form)
    if signature_error:
        return signature_error
    correction_reason = clean_value(form.get("correction_reason", ""))
    changes, missing_details, mismatched_values = collect_field_changes(
        form,
        {
            "operator_initials": entry["operator_initials"],
            "entry_date": entry["entry_date"],
            "entry_time": entry["entry_time"],
            "location": entry["location"],
            "time_on_pipe_or_pile": entry["time_on_pile"],
            "start_time": entry["start_time"],
            "stop_time": entry["stop_time"],
            "psf1_speed": entry["psf1_speed"],
            "psf1_load": entry["psf1_load"],
            "psf1_blowback": entry["psf1_blowback"],
            "psf2_speed": entry["psf2_speed"],
            "psf2_load": entry["psf2_load"],
            "psf2_blowback": entry["psf2_blowback"],
            "press_speed": entry["press_speed"],
            "press_load": entry["press_load"],
            "press_blowback": entry["press_blowback"],
            "pressate_ri": entry["pressate_ri"],
            "chip_bin_steam": entry["chip_bin_steam"],
            "chip_chute_temp": entry["chip_chute_temp"],
            "notes": entry["comments"],
            "photo_path": entry["photo_path"],
        },
        current_user(request),
        correction_reason,
    )
    if missing_details:
        return correction_missing_response(missing_details)
    if mismatched_values:
        return correction_error_response("Original saved values do not match these fields", mismatched_values)
    operator_initials = (form.get("operator_initials") or current_signature_initials(request) or current_initials(request)).strip().upper()
    update_extraction(entry_id, current_user(request), build_extraction_payload(form, operator_initials))
    insert_field_change_log(entry["run_id"], "extraction_entries", entry_id, changes)
    insert_audit(
        table_name="extraction_entries",
        record_id=entry_id,
        action_type="update",
        changed_by=current_user(request),
        old_data="",
        new_data="extraction entry updated",
    )
    return RedirectResponse("/process-dashboard", status_code=303)


@app.get("/edit/filtration/{entry_id}", response_class=HTMLResponse)
def edit_filtration_page(request: Request, entry_id: int):
    """Render the filtration correction form for a saved entry."""
    redirect = require_login(request)
    if redirect:
        return redirect
    entry, rows = get_filtration_entry(entry_id)
    return render_page(
        request,
        "filtration.html",
        run=None,
        entry=entry,
        row_map=build_filtration_row_map(rows),
        is_edit=True,
        form_action=f"/edit/filtration/{entry_id}",
        submit_label="Save Filtration Changes",
    )


@app.post("/edit/filtration/{entry_id}")
async def edit_filtration_submit(request: Request, entry_id: int):
    """Validate and save filtration corrections while logging field-level changes."""
    redirect = require_login(request)
    if redirect:
        return redirect
    entry, existing_rows = get_filtration_entry(entry_id)
    form = await request.form()
    signature_error = require_handwritten_signature(request, form)
    if signature_error:
        return signature_error
    correction_reason = clean_value(form.get("correction_reason", ""))
    old_values = {
        "operator_initials": entry["operator_initials"],
        "entry_date": entry["entry_date"],
        "clarification_sequential_no": entry["clarification_sequential_no"],
        "retentate_flow_set_point": entry["retentate_flow_set_point"],
        "zero_refract": entry["zero_refract"],
        "startup_time": entry["startup_time"],
        "shutdown_time": entry["shutdown_time"],
        "notes": entry["comments"],
        "photo_path": entry["photo_path"],
    }
    for row in existing_rows:
        if row["row_group"] == "main":
            prefix = f"row{row['row_no']}"
        else:
            prefix = f"dia_row{row['row_no']}"
        old_values[f"{prefix}_time"] = row["row_time"]
        old_values[f"{prefix}_feed_ri"] = row["feed_ri"]
        old_values[f"{prefix}_retentate_ri"] = row["retentate_ri"]
        old_values[f"{prefix}_permeate_ri"] = row["permeate_ri"]
        if row["row_group"] == "main":
            old_values[f"{prefix}_perm_flow_c"] = row["perm_flow_c"]
            old_values[f"{prefix}_perm_flow_d"] = row["perm_flow_d"]
    changes, missing_details, mismatched_values = collect_field_changes(form, old_values, current_user(request), correction_reason)
    if missing_details:
        return correction_missing_response(missing_details)
    if mismatched_values:
        return correction_error_response("Original saved values do not match these fields", mismatched_values)
    operator_initials = (form.get("operator_initials") or current_signature_initials(request) or current_initials(request)).strip().upper()
    update_filtration(entry_id, current_user(request), build_filtration_payload(form, operator_initials))
    insert_field_change_log(entry["run_id"], "filtration_entries", entry_id, changes)
    insert_audit(
        table_name="filtration_entries",
        record_id=entry_id,
        action_type="update",
        changed_by=current_user(request),
        old_data="",
        new_data="filtration entry updated",
    )
    return RedirectResponse("/process-dashboard", status_code=303)


@app.get("/edit/evaporation/{entry_id}", response_class=HTMLResponse)
def edit_evaporation_page(request: Request, entry_id: int):
    """Render the evaporation correction form for a saved entry."""
    redirect = require_login(request)
    if redirect:
        return redirect
    entry, rows = get_evaporation_entry(entry_id)
    return render_page(
        request,
        "evaporation.html",
        entry=entry,
        row_map=build_evaporation_row_map(rows),
        is_edit=True,
        form_action=f"/edit/evaporation/{entry_id}",
        submit_label="Save Evaporation Changes",
    )


@app.post("/edit/evaporation/{entry_id}")
async def edit_evaporation_submit(request: Request, entry_id: int):
    """Validate and save evaporation corrections while logging field-level changes."""
    redirect = require_login(request)
    if redirect:
        return redirect
    entry, existing_rows = get_evaporation_entry(entry_id)
    form = await request.form()
    signature_error = require_handwritten_signature(request, form)
    if signature_error:
        return signature_error
    correction_reason = clean_value(form.get("correction_reason", ""))
    old_values = {
        "operator_initials": entry["operator_initials"],
        "entry_date": entry["entry_date"],
        "evaporator_no": entry["evaporator_no"],
        "startup_time": entry["startup_time"],
        "shutdown_time": entry["shutdown_time"],
        "feed_ri": entry["feed_ri"],
        "concentrate_ri": entry["concentrate_ri"],
        "steam_pressure": entry["steam_pressure"],
        "vacuum": entry["vacuum"],
        "sump_level": entry["sump_level"],
        "product_temp": entry["product_temp"],
        "notes": entry["comments"],
        "photo_path": entry["photo_path"],
    }
    for row in existing_rows:
        prefix = f"row{row['row_no']}"
        old_values[f"{prefix}_time"] = row["row_time"]
        old_values[f"{prefix}_feed_rate"] = row["feed_rate"]
        old_values[f"{prefix}_evap_temp"] = row["evap_temp"]
        old_values[f"{prefix}_vacuum"] = row["row_vacuum"]
        old_values[f"{prefix}_concentrate_ri"] = row["row_concentrate_ri"]
    changes, missing_details, mismatched_values = collect_field_changes(form, old_values, current_user(request), correction_reason)
    if missing_details:
        return correction_missing_response(missing_details)
    if mismatched_values:
        return correction_error_response("Original saved values do not match these fields", mismatched_values)
    operator_initials = (form.get("operator_initials") or current_signature_initials(request) or current_initials(request)).strip().upper()
    update_evaporation(
        entry_id,
        current_user(request),
        build_evaporation_payload(form, entry["run_id"], operator_initials),
    )
    insert_field_change_log(entry["run_id"], "evaporation_entries", entry_id, changes)
    insert_audit(
        table_name="evaporation_entries",
        record_id=entry_id,
        action_type="update",
        changed_by=current_user(request),
        old_data="",
        new_data="evaporation entry updated",
    )
    return RedirectResponse("/stages", status_code=303)


@app.get("/edit/generic/{entry_id}", response_class=HTMLResponse)
def edit_generic_page(request: Request, entry_id: int):
    """Render the generic batch-pack correction form for a saved entry."""
    redirect = require_login(request)
    if redirect:
        return redirect
    entry = get_sheet_entry(entry_id)
    stage_key = entry["stage_key"]
    stage = get_generic_stage(stage_key)
    payload = json.loads(entry["payload_json"] or "{}")
    return render_page(
        request,
        "generic_sheet.html",
        stage_key=stage_key,
        stage=stage,
        entry_values=payload,
        entry=entry,
        is_edit=True,
        form_action=f"/edit/generic/{entry_id}",
        submit_label=f"Save {stage['title']} Changes",
    )


@app.post("/edit/generic/{entry_id}")
async def edit_generic_submit(request: Request, entry_id: int):
    """Validate and save generic sheet corrections while logging field-level changes."""
    redirect = require_login(request)
    if redirect:
        return redirect
    entry = get_sheet_entry(entry_id)
    form = await request.form()
    signature_error = require_handwritten_signature(request, form)
    if signature_error:
        return signature_error
    correction_reason = clean_value(form.get("correction_reason", ""))
    # Internal correction-helper fields are stripped before the real sheet payload is re-saved.
    payload = {
        key: value
        for key, value in form.multi_items()
        if not key.startswith("__change__")
        and not key.startswith("__original__")
        and not key.startswith("__corrected__")
        and not key.startswith("__session_signature_")
        and key != "correction_reason"
    }
    old_values = json.loads(entry["payload_json"] or "{}")
    old_values["comments"] = entry["comments"]
    old_values["entry_date"] = entry["entry_date"]
    old_values["operator_initials"] = entry["operator_initials"]
    changes, missing_details, mismatched_values = collect_field_changes(form, old_values, current_user(request), correction_reason)
    if missing_details:
        return correction_missing_response(missing_details)
    if mismatched_values:
        return correction_error_response("Original saved values do not match these fields", mismatched_values)
    update_sheet_entry(
        entry_id,
        current_user(request),
        {
            "operator_initials": (form.get("operator_initials") or current_signature_initials(request) or current_initials(request)).strip().upper(),
            "entry_date": form.get("entry_date", ""),
            "comments": form.get("comments", ""),
            "payload_json": json.dumps(payload),
        },
    )
    insert_field_change_log(entry["run_id"], "sheet_entries", entry_id, changes)
    insert_audit(
        table_name="sheet_entries",
        record_id=entry_id,
        action_type="update",
        changed_by=current_user(request),
        old_data="",
        new_data=f"{entry['stage_title']} entry updated",
    )
    return RedirectResponse("/stages", status_code=303)


# ------------------------
# DASHBOARD
# ------------------------

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """Render the grouped batch-pack dashboard used to reopen saved batch sheets."""
    redirect = require_login(request)
    if redirect:
        return redirect

    activity_rows = last_12_hour_activity()
    return render_page(request, "dashboard.html", rows=activity_rows, batch_packs=dashboard_batch_packs(activity_rows))


@app.get("/change-history", response_class=HTMLResponse)
def change_history(request: Request):
    """Render the correction history dashboard for all runs and the active run."""
    redirect = require_login(request)
    if redirect:
        return redirect

    # `changes` holds the full plant-wide correction history.
    changes = []
    for row in get_field_change_history():
        item = dict(row)
        item["display_sheet"] = display_sheet_name(item["entry_table"])
        changes.append(item)

    # `active_changes` narrows the same history to the run currently selected in session.
    active_changes = []
    if current_run_id(request):
        for row in get_field_change_history(current_run_id(request)):
            item = dict(row)
            item["display_sheet"] = display_sheet_name(item["entry_table"])
            active_changes.append(item)

    return render_page(
        request,
        "change_history.html",
        changes=changes,
        active_changes=active_changes,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=configured_host(), port=configured_port(), reload=False)
