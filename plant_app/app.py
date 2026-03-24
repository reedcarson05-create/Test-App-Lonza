from pathlib import Path
from datetime import datetime

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
    insert_extraction,
    insert_filtration,
    insert_audit,
    last_12_hour_activity,
)

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


def require_login(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)
    return None


def require_run(request: Request):
    if not current_run_id(request):
        return RedirectResponse("/run/select", status_code=303)
    return None


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
        return RedirectResponse("/run/select", status_code=303)

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
        return RedirectResponse("/run/select", status_code=303)

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
# RUN SELECTION
# ------------------------

@app.get("/run/select", response_class=HTMLResponse)
def run_select_page(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "run_select.html",
        {
            "request": request,
            "user": current_user(request),
            "runs": list_runs(),
        },
    )


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

    request.session["run_id"] = run_id
    return RedirectResponse("/stages", status_code=303)


@app.get("/run/use/{run_id}")
def use_run(request: Request, run_id: int):
    redirect = require_login(request)
    if redirect:
        return redirect

    request.session["run_id"] = run_id
    return RedirectResponse("/stages", status_code=303)


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

    return templates.TemplateResponse(
        "stages.html",
        {
            "request": request,
            "user": current_user(request),
            "run": get_run(current_run_id(request)),
        },
    )


# ------------------------
# EXTRACTION
# ------------------------

@app.get("/stage/extraction", response_class=HTMLResponse)
def extraction_page(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "extraction.html",
        {
            "request": request,
            "user": current_user(request),
            "initials": current_initials(request),
            "run": get_run(current_run_id(request)),
            "today": datetime.now().strftime("%Y-%m-%d"),
        },
    )


@app.post("/submit/extraction")
def submit_extraction(
    request: Request,
    operator_initials: str = Form(""),
    entry_date: str = Form(""),
    entry_time: str = Form(""),
    location: str = Form("Pile"),
    time_on_pile: str = Form(""),
    start_time: str = Form(""),
    stop_time: str = Form(""),
    psf1_speed: str = Form(""),
    psf1_load: str = Form(""),
    psf1_blowback: str = Form(""),
    psf2_speed: str = Form(""),
    psf2_load: str = Form(""),
    psf2_blowback: str = Form(""),
    press_speed: str = Form(""),
    press_load: str = Form(""),
    press_blowback: str = Form(""),
    pressate_ri: str = Form(""),
    chip_bin_steam: str = Form(""),
    chip_chute_temp: str = Form(""),
    comments: str = Form(""),
    photo_path: str = Form(""),
):
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    entry_id = insert_extraction(
        current_user(request),
        {
            "run_id": current_run_id(request),
            "operator_initials": (operator_initials or current_initials(request)).strip().upper(),
            "entry_date": entry_date,
            "entry_time": entry_time,
            "location": location or "Pile",
            "time_on_pile": time_on_pile,
            "start_time": start_time,
            "stop_time": stop_time,
            "psf1_speed": psf1_speed,
            "psf1_load": psf1_load,
            "psf1_blowback": psf1_blowback,
            "psf2_speed": psf2_speed,
            "psf2_load": psf2_load,
            "psf2_blowback": psf2_blowback,
            "press_speed": press_speed,
            "press_load": press_load,
            "press_blowback": press_blowback,
            "pressate_ri": pressate_ri,
            "chip_bin_steam": chip_bin_steam,
            "chip_chute_temp": chip_chute_temp,
            "comments": comments,
            "photo_path": photo_path,
        },
    )

    insert_audit(
        table_name="extraction_entries",
        record_id=entry_id,
        action_type="create",
        changed_by=current_user(request),
        old_data="",
        new_data="extraction entry created",
    )

    return RedirectResponse("/stages", status_code=303)


# ------------------------
# FILTRATION
# ------------------------

@app.get("/stage/filtration", response_class=HTMLResponse)
def filtration_page(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "filtration.html",
        {
            "request": request,
            "user": current_user(request),
            "initials": current_initials(request),
            "run": get_run(current_run_id(request)),
            "today": datetime.now().strftime("%Y-%m-%d"),
        },
    )


@app.post("/submit/filtration")
async def submit_filtration(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    redirect = require_run(request)
    if redirect:
        return redirect

    form = await request.form()

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

    entry_id = insert_filtration(
        current_user(request),
        {
            "run_id": current_run_id(request),
            "operator_initials": (form.get("operator_initials") or current_initials(request)).strip().upper(),
            "entry_date": form.get("entry_date", ""),
            "clarification_sequential_no": form.get("clarification_sequential_no", ""),
            "retentate_flow_set_point": form.get("retentate_flow_set_point", ""),
            "zero_refract": form.get("zero_refract", ""),
            "startup_time": form.get("startup_time", ""),
            "shutdown_time": form.get("shutdown_time", ""),
            "start_time": form.get("start_time", ""),
            "stop_time": form.get("stop_time", ""),
            "comments": form.get("comments", ""),
            "photo_path": form.get("photo_path", ""),
            "rows": main_rows + dia_rows,
        },
    )

    insert_audit(
        table_name="filtration_entries",
        record_id=entry_id,
        action_type="create",
        changed_by=current_user(request),
        old_data="",
        new_data="filtration entry created",
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

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user(request),
            "rows": last_12_hour_activity(),
        },
    )