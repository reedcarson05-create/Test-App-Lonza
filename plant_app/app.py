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
    get_user,
    upsert_batch,
    get_batch,
    list_batches,
    insert_extraction,
    insert_filtration,
    insert_evaporation,
    recent_activity,
    batch_history,
    plant_status,
    close_batch,
)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="lonza-secret-key-change-me")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

init_db()


def logged_in(request: Request) -> bool:
    return bool(request.session.get("user"))


def current_user(request: Request) -> str:
    return request.session.get("user", "")


def current_initials(request: Request) -> str:
    return request.session.get("initials", "")


def current_batch_number(request: Request) -> str:
    return request.session.get("batch_number", "")


def initials_from_user(user_id: str, full_name: str = "") -> str:
    full_name = (full_name or "").strip()
    if full_name:
        words = []
        for part in full_name.replace("-", " ").split():
            letters = "".join(char for char in part if char.isalpha())
            if letters:
                words.append(letters)
        if len(words) >= 2:
            return "".join(word[0] for word in words[:3]).upper()
        if len(words) == 1:
            return words[0][:2].upper()
    user_id = (user_id or "").strip()
    return user_id[:2].upper() if user_id else ""


def set_notice(request: Request, message: str) -> None:
    request.session["notice"] = message


def pop_notice(request: Request) -> str:
    return request.session.pop("notice", "")


def require_login(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)
    return None


def require_batch(request: Request):
    if not current_batch_number(request):
        return RedirectResponse("/batch/select", status_code=303)
    return None


@app.get("/health", response_class=PlainTextResponse)
def health():
    return "OK"


