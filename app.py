"""FastAPI application for operator login, run setup, data entry, and correction flows."""

# Standard-library imports used for path resolution, timestamp helpers, and JSON sheet payloads.
import base64
import binascii
from pathlib import Path
from datetime import datetime
import json
import os
import socket
from time import perf_counter
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
    backend_status,  # Reports the local database file this server is using.
    validate_user,  # Authenticates an employee number and password pair.
    get_user_initials,  # Loads the initials displayed and reused in forms.
    get_user_preferences,  # Loads persisted per-user UI preferences.
    update_user_preferences,  # Saves persisted per-user UI preferences.
    create_run,  # Creates a new run record.
    get_run,  # Fetches a single run record by id.
    list_runs,  # Lists recent runs for the run selection screen.
    list_open_runs,  # Lists open runs for the home quick-access panels.
    get_runs_by_ids,  # Loads selected runs for multi-run actions and audit printing.
    mark_run_complete,  # Finalizes a run after review.
    apply_run_group_action,  # Applies shared split/blend labels across selected runs.
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
app.add_middleware(SessionMiddleware, secret_key="lag-secret-key-change-me")

# Base directory used to resolve the bundled static assets and Jinja templates.
BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SIGNATURE_DIR = UPLOAD_DIR / "signatures"
SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)
SIGNATURE_DEBUG_LOG = RUNTIME_DIR / "signature_debug.log"
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
BOOT_TEMPLATE_NAMES = tuple(
    sorted(
        path.relative_to(BASE_DIR / "templates").as_posix()
        for path in (BASE_DIR / "templates").glob("**/*.html")
    )
)
BOOT_STATIC_FILES = (
    "style.css",
    "settings.js",
    "dynamic_rows.js",
    "signature_session.js",
    "form_corrections.js",
    "image_upload.js",
    "logo.png",
)
BOOT_MIN_DURATION_MS = 1200
RUN_STAGE_KEYS = tuple(stage_key for stage_key in GENERIC_STAGE_DEFS if stage_key != "filtration_cycles")
MACHINE_DEFINITIONS = (
    {"section": "Extraction", "title": "Extraction", "href": "/stage/extraction"},
    {"section": "Filtration", "title": "Filtration", "href": "/stage/filtration"},
    {"section": "Evaporation", "title": "Evaporation", "href": "/stage/evaporation"},
)


def current_app_build() -> dict[str, str]:
    """Return the latest code/build marker visible on disk for this app."""
    candidate_paths = [
        BASE_DIR / "app.py",
        BASE_DIR / "db.py",
        BASE_DIR / "stage_defs.py",
        BASE_DIR / "static" / "style.css",
        BASE_DIR / "static" / "settings.js",
        BASE_DIR / "static" / "dynamic_rows.js",
        BASE_DIR / "static" / "signature_session.js",
        BASE_DIR / "static" / "form_corrections.js",
        BASE_DIR / "static" / "image_upload.js",
        BASE_DIR / "static" / "logo.png",
    ]
    candidate_paths.extend(sorted((BASE_DIR / "templates").glob("**/*.html")))

    latest_stamp = 0
    latest_path = BASE_DIR / "app.py"
    for path in candidate_paths:
        try:
            modified = path.stat().st_mtime_ns
        except OSError:
            continue
        if modified >= latest_stamp:
            latest_stamp = modified
            latest_path = path

    if not latest_stamp:
        latest_stamp = int(datetime.now().timestamp() * 1_000_000_000)

    try:
        changed_file = latest_path.relative_to(BASE_DIR).as_posix()
    except ValueError:
        changed_file = latest_path.name

    return {
        "version": str(latest_stamp),
        "build_label": datetime.fromtimestamp(latest_stamp / 1_000_000_000).strftime("%Y-%m-%d %I:%M:%S %p"),
        "changed_file": changed_file,
    }


LOADED_APP_BUILD = current_app_build()


def asset_version() -> str:
    """Return a cache-busting version based on the newest tracked app file on disk."""
    return current_app_build()["version"]


def warm_boot_cache() -> None:
    """Prime templates, static metadata, and common database reads before the login page opens."""
    for template_name in BOOT_TEMPLATE_NAMES:
        try:
            templates.env.get_template(template_name)
        except Exception:
            continue

    for static_name in BOOT_STATIC_FILES:
        try:
            (BASE_DIR / "static" / static_name).stat()
        except OSError:
            continue

    asset_version()
    try:
        list_runs(limit=12)
    except Exception:
        pass
    try:
        last_12_hour_activity(limit=36)
    except Exception:
        pass


