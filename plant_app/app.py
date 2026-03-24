from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="change-this-secret-key-please")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Temporary in-memory storage
EXTRACTION_SUBMISSIONS: List[Dict[str, Any]] = []
FILTRATION_SUBMISSIONS: List[Dict[str, Any]] = []


def logged_in(request: Request) -> bool:
    return bool(request.session.get("user"))


def current_user(request: Request) -> str:
    return request.session.get("user", "")


def initials_from_user(user_id: str) -> str:
    user_id = (user_id or "").strip()
    if not user_id:
        return ""
    return user_id[:2].upper()


@app.get("/health", response_class=PlainTextResponse)
def health():
    return "OK"


@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    if logged_in(request):
        return RedirectResponse("/stages", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/login")
def login_get():
    return RedirectResponse("/", status_code=303)


@app.post("/login")
def login(request: Request, employee: str = Form(...), password: str = Form(...)):
    if employee.strip() and password.strip():
        request.session["user"] = employee.strip()
        request.session["initials"] = initials_from_user(employee.strip())
        return RedirectResponse("/stages", status_code=303)
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/stages", response_class=HTMLResponse)
def stages(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        "stages.html",
        {"request": request, "user": current_user(request)},
    )


@app.get("/stage/extraction", response_class=HTMLResponse)
def extraction_page(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        "extraction.html",
        {
            "request": request,
            "user": current_user(request),
            "initials": request.session.get("initials", ""),
        },
    )


@app.post("/submit/extraction")
def submit_extraction(
    request: Request,
    operator_initials: str = Form(""),
    entry_date: str = Form(""),
    entry_time: str = Form(""),
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
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    EXTRACTION_SUBMISSIONS.append(
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": current_user(request),
            "stage": "Extraction",
            "operator_initials": operator_initials.strip().upper(),
            "entry_date": entry_date.strip(),
            "entry_time": entry_time.strip(),
            "location": location.strip(),
            "time_on_pipe_or_pile": time_on_pipe_or_pile.strip(),
            "psf1_speed": psf1_speed.strip(),
            "psf1_load": psf1_load.strip(),
            "psf1_blowback": psf1_blowback.strip(),
            "psf2_speed": psf2_speed.strip(),
            "psf2_load": psf2_load.strip(),
            "psf2_blowback": psf2_blowback.strip(),
            "press_speed": press_speed.strip(),
            "press_load": press_load.strip(),
            "press_blowback": press_blowback.strip(),
            "pressate_ri": pressate_ri.strip(),
            "chip_bin_steam": chip_bin_steam.strip(),
            "chip_chute_temp": chip_chute_temp.strip(),
            "notes": notes.strip(),
        }
    )

    return RedirectResponse("/stages", status_code=303)


@app.get("/stage/filtration", response_class=HTMLResponse)
def filtration_page(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        "filtration.html",
        {
            "request": request,
            "user": current_user(request),
            "initials": request.session.get("initials", ""),
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
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    FILTRATION_SUBMISSIONS.append(
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": current_user(request),
            "stage": "Filtration",
            "entry_date": entry_date.strip(),
            "clarification_sequential_no": clarification_sequential_no.strip(),
            "retentate_flow_set_point": retentate_flow_set_point.strip(),
            "zero_refract": zero_refract.strip(),
            "startup_time": startup_time.strip(),
            "shutdown_time": shutdown_time.strip(),
            "operator_initials": operator_initials.strip().upper(),

            "row1_time": row1_time.strip(),
            "row1_feed_ri": row1_feed_ri.strip(),
            "row1_retentate_ri": row1_retentate_ri.strip(),
            "row1_permeate_ri": row1_permeate_ri.strip(),
            "row1_perm_flow_c": row1_perm_flow_c.strip(),
            "row1_perm_flow_d": row1_perm_flow_d.strip(),

            "row2_time": row2_time.strip(),
            "row2_feed_ri": row2_feed_ri.strip(),
            "row2_retentate_ri": row2_retentate_ri.strip(),
            "row2_permeate_ri": row2_permeate_ri.strip(),
            "row2_perm_flow_c": row2_perm_flow_c.strip(),
            "row2_perm_flow_d": row2_perm_flow_d.strip(),

            "row3_time": row3_time.strip(),
            "row3_feed_ri": row3_feed_ri.strip(),
            "row3_retentate_ri": row3_retentate_ri.strip(),
            "row3_permeate_ri": row3_permeate_ri.strip(),
            "row3_perm_flow_c": row3_perm_flow_c.strip(),
            "row3_perm_flow_d": row3_perm_flow_d.strip(),

            "dia_row1_time": dia_row1_time.strip(),
            "dia_row1_feed_ri": dia_row1_feed_ri.strip(),
            "dia_row1_retentate_ri": dia_row1_retentate_ri.strip(),
            "dia_row1_permeate_ri": dia_row1_permeate_ri.strip(),

            "dia_row2_time": dia_row2_time.strip(),
            "dia_row2_feed_ri": dia_row2_feed_ri.strip(),
            "dia_row2_retentate_ri": dia_row2_retentate_ri.strip(),
            "dia_row2_permeate_ri": dia_row2_permeate_ri.strip(),

            "notes": notes.strip(),
        }
    )

    return RedirectResponse("/stages", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    rows = list(reversed((EXTRACTION_SUBMISSIONS + FILTRATION_SUBMISSIONS)[-30:]))

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": current_user(request), "rows": rows},
    )


@app.get("/stage/evaporation", response_class=HTMLResponse)
def evaporation_stub(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(
        "<h2 style='font-family:Arial;padding:20px;'>Evaporation page coming next.</h2><p style='font-family:Arial;padding:0 20px;'><a href='/stages'>Back to Stages</a></p>"
    )
