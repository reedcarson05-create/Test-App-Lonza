from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

from db import init_db, insert_entry, recent_batches, batch_entries, plant_status

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="change-this-secret-key")

BASE_DIR = Path(__file__).resolve().parent

# Serve CSS and static assets
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

machines = [
    {"MachineID": 1, "Name": "Extraction"},
    {"MachineID": 2, "Name": "Filtration"},
    {"MachineID": 3, "Name": "Evaporation"},
]



# Create the local DB if it doesn't exist
init_db()


def logged_in(request: Request) -> bool:
    return bool(request.session.get("user"))


@app.get("/health", response_class=PlainTextResponse)
def health():
    return "OK"


@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/login")
def login_get():
    return RedirectResponse("/", status_code=303)


@app.post("/login")
def login(request: Request, employee: str = Form(...), password: str = Form(...)):
    # MVP login: any non-empty credentials
    if employee.strip() and password.strip():
        request.session["user"] = employee.strip()
        return RedirectResponse("/machines", status_code=303)
    return RedirectResponse("/", status_code=303)


@app.get("/machines", response_class=HTMLResponse)
def machine_list(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        "machines.html",
        {"request": request, "machines": machines, "user": request.session.get("user")},
    )


@app.get("/entry/{machine_id}", response_class=HTMLResponse)
def entry_page(request: Request, machine_id: int):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    machine = next((m for m in machines if m["MachineID"] == machine_id), None)
    if machine is None:
        return HTMLResponse("Machine not found", status_code=404)

    return templates.TemplateResponse(
        "entry.html",
        {"request": request, "machine": machine, "user": request.session.get("user")},
    )


@app.post("/submit")
def submit(
    request: Request,
    machine_id: int = Form(...),
    batch_number: str = Form(...),
    blowback: str = Form(""),
    pressate_ri: str = Form(""),
    pressate_flow: str = Form(""),
    chip_bin_steam: str = Form(""),
    chip_chute_temp: str = Form(""),
):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    employee = request.session.get("user", "UNKNOWN")

    batch_number = batch_number.strip().upper().replace(" ", "")
    if not batch_number:
        return HTMLResponse("Batch number required", status_code=400)

    machine = next((m for m in machines if m["MachineID"] == machine_id), None)
    if machine is None:
        return HTMLResponse("Machine not found", status_code=404)

    insert_entry(
        employee=employee,
        batch_number=batch_number,
        machine_id=machine_id,
        machine_name=machine["Name"],
        blowback=blowback.strip(),
        pressate_ri=pressate_ri.strip(),
        pressate_flow=pressate_flow.strip(),
        chip_bin_steam=chip_bin_steam.strip(),
        chip_chute_temp=chip_chute_temp.strip(),
    )

    return RedirectResponse(f"/batch/{batch_number}", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    batches = recent_batches(limit=25)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "batches": batches, "user": request.session.get("user")},
    )


@app.get("/plant", response_class=HTMLResponse)
def plant(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    rows = plant_status()
    return templates.TemplateResponse(
        "plant.html",
        {"request": request, "rows": rows, "user": request.session.get("user")},
    )


@app.get("/batch/{batch_number}", response_class=HTMLResponse)
def batch_detail(request: Request, batch_number: str):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)

    b = batch_number.strip().upper().replace(" ", "")
    rows = batch_entries(b)
    return templates.TemplateResponse(
        "batch.html",
        {"request": request, "batch_number": b, "rows": rows, "user": request.session.get("user")},
    )


@app.get("/success", response_class=HTMLResponse)
def success(request: Request):
    if not logged_in(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("success.html", {"request": request, "user": request.session.get("user")})