@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    if logged_in(request):
        return RedirectResponse("/batch/select", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, employee: str = Form(...), password: str = Form(...)):
    employee = employee.strip()
    if validate_user(employee, password):
        user = get_user(employee)
        request.session["user"] = employee
        request.session["initials"] = initials_from_user(employee, user["full_name"] if user else "")
        return RedirectResponse("/batch/select", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid employee number or password."},
        status_code=400,
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/batch/select", response_class=HTMLResponse)
def batch_select_page(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "batch.html",
        {
            "request": request,
            "user": current_user(request),
            "current_batch": current_batch_number(request),
            "batches": list_batches(),
            "notice": pop_notice(request),
        },
    )


@app.post("/batch/select")
def batch_select(
    request: Request,
    batch_number: str = Form(...),
    product_name: str = Form(""),
    shift_name: str = Form(""),
    split_batch_number: str = Form(""),
    run_number: str = Form(""),
    blend_number: str = Form(""),
    notes: str = Form(""),
):
    redirect = require_login(request)
    if redirect:
        return redirect

    batch_number = batch_number.strip().upper()
    if not batch_number:
        return RedirectResponse("/batch/select", status_code=303)

    reused = upsert_batch(
        batch_number,
        product_name,
        shift_name,
        current_user(request),
        split_batch_number,
        run_number,
        blend_number,
        notes,
    )
    request.session["batch_number"] = batch_number
    if reused:
        set_notice(request, f"Reused existing batch number {batch_number}. Existing history remains available.")
    else:
        set_notice(request, f"Batch {batch_number} is active for batch-based stages.")
    return RedirectResponse("/stages", status_code=303)


@app.get("/batch/use/{batch_number}")
def use_existing_batch(request: Request, batch_number: str):
    redirect = require_login(request)
    if redirect:
        return redirect
    batch = get_batch(batch_number)
    if batch:
        request.session["batch_number"] = batch["batch_number"]
        set_notice(request, f"Batch {batch['batch_number']} loaded for batch-based stages.")
    return RedirectResponse("/stages", status_code=303)


@app.get("/batch/close/{batch_number}")
def close_existing_batch(request: Request, batch_number: str):
    redirect = require_login(request)
    if redirect:
        return redirect
    close_batch(batch_number)
    if current_batch_number(request) == batch_number:
        request.session.pop("batch_number", None)
    set_notice(request, f"Batch {batch_number} marked complete.")
    return RedirectResponse("/batch/select", status_code=303)


@app.get("/stages", response_class=HTMLResponse)
def stages(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect
    batch = get_batch(current_batch_number(request)) if current_batch_number(request) else None
    return templates.TemplateResponse(
        "stages.html",
        {
            "request": request,
            "user": current_user(request),
            "batch": batch,
            "notice": pop_notice(request),
        },
    )


@app.get("/stage/extraction", response_class=HTMLResponse)
def extraction_page(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "extraction.html",
        {
            "request": request,
            "user": current_user(request),
            "initials": current_initials(request),
            "batch": get_batch(current_batch_number(request))
            if current_batch_number(request)
            else None,
            "today": datetime.now().strftime("%Y-%m-%d"),
        },
    )


@app.post("/submit/extraction")
def submit_extraction(
    request: Request,
    operator_initials: str = Form(""),
    entry_date: str = Form(""),
    entry_time: str = Form(""),
    start_time: str = Form(""),
    stop_time: str = Form(""),
    location: str = Form("Pile"),
    time_on_pipe_or_pile: str = Form(""),
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
    notes: str = Form(""),
):
    redirect = require_login(request)
    if redirect:
        return redirect

    insert_extraction(
        current_user(request),
        {
            "batch_number": current_batch_number(request),
            "operator_initials": operator_initials.strip().upper()
            or current_initials(request),
            "entry_date": entry_date,
            "entry_time": entry_time,
            "start_time": start_time,
            "stop_time": stop_time,
            "location": location,
            "time_on_pipe_or_pile": time_on_pipe_or_pile,
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
            "notes": notes,
        },
    )
    set_notice(request, "Extraction entry saved. Ready for the next stage selection.")
    return RedirectResponse("/stages", status_code=303)


@app.get("/stage/filtration", response_class=HTMLResponse)
def filtration_page(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "filtration.html",
        {
            "request": request,
            "user": current_user(request),
            "initials": current_initials(request),
            "batch": get_batch(current_batch_number(request))
            if current_batch_number(request)
            else None,
            "today": datetime.now().strftime("%Y-%m-%d"),
        },
    )


@app.post("/submit/filtration")
def submit_filtration(
    request: Request,
    entry_date: str = Form(""),
    clarification_sequential_no: str = Form(""),
    retentate_flow_set_point: str = Form(""),
    zero_refract: str = Form(""),
    startup_time: str = Form(""),
    shutdown_time: str = Form(""),
    operator_initials: str = Form(""),
    row1_time: str = Form(""),
    row1_feed_ri: str = Form(""),
    row1_retentate_ri: str = Form(""),
    row1_permeate_ri: str = Form(""),
    row1_perm_flow_c: str = Form(""),
    row1_perm_flow_d: str = Form(""),
    row2_time: str = Form(""),
    row2_feed_ri: str = Form(""),
    row2_retentate_ri: str = Form(""),
    row2_permeate_ri: str = Form(""),
    row2_perm_flow_c: str = Form(""),
    row2_perm_flow_d: str = Form(""),
    row3_time: str = Form(""),
    row3_feed_ri: str = Form(""),
    row3_retentate_ri: str = Form(""),
    row3_permeate_ri: str = Form(""),
    row3_perm_flow_c: str = Form(""),
    row3_perm_flow_d: str = Form(""),
    dia_row1_time: str = Form(""),
    dia_row1_feed_ri: str = Form(""),
    dia_row1_retentate_ri: str = Form(""),
    dia_row1_permeate_ri: str = Form(""),
    dia_row2_time: str = Form(""),
    dia_row2_feed_ri: str = Form(""),
    dia_row2_retentate_ri: str = Form(""),
    dia_row2_permeate_ri: str = Form(""),
    notes: str = Form(""),
):
    redirect = require_login(request)
    if redirect:
        return redirect

    insert_filtration(
        current_user(request),
        {
            "batch_number": current_batch_number(request),
            "operator_initials": operator_initials.strip().upper()
            or current_initials(request),
            "entry_date": entry_date,
            "clarification_sequential_no": clarification_sequential_no,
            "retentate_flow_set_point": retentate_flow_set_point,
            "zero_refract": zero_refract,
            "startup_time": startup_time,
            "shutdown_time": shutdown_time,
            "row1_time": row1_time,
            "row1_feed_ri": row1_feed_ri,
            "row1_retentate_ri": row1_retentate_ri,
            "row1_permeate_ri": row1_permeate_ri,
            "row1_perm_flow_c": row1_perm_flow_c,
            "row1_perm_flow_d": row1_perm_flow_d,
            "row2_time": row2_time,
            "row2_feed_ri": row2_feed_ri,
            "row2_retentate_ri": row2_retentate_ri,
            "row2_permeate_ri": row2_permeate_ri,
            "row2_perm_flow_c": row2_perm_flow_c,
            "row2_perm_flow_d": row2_perm_flow_d,
            "row3_time": row3_time,
            "row3_feed_ri": row3_feed_ri,
            "row3_retentate_ri": row3_retentate_ri,
            "row3_permeate_ri": row3_permeate_ri,
            "row3_perm_flow_c": row3_perm_flow_c,
            "row3_perm_flow_d": row3_perm_flow_d,
            "dia_row1_time": dia_row1_time,
            "dia_row1_feed_ri": dia_row1_feed_ri,
            "dia_row1_retentate_ri": dia_row1_retentate_ri,
            "dia_row1_permeate_ri": dia_row1_permeate_ri,
            "dia_row2_time": dia_row2_time,
            "dia_row2_feed_ri": dia_row2_feed_ri,
            "dia_row2_retentate_ri": dia_row2_retentate_ri,
            "dia_row2_permeate_ri": dia_row2_permeate_ri,
            "notes": notes,
        },
    )
    set_notice(request, "Filtration entry saved. Ready for the next stage selection.")
    return RedirectResponse("/stages", status_code=303)


@app.get("/stage/evaporation", response_class=HTMLResponse)
def evaporation_page(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect
    redirect = require_batch(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "evaporation.html",
        {
            "request": request,
            "user": current_user(request),
            "initials": current_initials(request),
            "batch": get_batch(current_batch_number(request)),
            "today": datetime.now().strftime("%Y-%m-%d"),
        },
    )


@app.post("/submit/evaporation")
def submit_evaporation(
    request: Request,
    entry_date: str = Form(""),
    operator_initials: str = Form(""),
    evaporator_no: str = Form(""),
    startup_time: str = Form(""),
    shutdown_time: str = Form(""),
    feed_ri: str = Form(""),
    concentrate_ri: str = Form(""),
    steam_pressure: str = Form(""),
    vacuum: str = Form(""),
    sump_level: str = Form(""),
    product_temp: str = Form(""),
    row1_time: str = Form(""),
    row1_feed_rate: str = Form(""),
    row1_evap_temp: str = Form(""),
    row1_vacuum: str = Form(""),
    row1_concentrate_ri: str = Form(""),
    row2_time: str = Form(""),
    row2_feed_rate: str = Form(""),
    row2_evap_temp: str = Form(""),
    row2_vacuum: str = Form(""),
    row2_concentrate_ri: str = Form(""),
    row3_time: str = Form(""),
    row3_feed_rate: str = Form(""),
    row3_evap_temp: str = Form(""),
    row3_vacuum: str = Form(""),
    row3_concentrate_ri: str = Form(""),
    notes: str = Form(""),
):
    redirect = require_login(request)
    if redirect:
        return redirect
    redirect = require_batch(request)
    if redirect:
        return redirect

    insert_evaporation(
        current_user(request),
        {
            "batch_number": current_batch_number(request),
            "operator_initials": operator_initials.strip().upper()
            or current_initials(request),
            "entry_date": entry_date,
            "evaporator_no": evaporator_no,
            "startup_time": startup_time,
            "shutdown_time": shutdown_time,
            "feed_ri": feed_ri,
            "concentrate_ri": concentrate_ri,
            "steam_pressure": steam_pressure,
            "vacuum": vacuum,
            "sump_level": sump_level,
            "product_temp": product_temp,
            "row1_time": row1_time,
            "row1_feed_rate": row1_feed_rate,
            "row1_evap_temp": row1_evap_temp,
            "row1_vacuum": row1_vacuum,
            "row1_concentrate_ri": row1_concentrate_ri,
            "row2_time": row2_time,
            "row2_feed_rate": row2_feed_rate,
            "row2_evap_temp": row2_evap_temp,
            "row2_vacuum": row2_vacuum,
            "row2_concentrate_ri": row2_concentrate_ri,
            "row3_time": row3_time,
            "row3_feed_rate": row3_feed_rate,
            "row3_evap_temp": row3_evap_temp,
            "row3_vacuum": row3_vacuum,
            "row3_concentrate_ri": row3_concentrate_ri,
            "notes": notes,
        },
    )
    set_notice(request, "Evaporation entry saved. Ready for the next stage selection.")
    return RedirectResponse("/stages", status_code=303)


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
            "rows": recent_activity(hours=12),
            "batch": get_batch(current_batch_number(request))
            if current_batch_number(request)
            else None,
        },
    )


@app.get("/plant", response_class=HTMLResponse)
def plant(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "plant.html",
        {"request": request, "user": current_user(request), "rows": plant_status()},
    )


@app.get("/batch/{batch_number}", response_class=HTMLResponse)
def batch_detail(request: Request, batch_number: str):
    redirect = require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "batch_history.html",
        {
            "request": request,
            "user": current_user(request),
            "batch_number": batch_number,
            "rows": batch_history(batch_number),
        },
    )


@app.get("/success", response_class=HTMLResponse)
def success(request: Request, stage: str = ""):
    redirect = require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "success.html",
        {
            "request": request,
            "user": current_user(request),
            "stage": stage,
            "batch": get_batch(current_batch_number(request)),
        },
    )