def build_boot_manifest(request: Request) -> dict:
    """Return the startup preload plan shown by the animated boot screen."""
    version = asset_version()
    login_url = "/?fresh=1"
    tasks = [
        {
            "label": "Loading system stylesheet",
            "url": f"/static/style.css?v={version}",
            "kind": "text",
        },
        {
            "label": "Caching shared app controls",
            "url": f"/static/settings.js?v={version}",
            "kind": "text",
        },
        {
            "label": "Caching signature capture tools",
            "url": f"/static/signature_session.js?v={version}",
            "kind": "text",
        },
        {
            "label": "Caching correction editor tools",
            "url": f"/static/form_corrections.js?v={version}",
            "kind": "text",
        },
        {
            "label": "Caching image upload helpers",
            "url": f"/static/image_upload.js?v={version}",
            "kind": "text",
        },
        {
            "label": "Loading plant branding assets",
            "url": f"/static/logo.png?v={version}",
            "kind": "image",
        },
        {
            "label": "Warming templates and database reads",
            "url": "/boot/warm",
            "kind": "json",
        },
        {
            "label": "Preparing the operator login screen",
            "url": login_url,
            "kind": "text",
        },
    ]
    return {
        "target_url": login_url,
        "min_duration_ms": BOOT_MIN_DURATION_MS,
        "tasks": tasks,
        "local_port": request.url.port or configured_port(),
    }


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

# Ensure the local database file is reachable before any request handlers run.
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


def append_signature_debug_log(event_name: str, request: Request | None = None, **details) -> None:
    """Append a compact JSON line that helps trace where signature capture gets stuck."""
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "event": event_name,
    }
    if request is not None:
        payload["path"] = str(request.url.path)
        payload["user"] = current_user(request)
        payload["signature_ready"] = signature_session_ready(request)
    for key, value in details.items():
        if value in {None, ""}:
            continue
        if isinstance(value, (int, float, bool)):
            payload[key] = value
        else:
            payload[key] = clean_value(value)[:240]
    try:
        with SIGNATURE_DEBUG_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except OSError:
        pass


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


def run_display_number(record) -> str:
    """Return the primary run identifier shown across the UI."""
    if not record:
        return ""

    run_number = clean_value(record.get("run_number", ""))
    if run_number:
        return run_number

    batch_number = clean_value(record.get("batch_number", ""))
    if batch_number:
        return batch_number

    record_id = record.get("id") or record.get("run_id")
    return str(record_id) if record_id else ""


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
    """Redirect users to run selection until an active run is chosen."""
    if not current_run_id(request):
        return RedirectResponse("/run/select", status_code=303)
    return None


def get_generic_stage(stage_key: str):
    """Look up a generic stage configuration by its route key."""
    return GENERIC_STAGE_DEFS.get(stage_key)


def field_default_value(field, run=None) -> str:
    """Return the default value for a generic sheet field when no saved value exists."""
    field_name = field[0]
    configured_default = field[4] if len(field) > 4 else ""
    if configured_default:
        return configured_default

    if run:
        if field_name in {"run_number", "production_number"}:
            return run_display_number(run)
        if field_name == "run_blend_number":
            return clean_value(run.get("blend_number", "")) or run_display_number(run)
    return ""


def generic_table_render_rows(table: dict, payload: dict) -> int:
    """Show only populated rows by default, while keeping saved rows visible."""
    if not payload:
        return max(1, int(table.get("initial_rows", 1)))

    prefix = f"{table['prefix']}_"
    populated_rows: set[int] = set()
    for row_index in range(1, int(table.get("rows", 1)) + 1):
        row_prefix = f"{prefix}{row_index}_"
        for column in table["columns"]:
            value = payload.get(f"{row_prefix}{column[0]}", "")
            if clean_value(value):
                populated_rows.add(row_index)
                break

    if populated_rows:
        return min(max(populated_rows), int(table.get("rows", 1)))
    return max(1, int(table.get("initial_rows", 1)))


def generic_stage_for_render(stage: dict, payload: dict | None = None) -> dict:
    """Return a shallow stage copy with table row counts tailored to saved data."""
    payload = payload or {}
    prepared_stage = {**stage}
    prepared_tables = []
    for table in stage.get("tables", []):
        prepared_tables.append({**table, "render_rows": generic_table_render_rows(table, payload)})
    prepared_stage["tables"] = prepared_tables
    return prepared_stage


def render_page(request: Request, template_name: str, **context):
    """Render a template with the standard navigation/session context already included."""
    # Shared template values used by most pages for nav badges and defaults.
    loaded_build = LOADED_APP_BUILD
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
        "app_loaded_version": loaded_build["version"],
        "app_loaded_build_label": loaded_build["build_label"],
        "app_loaded_changed_file": loaded_build["changed_file"],
        "today": today_str(),
        "run": active_run(request),
        "local_access_urls": local_access_urls(request),
        "local_port": request.url.port or configured_port(),
        "blank_display": blank_display,
        "blank_stamp": blank_stamp,
        "is_blank_value": is_blank_value,
        "run_display_number": run_display_number,
        "field_default_value": field_default_value,
        "activity_open_href": activity_open_href,
    }
    page_context.update(context)
    return templates.TemplateResponse(request=request, name=template_name, context=page_context)


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
        "sheet_entries": "Run Sheet",
        "production_runs": "Run",
    }
    return labels.get(entry_table, entry_table.replace("_", " ").title())


