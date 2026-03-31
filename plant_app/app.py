from pathlib import Path
from datetime import datetime
import json

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from db import (
    init_db,
    validate_user,
    get_user_initials,
    create_run,
    get_run,
    list_runs,
    mark_run_complete,
    update_run,
    get_extraction_entry,
    update_extraction,
    get_filtration_entry,
    update_filtration,
    get_evaporation_entry,
    get_latest_evaporation_for_run,
    update_evaporation,
    get_sheet_entry,
    get_latest_sheet_entry_for_run_stage,
    update_sheet_entry,
    insert_extraction,
    insert_filtration,
    insert_evaporation,
    insert_sheet_entry,
    insert_field_change_log,
    insert_audit,
    get_field_change_history,
    last_12_hour_activity,
)
from stage_defs import GENERIC_STAGE_DEFS, STAGE_LINKS, PROCESS_STAGE_LINKS

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="lonza-secret-key-change-me")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

init_db()


# ------------------------
# HELPERS
# ------------------------

def logged_in(request: Request) -> bool:
    return bool(request.session.get("user"))


def current_user(request: Request) -> str:
    return request.session.get("user", "")


def current_initials(request: Request) -> str:
    return request.session.get("initials", "")


def current_run_id(request: Request):
    return request.session.get("run_id")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def active_run(request: Request):
    run_id = current_run_id(request)
    return get_run(run_id) if run_id else None


def require_login(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)
    return None


def require_run(request: Request):
    if not current_run_id(request):
        return RedirectResponse("/run/select", status_code=303)
    return None


def get_generic_stage(stage_key: str):
    return GENERIC_STAGE_DEFS.get(stage_key)


def render_page(request: Request, template_name: str, **context):
    page_context = {
        "request": request,
        "user": current_user(request),
        "initials": current_initials(request),
        "today": today_str(),
        "run": active_run(request),
    }
    page_context.update(context)
    return templates.TemplateResponse(template_name, page_context)


def clean_value(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def collect_field_changes(form, old_values: dict, changed_by: str, correction_reason: str):
    changes = []
    missing_details = []

    for key, value in form.multi_items():
        if key == "correction_reason":
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
    field_list = ", ".join(fields[:8])
    if len(fields) > 8:
        field_list += ", ..."
    return PlainTextResponse(
        f"{prefix}: {field_list}",
        status_code=400,
    )


def correction_missing_response(fields: list[str]):
    return correction_error_response("Please add initials for each edited field", fields)


def display_sheet_name(entry_table: str, section: str = "", stage_title: str = "") -> str:
    if stage_title:
        return stage_title
    if section:
        return section
    labels = {
        "extraction_entries": "Extraction",
        "filtration_entries": "Filtration",
        "evaporation_entries": "Evaporation",
        "sheet_entries": "Batch Sheet",
        "production_runs": "Batch",
    }
    return labels.get(entry_table, entry_table.replace("_", " ").title())


def process_dashboard_rows():
    return [row for row in last_12_hour_activity() if row["section"] in {"Extraction", "Filtration"}]


def build_filtration_row_map(rows):
    row_map = {}
    for row in rows:
        prefix = "dia" if row["row_group"] == "dia" else "main"
        row_map[f"{prefix}_{row['row_no']}"] = row
    return row_map


def build_evaporation_row_map(rows):
    return {f"row{row['row_no']}": row for row in rows}


def build_extraction_payload(form, operator_initials: str):
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
    rows = []
    for i in range(1, 4):
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


def process_dashboard_items():
    items = []
    for row in process_dashboard_rows():
        href = ""
        if row["section"] == "Extraction":
            href = f"/edit/extraction/{row['record_id']}"
        elif row["section"] == "Filtration":
            href = f"/edit/filtration/{row['record_id']}"
        items.append({**dict(row), "edit_href": href, "display_section": display_sheet_name(row["entry_table"], row["section"])})
    return items


def dashboard_batch_packs():
    packs = {}
    for row in last_12_hour_activity():
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
    run = get_run(run_id)
    evaporation_entry, evaporation_rows = get_latest_evaporation_for_run(run_id)

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
    return "OK"


# ------------------------
# LOGIN
# ------------------------

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    if logged_in(request):
        return RedirectResponse("/home", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": "",
        },
    )