def selected_run_ids_from_form(form) -> list[int]:
    """Read unique selected run ids from a checkbox form."""
    selected_ids: list[int] = []
    for raw_value in form.getlist("selected_run_ids"):
        try:
            run_id = int(str(raw_value).strip())
        except (TypeError, ValueError):
            continue
        if run_id > 0 and run_id not in selected_ids:
            selected_ids.append(run_id)
    return selected_ids


def run_action_label(action_name: str) -> str:
    """Build a deterministic timestamp-based group label for blend/split actions."""
    return f"{action_name.upper()}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def activity_open_href(row: dict) -> str:
    """Return the quickest reopen link for a recent activity row."""
    section = clean_value(row.get("section", ""))
    run_id = row.get("run_id")
    stage_key = clean_value(row.get("stage_key", ""))

    if section in {"Extraction", "Filtration"}:
        return "/process-dashboard"
    if section == "Evaporation" and run_id:
        return f"/run/use/{run_id}?next=/stage/evaporation"
    if row.get("entry_table") == "sheet_entries" and run_id and stage_key:
        return f"/run/use/{run_id}?next=/stage/generic/{stage_key}"
    if run_id:
        return f"/run/use/{run_id}"
    return "/dashboard"


def activity_is_active(row: dict) -> bool:
    """Treat rows without an end time or with an open run as active/in-use items."""
    if row.get("section") in {"Extraction", "Filtration", "Evaporation"}:
        return clean_value(row.get("end_label", "")) == ""
    return clean_value(row.get("status", "")) == "Open"


def machine_status_cards(rows=None, current_run=None):
    """Build the home-page machine quick-access cards from recent live activity."""
    source_rows = rows if rows is not None else last_12_hour_activity()
    cards = []
    for machine in MACHINE_DEFINITIONS:
        latest_row = next((row for row in source_rows if row["section"] == machine["section"]), None)
        is_currently_active = bool(latest_row and activity_is_active(latest_row))
        if latest_row:
            detail_parts = [latest_row["activity_time"]]
            if run_display_number(latest_row):
                detail_parts.insert(0, f"Run {run_display_number(latest_row)}")
            status_label = "In Use" if is_currently_active else "Recently Used"
            href = activity_open_href(latest_row)
            button_label = "Open Machine"
            detail = " | ".join(part for part in detail_parts if part)
        else:
            status_label = "Not Used"
            href = machine["href"] if machine["section"] in {"Extraction", "Filtration"} else (
                "/stage/evaporation" if current_run else "/run/select"
            )
            button_label = "Start Entry" if machine["section"] in {"Extraction", "Filtration"} else (
                "Open Machine" if current_run else "Choose Run"
            )
            detail = "Auto-populated as not in use until an operator starts this machine."

        cards.append(
            {
                **machine,
                "status_label": status_label,
                "detail": detail,
                "href": href,
                "button_label": button_label,
                "is_active": is_currently_active,
            }
        )
    return cards


def in_use_items(rows=None):
    """Return the most relevant active items to surface on the homepage."""
    source_rows = rows if rows is not None else last_12_hour_activity(limit=40)
    items = []
    seen_keys = set()
    for row in source_rows:
        if not activity_is_active(row):
            continue
        key = (row["entry_table"], row["record_id"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        items.append(
            {
                "title": display_sheet_name(row["entry_table"], row["section"]),
                "run_label": run_display_number(row),
                "activity_time": row["activity_time"],
                "comments": clean_value(row.get("comments", "")),
                "href": activity_open_href(row),
                "status_label": "In Use" if activity_is_active(row) else "Saved",
            }
        )
        if len(items) >= 10:
            break
    return items


def run_record_groups(rows=None):
    """Group run-linked records by run number for the dashboard screen."""
    groups = {}
    source_rows = rows if rows is not None else last_12_hour_activity()
    for row in source_rows:
        if not row.get("run_id"):
            continue
        run_key = run_display_number(row) or f"Run {row['run_id']}"
        group = groups.setdefault(
            run_key,
            {
                "run_key": run_key,
                "entries": [],
                "latest_time": row["activity_time"],
                "blend_numbers": set(),
                "statuses": set(),
            },
        )
        group["entries"].append(
            {
                **dict(row),
                "edit_href": activity_open_href(row),
                "display_section": display_sheet_name(row["entry_table"], row["section"]),
            }
        )
        if row["activity_time"] > group["latest_time"]:
            group["latest_time"] = row["activity_time"]
        if row.get("blend_number"):
            group["blend_numbers"].add(row["blend_number"])
        if row.get("status"):
            group["statuses"].add(row["status"])

    results = sorted(groups.values(), key=lambda group: group["latest_time"], reverse=True)
    for group in results:
        group["blend_numbers"] = ", ".join(sorted(group["blend_numbers"]))
        group["statuses"] = ", ".join(sorted(group["statuses"]))
        group["entry_count"] = len(group["entries"])
    return results


def process_dashboard_rows(rows=None):
    """Filter recent activity down to the standalone extraction and filtration sections."""
    source_rows = rows if rows is not None else last_12_hour_activity()
    return [row for row in source_rows if row["section"] in {"Extraction", "Filtration"}]


def build_filtration_row_map(rows):
    """Convert filtration child rows into template-friendly keys such as cycle1_1."""
    row_map = {}
    for row in rows:
        prefix = row.get("row_group") or "main"
        row_map[f"{prefix}_{row['row_no']}"] = row
    return row_map


def parse_payload_json(entry) -> dict:
    """Safely parse a saved JSON payload column."""
    if not entry:
        return {}
    try:
        return json.loads(entry.get("payload_json") or "{}")
    except (TypeError, ValueError):
        return {}


def filtration_cycle_render_rows(row_map: dict, prefix: str) -> int:
    """Return the visible Microflow row count for one cycle."""
    row_numbers = []
    for key, row in row_map.items():
        if not key.startswith(f"{prefix}_"):
            continue
        values = (
            row.get("row_time", ""),
            row.get("operator_initials", ""),
            row.get("fic1_gpm", ""),
            row.get("tit1", ""),
            row.get("tit2", ""),
            row.get("dpt", ""),
            row.get("dpm", ""),
            row.get("perm_total", ""),
            row.get("f12_gpm", ""),
            row.get("permeate_ri", ""),
            row.get("retentate_ri", ""),
            row.get("qic1_ntu_turbidity", ""),
            row.get("pressure_pt1", ""),
            row.get("pressure_pt2", ""),
            row.get("pressure_pt3", ""),
        )
        if any(clean_value(value) for value in values):
            row_numbers.append(int(row.get("row_no") or 1))
    return max(row_numbers) if row_numbers else 1


def filtration_cycle_context(row_map: dict | None = None) -> list[dict]:
    """Build the four Microflow cycle sections shown by the filtration template."""
    row_map = row_map or {}
    return [
        {
            "number": cycle_no,
            "prefix": f"cycle{cycle_no}",
            "render_rows": filtration_cycle_render_rows(row_map, f"cycle{cycle_no}"),
            "max_rows": 4,
        }
        for cycle_no in range(1, 5)
    ]


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


def form_row_indexes(form, prefix: str) -> list[int]:
    """Find row numbers submitted by a dynamic table prefix such as cycle1."""
    indexes: set[int] = set()
    marker = f"{prefix}_"
    for key in form.keys():
        if not key.startswith(marker):
            continue
        remainder = key[len(marker):]
        row_text = remainder.split("_", 1)[0]
        if row_text.isdigit():
            indexes.add(int(row_text))
    return sorted(indexes)


def build_filtration_rows(form):
    """Build normalized Microflow Filtration cycle rows from the dynamic table fields."""
    rows = []
    row_fields = (
        "time",
        "operator_initials",
        "fic1_gpm",
        "tit1",
        "tit2",
        "dpt",
        "dpm",
        "perm_total",
        "f12_gpm",
        "permeate_ri",
        "retentate_ri",
        "qic1_ntu_turbidity",
        "pressure_pt1",
        "pressure_pt2",
        "pressure_pt3",
    )
    for cycle_no in range(1, 5):
        prefix = f"cycle{cycle_no}"
        for row_no in form_row_indexes(form, prefix):
            row = {
                "row_group": prefix,
                "row_no": row_no,
                "row_time": form.get(f"{prefix}_{row_no}_time", ""),
                "operator_initials": form.get(f"{prefix}_{row_no}_operator_initials", ""),
                "fic1_gpm": form.get(f"{prefix}_{row_no}_fic1_gpm", ""),
                "tit1": form.get(f"{prefix}_{row_no}_tit1", ""),
                "tit2": form.get(f"{prefix}_{row_no}_tit2", ""),
                "dpt": form.get(f"{prefix}_{row_no}_dpt", ""),
                "dpm": form.get(f"{prefix}_{row_no}_dpm", ""),
                "perm_total": form.get(f"{prefix}_{row_no}_perm_total", ""),
                "f12_gpm": form.get(f"{prefix}_{row_no}_f12_gpm", ""),
                "permeate_ri": form.get(f"{prefix}_{row_no}_permeate_ri", ""),
                "retentate_ri": form.get(f"{prefix}_{row_no}_retentate_ri", ""),
                "qic1_ntu_turbidity": form.get(f"{prefix}_{row_no}_qic1_ntu_turbidity", ""),
                "pressure_pt1": form.get(f"{prefix}_{row_no}_pressure_pt1", ""),
                "pressure_pt2": form.get(f"{prefix}_{row_no}_pressure_pt2", ""),
                "pressure_pt3": form.get(f"{prefix}_{row_no}_pressure_pt3", ""),
                "feed_ri": "",
                "perm_flow_c": "",
                "perm_flow_d": "",
            }
            if any(clean_value(row.get(field if field != "time" else "row_time", "")) for field in row_fields):
                rows.append(row)
    return rows


def build_filtration_extra_payload(form) -> dict:
    """Store cycle summary fields that do not belong to a repeating reading row."""
    payload = {}
    cycle_summary_fields = ("cycle_number", "ri_to_sewer", "total_filtrate_volume", "cleaning_method")
    for cycle_no in range(1, 5):
        prefix = f"cycle{cycle_no}"
        for field_name in cycle_summary_fields:
            key = f"{prefix}_{field_name}"
            payload[key] = form.get(key, "")
    return payload


def build_filtration_payload(form, operator_initials: str):
    """Map the filtration form fields into the database payload expected by `insert_filtration`."""
    # The parent record fields live beside the child `rows` collection in one payload object.
    return {
        "run_id": None,
        "operator_initials": operator_initials,
        "entry_date": form.get("entry_date", ""),
        "cycle_volume_set_point": form.get("cycle_volume_set_point", ""),
        "clarification_sequential_no": form.get("clarification_sequential_no", ""),
        "retentate_flow_set_point": form.get("retentate_flow_set_point", ""),
        "zero_refract": form.get("zero_refract", ""),
        "startup_time": form.get("startup_time", ""),
        "shutdown_time": form.get("shutdown_time", ""),
        "start_time": form.get("start_time", ""),
        "stop_time": form.get("stop_time", ""),
        "comments": form.get("comments", "") or form.get("notes", ""),
        "photo_path": form.get("photo_path", ""),
        "payload_json": json.dumps(build_filtration_extra_payload(form)),
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
    # Unlike extraction/filtration, evaporation is always tied to a selected run.
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
    """Backward-compatible wrapper for the dashboard's run-record groupings."""
    return run_record_groups(rows)


def build_batch_review(run_id: int):
    """Gather the latest saved run-linked sheets so the review page can summarize them."""
    run = get_run(run_id)
    evaporation_entry, evaporation_rows = get_latest_evaporation_for_run(run_id)

    # Generic stage entries are discovered from configuration instead of hard-coded one by one.
    generic_entries = []
    for stage_key in RUN_STAGE_KEYS:
        stage = GENERIC_STAGE_DEFS[stage_key]
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

    # This return object is passed straight into the run review template.
    return {
        "run": run,
        "evaporation_entry": evaporation_entry,
        "evaporation_rows": evaporation_rows,
        "generic_entries": generic_entries,
        "has_entries": bool(evaporation_entry or generic_entries),
    }


def existing_open_run_by_number(run_number: str):
    """Reuse an already-open run when the operator enters the same run number again."""
    normalized = clean_value(run_number).lower()
    if not normalized:
        return None

    for run in list_open_runs(limit=200):
        if run_display_number(run).lower() == normalized:
            return run
    return None


def build_print_packets(selected_runs):
    """Build the audit-print payload for one or more selected runs."""
    packets = []
    for run in selected_runs:
        review = build_batch_review(run["id"])
        packets.append(
            {
                "run": review["run"],
                "run_label": run_display_number(review["run"]),
                "evaporation_entry": review["evaporation_entry"],
                "evaporation_rows": review["evaporation_rows"],
                "generic_entries": review["generic_entries"],
                "has_entries": review["has_entries"],
            }
        )
    return packets


def run_action_page_context(action_name: str, selected_run_ids: list[int] | None = None, message: str = "", error: str = "") -> dict:
    """Build shared context for the split/blend selection pages."""
    selected_ids = selected_run_ids or []
    selected_runs = get_runs_by_ids(selected_ids)
    action_title = action_name.title()
    return {
        "action_name": action_name,
        "action_title": action_title,
        "page_title": f"{action_title} Runs",
        "page_heading": f"{action_title} Runs",
        "page_copy": f"Choose one or more runs, then confirm {action_name} to apply the shared {action_name} action.",
        "runs": list_runs(limit=120),
        "selected_run_ids": selected_ids,
        "selected_runs": selected_runs,
        "result_message": message,
        "error_message": error,
        "submit_label": action_title,
    }


# ------------------------
# BASIC
# ------------------------

@app.get("/health", response_class=PlainTextResponse)
def health():
    """Simple health-check endpoint for smoke tests and deployment checks."""
    return "OK"


@app.get("/boot", response_class=HTMLResponse)
def boot_page(request: Request):
    """Show the startup animation, clear any stale session, and preload shared app resources."""
    clear_signature_session(request)
    request.session.clear()
    response = templates.TemplateResponse(
        request=request,
        name="boot.html",
        context={
            "request": request,
            "boot_manifest": build_boot_manifest(request),
            "asset_version": asset_version(),
        },
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/boot/warm")
def boot_warm():
    """Warm shared templates and database queries so the first operator interaction feels lighter."""
    warm_boot_cache()
    return JSONResponse({"ok": True})


@app.get("/app-status")
def app_status():
    """Return the build loaded by this server plus the latest code timestamp visible on disk."""
    current_build = current_app_build()
    db_status = backend_status()
    return JSONResponse(
        {
            "loaded_version": LOADED_APP_BUILD["version"],
            "loaded_build_label": LOADED_APP_BUILD["build_label"],
            "loaded_changed_file": LOADED_APP_BUILD["changed_file"],
            "disk_version": current_build["version"],
            "disk_build_label": current_build["build_label"],
            "disk_changed_file": current_build["changed_file"],
            "restart_required": current_build["version"] != LOADED_APP_BUILD["version"],
            "database_backend": db_status["backend"],
            "database_path": db_status["database_path"],
            "export_mode": db_status["export_mode"],
        }
    )


# ------------------------
# LOGIN
# ------------------------

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    """Render the login form or jump straight home when a session already exists."""
    fresh_login = request.query_params.get("fresh") == "1"
    if fresh_login:
        clear_signature_session(request)
        request.session.clear()
    elif logged_in(request):
        return RedirectResponse("/home", status_code=303)

    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
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
    if fresh_login:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


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
        request=request,
        name="login.html",
        context={
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

    started = perf_counter()
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        append_signature_debug_log("signature-session-invalid-json", request)
        return JSONResponse({"error": "The signature payload was not valid JSON."}, status_code=400)

    initials = clean_value(payload.get("initials", "")).upper()
    signature_data = clean_value(payload.get("signature_data", ""))
    signed_at = clean_value(payload.get("signed_at", ""))
    append_signature_debug_log(
        "signature-session-request",
        request,
        initials=initials,
        signed_at=signed_at,
        signature_length=len(signature_data),
    )
    if not initials or not signature_data or not signed_at:
        append_signature_debug_log(
            "signature-session-missing-fields",
            request,
            initials=initials,
            signed_at=signed_at,
            signature_length=len(signature_data),
        )
        return JSONResponse({"error": "Initials, signed time, and a handwritten signature are all required."}, status_code=400)

    if not update_signature_session(request, initials, signature_data, signed_at):
        append_signature_debug_log(
            "signature-session-save-failed",
            request,
            initials=initials,
            signed_at=signed_at,
            signature_length=len(signature_data),
            duration_ms=round((perf_counter() - started) * 1000, 1),
        )
        return JSONResponse({"error": "The app could not save that signature image. Please try again."}, status_code=400)

    append_signature_debug_log(
        "signature-session-save-ok",
        request,
        initials=current_signature_initials(request),
        signed_at=current_signature_signed_at(request),
        signature_ref=current_signature_data(request),
        signature_length=len(signature_data),
        duration_ms=round((perf_counter() - started) * 1000, 1),
    )
    return JSONResponse(
        {
            "ok": True,
            "initials": current_signature_initials(request),
            "signed_at": current_signature_signed_at(request),
            "signature_data": current_signature_data(request),
        }
    )


@app.post("/signature-debug")
async def signature_debug_api(request: Request):
    """Capture client-side signature flow breadcrumbs in a server log for desktop debugging."""
    redirect = require_login(request)
    if redirect:
        return PlainTextResponse("", status_code=204)

    try:
        payload = await request.json()
    except json.JSONDecodeError:
        append_signature_debug_log("signature-client-invalid-json", request)
        return PlainTextResponse("", status_code=204)

    event_name = clean_value(payload.get("event", "")) or "unknown"
    raw_details = payload.get("details", {})
    details = {}
    if isinstance(raw_details, dict):
        for key, value in raw_details.items():
            if isinstance(value, (str, int, float, bool)):
                details[f"client_{clean_value(key)}"] = value
    append_signature_debug_log(
        f"signature-client-{event_name}",
        request,
        client_page=payload.get("page", ""),
        client_at=payload.get("at", ""),
        **details,
    )
    return PlainTextResponse("", status_code=204)


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
    """Render the fast home screen for run creation, active runs, and machine access."""
    redirect = require_login(request)
    if redirect:
        return redirect

    activity_rows = last_12_hour_activity(limit=48)
    current_run = active_run(request)
    return render_page(
        request,
        "home.html",
        open_runs=list_open_runs(limit=80),
        machine_cards=machine_status_cards(activity_rows, current_run),
        in_use_items=in_use_items(activity_rows),
    )


# ------------------------
# RUN SELECTION
# ------------------------

@app.get("/run/select", response_class=HTMLResponse)
def run_select_page(request: Request):
    """Render the simplified run creation screen with quick access to recent runs."""
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(
        request,
        "run_select.html",
        runs=list_runs(limit=80),
        open_runs=list_open_runs(limit=80),
        create_error="",
    )


@app.post("/run/select")
async def run_select(
    request: Request,
    run_number: str = Form(""),
):
    """Create or reopen a run using only the run number."""
    redirect = require_login(request)
    if redirect:
        return redirect

    normalized_run_number = clean_value(run_number)
    if not normalized_run_number:
        return render_page(
            request,
            "run_select.html",
            runs=list_runs(limit=80),
            open_runs=list_open_runs(limit=80),
            create_error="Run number is required.",
        )

    existing_run = existing_open_run_by_number(normalized_run_number)
    if existing_run:
        request.session["run_id"] = existing_run["id"]
        return RedirectResponse("/home", status_code=303)

    try:
        run_id = create_run(
            batch_number=normalized_run_number,
            split_batch_number="",
            blend_number="",
            run_number=normalized_run_number,
            batch_type="standard",
            reused_batch=0,
            product_name="",
            shift_name="",
            operator_id=current_user(request),
            notes="",
        )
    except Exception as exc:
        return PlainTextResponse(f"Run save failed: {type(exc).__name__}: {exc}", status_code=500)

    request.session["run_id"] = run_id
    return RedirectResponse("/home", status_code=303)


@app.get("/run/use/{run_id}")
def use_run(request: Request, run_id: int):
    """Switch the current session to an existing run selected from the recent list."""
    redirect = require_login(request)
    if redirect:
        return redirect

    request.session["run_id"] = run_id
    next_path = clean_value(request.query_params.get("next", ""))
    if next_path.startswith("/"):
        return RedirectResponse(next_path, status_code=303)
    return RedirectResponse("/home", status_code=303)


@app.get("/run/edit", response_class=HTMLResponse)
@app.get("/batch/edit", response_class=HTMLResponse)
def batch_edit_page(request: Request):
    """Render the run detail form for the currently selected run."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    return render_page(request, "batch_edit.html")


@app.post("/run/edit")
@app.post("/batch/edit")
async def batch_edit_submit(
    request: Request,
    run_number: str = Form(""),
    product_name: str = Form(""),
    notes: str = Form(""),
    final_edit_initials: str = Form(""),
    final_edit_notes: str = Form(""),
):
    """Persist run detail edits and record the change in the audit log."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    form = await request.form()
    save_signature_session(request, form)
    final_edit_initials = (final_edit_initials or current_signature_initials(request) or current_initials(request)).strip().upper()
    current_run = active_run(request)
    normalized_run_number = clean_value(run_number) or run_display_number(current_run)

    update_run(
        run_id=current_run_id(request),
        batch_number=normalized_run_number,
        split_batch_number=current_run.get("split_batch_number", ""),
        blend_number=current_run.get("blend_number", ""),
        run_number=normalized_run_number,
        batch_type=current_run.get("batch_type", "standard"),
        reused_batch=current_run.get("reused_batch", 0),
        product_name=product_name,
        shift_name=current_run.get("shift_name", ""),
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
        new_data="run details updated",
    )

    return RedirectResponse("/home", status_code=303)


@app.post("/run/close/{run_id}")
def close_run(request: Request, run_id: int):
    """Close a run directly from a quick action without reopening each machine."""
    redirect = require_login(request)
    if redirect:
        return redirect

    mark_run_complete(run_id, current_user(request))
    insert_audit(
        table_name="production_runs",
        record_id=run_id,
        action_type="finalize",
        changed_by=current_user(request),
        old_data="",
        new_data="run closed from quick action",
    )
    if current_run_id(request) == run_id:
        request.session.pop("run_id", None)
    return RedirectResponse("/home", status_code=303)


@app.get("/runs/blend", response_class=HTMLResponse)
def blend_runs_page(request: Request):
    """Render the multi-run blend workflow."""
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "run_action.html", **run_action_page_context("blend"))


@app.post("/runs/blend")
async def blend_runs_submit(request: Request):
    """Apply a shared blend label to the selected runs."""
    redirect = require_login(request)
    if redirect:
        return redirect

    form = await request.form()
    selected_run_ids = selected_run_ids_from_form(form)
    if not selected_run_ids:
        return render_page(
            request,
            "run_action.html",
            **run_action_page_context("blend", error="Select at least one run to blend."),
        )

    blend_label = run_action_label("blend")
    apply_run_group_action(selected_run_ids, "blend", blend_label)
    request.session["run_id"] = selected_run_ids[0]
    return render_page(
        request,
        "run_action.html",
        **run_action_page_context(
            "blend",
            selected_run_ids=selected_run_ids,
            message=f"Blend {blend_label} saved for {len(selected_run_ids)} selected run(s).",
        ),
    )


@app.get("/runs/split", response_class=HTMLResponse)
def split_runs_page(request: Request):
    """Render the multi-run split workflow."""
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "run_action.html", **run_action_page_context("split"))


@app.post("/runs/split")
async def split_runs_submit(request: Request):
    """Apply a shared split label to the selected runs."""
    redirect = require_login(request)
    if redirect:
        return redirect

    form = await request.form()
    selected_run_ids = selected_run_ids_from_form(form)
    if not selected_run_ids:
        return render_page(
            request,
            "run_action.html",
            **run_action_page_context("split", error="Select at least one run to split."),
        )

    split_label = run_action_label("split")
    apply_run_group_action(selected_run_ids, "split", split_label)
    request.session["run_id"] = selected_run_ids[0]
    return render_page(
        request,
        "run_action.html",
        **run_action_page_context(
            "split",
            selected_run_ids=selected_run_ids,
            message=f"Split {split_label} saved for {len(selected_run_ids)} selected run(s).",
        ),
    )


@app.get("/runs/print", response_class=HTMLResponse)
def run_print_page(request: Request):
    """Render the audit print selection page for single or multi-run printing."""
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(
        request,
        "run_print.html",
        runs=list_runs(limit=120),
        selected_run_ids=[],
        selected_runs=[],
        print_packets=[],
        error_message="",
    )


@app.post("/runs/print")
async def run_print_submit(request: Request):
    """Build the audit print preview for the selected runs."""
    redirect = require_login(request)
    if redirect:
        return redirect

    form = await request.form()
    selected_run_ids = selected_run_ids_from_form(form)
    selected_runs = get_runs_by_ids(selected_run_ids)
    if not selected_runs:
        return render_page(
            request,
            "run_print.html",
            runs=list_runs(limit=120),
            selected_run_ids=[],
            selected_runs=[],
            print_packets=[],
            error_message="Select at least one run to print.",
        )

    return render_page(
        request,
        "run_print.html",
        runs=list_runs(limit=120),
        selected_run_ids=selected_run_ids,
        selected_runs=selected_runs,
        print_packets=build_print_packets(selected_runs),
        error_message="",
    )


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
    """Render the run-linked sheet picker for the currently selected run."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    return render_page(request, "stages.html", stage_links=STAGE_LINKS)


@app.get("/run/review", response_class=HTMLResponse)
@app.get("/batch/review", response_class=HTMLResponse)
def batch_review_page(request: Request):
    """Render the run review page for the active run."""
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    review = build_batch_review(current_run_id(request))
    return render_page(request, "batch_review.html", **review)


@app.post("/run/review/finalize")
@app.post("/batch/review/finalize")
async def finalize_batch_review(request: Request):
    """Mark the active run complete once at least one run-linked record exists."""
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
        return PlainTextResponse("Add at least one run record before closing the run.", status_code=400)

    mark_run_complete(current_run_id(request), current_user(request))
    insert_audit(
        table_name="production_runs",
        record_id=current_run_id(request),
        action_type="finalize",
        changed_by=current_user(request),
        old_data="",
        new_data="run review completed and run closed",
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

    return render_page(request, "filtration.html", run=None, entry_payload={}, filtration_cycles=filtration_cycle_context())


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
    """Render a generic run sheet driven entirely by `stage_defs.py`."""
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
    prepared_stage = generic_stage_for_render(stage, payload)
    return render_page(
        request,
        "generic_sheet.html",
        stage_key=stage_key,
        stage=prepared_stage,
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
        entry_payload=parse_payload_json(entry),
        filtration_cycles=filtration_cycle_context(build_filtration_row_map(rows)),
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
    entry_payload = parse_payload_json(entry)
    old_values = {
        "operator_initials": entry["operator_initials"],
        "entry_date": entry["entry_date"],
        "cycle_volume_set_point": entry.get("cycle_volume_set_point", ""),
        "zero_refract": entry["zero_refract"],
        "notes": entry["comments"],
        "photo_path": entry["photo_path"],
    }
    for cycle_no in range(1, 5):
        for field_name in ("cycle_number", "ri_to_sewer", "total_filtrate_volume", "cleaning_method"):
            key = f"cycle{cycle_no}_{field_name}"
            old_values[key] = entry_payload.get(key, "")
    for row in existing_rows:
        row_group = row.get("row_group") or "cycle1"
        prefix = f"{row_group}_{row['row_no']}"
        old_values[f"{prefix}_time"] = row["row_time"]
        old_values[f"{prefix}_operator_initials"] = row.get("operator_initials", "")
        old_values[f"{prefix}_fic1_gpm"] = row.get("fic1_gpm", "")
        old_values[f"{prefix}_tit1"] = row.get("tit1", "")
        old_values[f"{prefix}_tit2"] = row.get("tit2", "")
        old_values[f"{prefix}_dpt"] = row.get("dpt", "")
        old_values[f"{prefix}_dpm"] = row.get("dpm", "")
        old_values[f"{prefix}_perm_total"] = row.get("perm_total", "")
        old_values[f"{prefix}_f12_gpm"] = row.get("f12_gpm", "")
        old_values[f"{prefix}_permeate_ri"] = row["permeate_ri"]
        old_values[f"{prefix}_retentate_ri"] = row["retentate_ri"]
        old_values[f"{prefix}_qic1_ntu_turbidity"] = row.get("qic1_ntu_turbidity", "")
        old_values[f"{prefix}_pressure_pt1"] = row.get("pressure_pt1", "")
        old_values[f"{prefix}_pressure_pt2"] = row.get("pressure_pt2", "")
        old_values[f"{prefix}_pressure_pt3"] = row.get("pressure_pt3", "")
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
    """Render the generic run-sheet correction form for a saved entry."""
    redirect = require_login(request)
    if redirect:
        return redirect
    entry = get_sheet_entry(entry_id)
    stage_key = entry["stage_key"]
    stage = get_generic_stage(stage_key)
    payload = json.loads(entry["payload_json"] or "{}")
    prepared_stage = generic_stage_for_render(stage, payload)
    return render_page(
        request,
        "generic_sheet.html",
        stage_key=stage_key,
        stage=prepared_stage,
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
    """Render the grouped run-record dashboard used to reopen saved run sheets."""
    redirect = require_login(request)
    if redirect:
        return redirect

    activity_rows = last_12_hour_activity()
    return render_page(request, "dashboard.html", rows=activity_rows, run_groups=run_record_groups(activity_rows))


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