@app.post("/login")
def login(
    request: Request,
    employee: str = Form(...),
    password: str = Form(...),
):
    employee = employee.strip()

    if validate_user(employee, password):
        request.session["user"] = employee
        request.session["initials"] = get_user_initials(employee)
        return RedirectResponse("/home", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": "Invalid employee number or password.",
        },
        status_code=400,
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ------------------------
# HOME
# ------------------------

@app.get("/home", response_class=HTMLResponse)
def home(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "home.html")


# ------------------------
# RUN SELECTION
# ------------------------

@app.get("/run/select", response_class=HTMLResponse)
def run_select_page(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "run_select.html", runs=list_runs())


@app.post("/run/select")
def run_select(
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
    redirect = require_login(request)
    if redirect:
        return redirect

    try:
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
    redirect = require_login(request)
    if redirect:
        return redirect

    request.session["run_id"] = run_id
    return RedirectResponse("/stages", status_code=303)


@app.get("/batch/edit", response_class=HTMLResponse)
def batch_edit_page(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    return render_page(request, "batch_edit.html")


@app.post("/batch/edit")
def batch_edit_submit(
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
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

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
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "process_dashboard.html", stage_links=PROCESS_STAGE_LINKS, items=process_dashboard_items())


# ------------------------
# STAGE SELECTION
# ------------------------

@app.get("/stages", response_class=HTMLResponse)
def stages(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    return render_page(request, "stages.html", stage_links=STAGE_LINKS)


@app.get("/batch/review", response_class=HTMLResponse)
def batch_review_page(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    review = build_batch_review(current_run_id(request))
    return render_page(request, "batch_review.html", **review)


@app.post("/batch/review/finalize")
def finalize_batch_review(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

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
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "extraction.html", run=None)


@app.post("/submit/extraction")
async def submit_extraction(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    form = await request.form()
    operator_initials = (form.get("operator_initials") or current_initials(request)).strip().upper()

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
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "filtration.html", run=None)


@app.post("/submit/filtration")
async def submit_filtration(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    form = await request.form()

    try:
        operator_initials = (form.get("operator_initials") or current_initials(request)).strip().upper()
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
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    form = await request.form()
    try:
        operator_initials = (form.get("operator_initials") or current_initials(request)).strip().upper()
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
    payload = {key: value for key, value in form.multi_items()}

    entry_id = insert_sheet_entry(
        current_user(request),
        {
            "run_id": current_run_id(request),
            "stage_key": stage_key,
            "stage_title": stage["title"],
            "operator_initials": (form.get("operator_initials") or current_initials(request)).strip().upper(),
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
    redirect = require_login(request)
    if redirect:
        return redirect
    entry = get_extraction_entry(entry_id)
    form = await request.form()
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
    operator_initials = (form.get("operator_initials") or current_initials(request)).strip().upper()
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
    redirect = require_login(request)
    if redirect:
        return redirect
    entry, existing_rows = get_filtration_entry(entry_id)
    form = await request.form()
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
    operator_initials = (form.get("operator_initials") or current_initials(request)).strip().upper()
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
    redirect = require_login(request)
    if redirect:
        return redirect
    entry, existing_rows = get_evaporation_entry(entry_id)
    form = await request.form()
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
    operator_initials = (form.get("operator_initials") or current_initials(request)).strip().upper()
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
    redirect = require_login(request)
    if redirect:
        return redirect
    entry = get_sheet_entry(entry_id)
    form = await request.form()
    correction_reason = clean_value(form.get("correction_reason", ""))
    payload = {
        key: value
        for key, value in form.multi_items()
        if not key.startswith("__change__")
        and not key.startswith("__original__")
        and not key.startswith("__corrected__")
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
            "operator_initials": (form.get("operator_initials") or current_initials(request)).strip().upper(),
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
    redirect = require_login(request)
    if redirect:
        return redirect

    return render_page(request, "dashboard.html", rows=last_12_hour_activity(), batch_packs=dashboard_batch_packs())


@app.get("/change-history", response_class=HTMLResponse)
def change_history(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    changes = []
    for row in get_field_change_history():
        item = dict(row)
        item["display_sheet"] = display_sheet_name(item["entry_table"])
        changes.append(item)

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
