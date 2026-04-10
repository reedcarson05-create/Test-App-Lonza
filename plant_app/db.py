"""SQL Server persistence helpers for authentication, runs, stage entries, and audit history."""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pyodbc

DEFAULT_SQL_DRIVER = "ODBC Driver 18 for SQL Server"
DEFAULT_SQL_SERVER = r"localhost\SQLEXPRESS"
PREFERRED_SQL_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 13 for SQL Server",
    "ODBC Driver 11 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
)
PREFERRED_SQL_DATABASE = "LAGPlantOpsApp"
FALLBACK_SQL_DATABASE = "PlantOpsApp"
SQLITE_FALLBACK_PATH = Path(__file__).resolve().parent / "plant.db"
_resolved_sql_database: str | None = None
_active_backend: str | None = None


def _env_text(name: str, default: str = "") -> str:
    """Return a trimmed environment value, falling back when missing or blank."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    trimmed = raw_value.strip()
    return trimmed if trimmed else default


def _env_bool(name: str, default: bool) -> bool:
    """Parse a common yes/no style environment flag safely."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _yes_no(value: bool) -> str:
    """Convert a boolean into the yes/no string SQL Server expects."""
    return "yes" if value else "no"


def _resolved_sql_driver() -> str:
    """Pick an installed SQL Server ODBC driver, unless one is explicitly configured."""
    configured_driver = _env_text("PLANT_APP_SQL_DRIVER")
    if configured_driver:
        return configured_driver.strip("{}")

    installed_drivers = {driver.strip(): driver.strip() for driver in pyodbc.drivers() if driver.strip()}
    for driver_name in PREFERRED_SQL_DRIVERS:
        if driver_name in installed_drivers:
            return installed_drivers[driver_name]

    return DEFAULT_SQL_DRIVER


def _default_encrypt_enabled(driver: str) -> bool:
    """Keep secure defaults for modern drivers and broad compatibility for legacy ones."""
    return driver != "SQL Server"


def _supports_secure_connection_flags(driver: str) -> bool:
    """Return True when the selected driver supports Encrypt/TrustServerCertificate flags."""
    return driver != "SQL Server"


def _requested_backend() -> str:
    """Return the preferred backend mode: auto, sqlserver, or sqlite."""
    requested = _env_text("PLANT_APP_DB_BACKEND", "auto").lower()
    if requested in {"sqlite", "sqlite3"}:
        return "sqlite"
    if requested in {"sql", "sqlserver", "mssql"}:
        return "sqlserver"
    return "auto"


def _sql_configuration_present() -> bool:
    """Return True when the environment explicitly points at a shared SQL Server."""
    relevant_names = (
        "PLANT_APP_SQL_CONNECTION_STRING",
        "PLANT_APP_SQL_SERVER",
        "PLANT_APP_SQL_PORT",
        "PLANT_APP_SQL_DATABASE",
        "PLANT_APP_SQL_USER",
        "PLANT_APP_SQL_PASSWORD",
        "PLANT_APP_SQL_DRIVER",
        "PLANT_APP_SQL_TRUSTED_CONNECTION",
    )
    return any(os.getenv(name) not in {None, ""} for name in relevant_names)


def _sqlite_available() -> bool:
    """Return True when the bundled local SQLite fallback database exists."""
    return SQLITE_FALLBACK_PATH.exists()


def _open_sqlite_conn():
    """Open the bundled SQLite fallback used when shared SQL is unavailable."""
    conn = sqlite3.connect(SQLITE_FALLBACK_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _is_sqlite_connection(conn) -> bool:
    """Return True when the supplied DB-API connection is SQLite."""
    return isinstance(conn, sqlite3.Connection)


def _limit_clause(limit: int, sqlite_backend: bool) -> str:
    """Return the backend-specific row-limit clause fragment."""
    safe_limit = max(1, int(limit))
    return f"LIMIT {safe_limit}" if sqlite_backend else f"TOP ({safe_limit})"


def _connect_sql_server():
    """Open the configured SQL Server database."""
    return pyodbc.connect(_connection_string(resolve_sql_database()))


def _sql_server_target() -> str:
    """Return the configured SQL Server host or host:port target."""
    server = _env_text("PLANT_APP_SQL_SERVER", DEFAULT_SQL_SERVER)
    port = _env_text("PLANT_APP_SQL_PORT")

    if port and "\\" not in server and "," not in server:
        prefix = "" if server.lower().startswith("tcp:") else "tcp:"
        return f"{prefix}{server},{port}"

    return server


def _with_database(connection_string: str, database: str) -> str:
    """Inject the target database into a caller-supplied connection string."""
    parts: list[str] = []
    for segment in connection_string.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        key = segment.split("=", 1)[0].strip().lower()
        if key in {"database", "initial catalog"}:
            continue
        parts.append(segment)

    parts.append(f"DATABASE={database}")
    return ";".join(parts) + ";"


def build_sql_connection_string(database: str) -> str:
    """Build a SQL Server connection string for local or shared multi-device access."""
    override = _env_text("PLANT_APP_SQL_CONNECTION_STRING")
    if override:
        return _with_database(override, database)

    driver = _resolved_sql_driver()
    username = os.getenv("PLANT_APP_SQL_USER", "").strip()
    password = os.getenv("PLANT_APP_SQL_PASSWORD", "")
    timeout = _env_text("PLANT_APP_SQL_TIMEOUT", "5")
    encrypt_enabled = _env_bool("PLANT_APP_SQL_ENCRYPT", _default_encrypt_enabled(driver))
    trust_server_certificate = _env_bool("PLANT_APP_SQL_TRUST_SERVER_CERTIFICATE", encrypt_enabled)

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={_sql_server_target()}",
        f"DATABASE={database}",
    ]

    if username:
        # Shared SQL credentials let every signed-in device write to one central server.
        parts.extend([f"UID={username}", f"PWD={password}"])
    else:
        parts.append(
            f"Trusted_Connection={_yes_no(_env_bool('PLANT_APP_SQL_TRUSTED_CONNECTION', True))}"
        )

    if _supports_secure_connection_flags(driver):
        parts.extend(
            [
                f"Encrypt={_yes_no(encrypt_enabled)}",
                f"TrustServerCertificate={_yes_no(trust_server_certificate)}",
            ]
        )

    if timeout:
        parts.append(f"Connection Timeout={timeout}")

    return ";".join(parts) + ";"


def _connection_string(database: str) -> str:
    """Backwards-compatible wrapper around the shared SQL connection builder."""
    return build_sql_connection_string(database)


def resolve_sql_database() -> str:
    """Pick an explicit, preferred, or discovered Plant App database name."""
    global _resolved_sql_database

    explicit_database = os.getenv("PLANT_APP_SQL_DATABASE", "").strip()
    if explicit_database:
        return explicit_database

    if _resolved_sql_database:
        return _resolved_sql_database

    try:
        conn = pyodbc.connect(_connection_string("master"))
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT TOP (1) name
                FROM sys.databases
                WHERE name IN (?, ?) OR name LIKE ?
                ORDER BY CASE
                    WHEN name = ? THEN 0
                    WHEN name = ? THEN 1
                    ELSE 2
                END, name
                """,
                (
                    PREFERRED_SQL_DATABASE,
                    FALLBACK_SQL_DATABASE,
                    "%PlantOpsApp",
                    PREFERRED_SQL_DATABASE,
                    FALLBACK_SQL_DATABASE,
                ),
            )
            row = cur.fetchone()
        finally:
            conn.close()
    except pyodbc.Error:
        row = None

    if row and row[0]:
        _resolved_sql_database = str(row[0])
        return _resolved_sql_database

    _resolved_sql_database = PREFERRED_SQL_DATABASE
    return _resolved_sql_database


def get_conn():
    """Open the active application database, preferring SQL Server with SQLite fallback."""
    global _active_backend

    requested_backend = _requested_backend()
    if requested_backend == "sqlite":
        _active_backend = "sqlite"
        return _open_sqlite_conn()

    try:
        conn = _connect_sql_server()
        _active_backend = "sqlserver"
        return conn
    except pyodbc.Error:
        if requested_backend == "sqlserver" or not _sqlite_available():
            raise
        _active_backend = "sqlite"
        return _open_sqlite_conn()


def now_stamp() -> str:
    """Return a consistent timestamp string for inserts, updates, and audit rows."""
    return datetime.now().isoformat(timespec="seconds")


def row_to_dict(columns: list[str], row) -> dict | None:
    """Convert a pyodbc row into a plain dictionary."""
    if row is None:
        return None
    return dict(zip(columns, row))


def rows_to_dicts(columns: list[str], rows) -> list[dict]:
    """Convert a list of database rows into plain dictionaries."""
    return [row_to_dict(columns, row) for row in rows]


def init_db() -> None:
    """Validate that the configured database backend is reachable."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1")
    conn.close()


def validate_user(employee: str, password: str) -> bool:
    """Return True when the supplied employee credentials match an active user."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT 1
        FROM users
        WHERE employee_number = ? AND password = ? AND active = 1
    """, (employee.strip(), password.strip()))
    row = cur.fetchone()
    conn.close()
    return row is not None


def get_user_initials(employee: str) -> str:
    """Return the stored initials for a user, or derive a fallback from the employee id."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT initials FROM users WHERE employee_number = ?", (employee.strip(),))
    columns = [col[0] for col in cur.description]
    row = row_to_dict(columns, cur.fetchone())
    conn.close()
    if row and row["initials"]:
        return row["initials"]
    return (employee[:2] if employee else "").upper()


def get_user_preferences(employee: str) -> dict[str, str]:
    """Return the saved display settings for a user, falling back to app defaults."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT theme_preference, font_scale_preference
        FROM users
        WHERE employee_number = ?
    """, (employee.strip(),))
    columns = [col[0] for col in cur.description]
    row = row_to_dict(columns, cur.fetchone())
    conn.close()
    if not row:
        return {"theme": "light", "font_scale": "1"}
    return {
        "theme": row["theme_preference"] or "light",
        "font_scale": row["font_scale_preference"] or "1",
    }


def update_user_preferences(employee: str, theme: str, font_scale: str) -> dict[str, str]:
    """Persist validated display settings for a user and return the saved values."""
    safe_theme = theme if theme in {"light", "dark"} else "light"
    safe_font_scale = font_scale if font_scale in {"1", "1.15", "1.3"} else "1"

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET theme_preference = ?, font_scale_preference = ?
        WHERE employee_number = ?
    """, (safe_theme, safe_font_scale, employee.strip()))
    conn.commit()
    conn.close()
    return {"theme": safe_theme, "font_scale": safe_font_scale}


def create_run(
    batch_number: str,
    split_batch_number: str,
    blend_number: str,
    run_number: str,
    batch_type: str,
    reused_batch: int,
    product_name: str,
    shift_name: str,
    operator_id: str,
    notes: str,
) -> int:
    """Insert a new production run and return its generated id."""
    normalized_run_number = run_number.strip() or batch_number.strip()
    normalized_batch_number = batch_number.strip() or normalized_run_number

    conn = get_conn()
    cur = conn.cursor()
    sqlite_backend = _is_sqlite_connection(conn)
    # One shared timestamp is used for both created/updated values on the first insert.
    stamp = now_stamp()
    params = (
        normalized_batch_number,
        split_batch_number.strip(),
        blend_number.strip(),
        normalized_run_number,
        batch_type.strip() or "standard",
        int(reused_batch),
        product_name.strip(),
        shift_name.strip(),
        operator_id.strip(),
        notes.strip(),
        stamp,
        stamp,
    )
    if sqlite_backend:
        cur.execute("""
            INSERT INTO production_runs (
                batch_number, split_batch_number, blend_number, run_number, batch_type,
                reused_batch, product_name, shift_name, operator_id, notes, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?)
        """, params)
        run_id = int(cur.lastrowid)
    else:
        cur.execute("""
            INSERT INTO production_runs (
                batch_number, split_batch_number, blend_number, run_number, batch_type,
                reused_batch, product_name, shift_name, operator_id, notes, status,
                created_at, updated_at
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?)
        """, params)
        run_id = int(cur.fetchone()[0])
    conn.commit()
    conn.close()
    return run_id


def get_run(run_id: int):
    """Fetch a single production run by id."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM production_runs WHERE id = ?", (run_id,))
    columns = [col[0] for col in cur.description]
    row = row_to_dict(columns, cur.fetchone())
    conn.close()
    return row


def list_runs(limit: int = 50):
    """Return the most recently updated production runs for the selection screen."""
    conn = get_conn()
    cur = conn.cursor()
    sqlite_backend = _is_sqlite_connection(conn)
    safe_limit = max(1, int(limit))
    if sqlite_backend:
        cur.execute(f"""
            SELECT *
            FROM production_runs
            ORDER BY updated_at DESC
            LIMIT {safe_limit}
        """)
    else:
        cur.execute(f"""
            SELECT TOP ({safe_limit}) *
            FROM production_runs
            ORDER BY updated_at DESC
        """)
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows


def list_open_runs(limit: int = 100):
    """Return currently open runs ordered by the most recent activity."""
    conn = get_conn()
    cur = conn.cursor()
    sqlite_backend = _is_sqlite_connection(conn)
    safe_limit = max(1, int(limit))
    if sqlite_backend:
        cur.execute(f"""
            SELECT *
            FROM production_runs
            WHERE status = 'Open'
            ORDER BY updated_at DESC
            LIMIT {safe_limit}
        """)
    else:
        cur.execute(f"""
            SELECT TOP ({safe_limit}) *
            FROM production_runs
            WHERE status = 'Open'
            ORDER BY updated_at DESC
        """)
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows


def get_runs_by_ids(run_ids: list[int]):
    """Return multiple runs in one query while preserving a stable updated-time sort."""
    normalized_ids = [int(run_id) for run_id in run_ids if int(run_id) > 0]
    if not normalized_ids:
        return []

    placeholders = ", ".join("?" for _ in normalized_ids)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT *
        FROM production_runs
        WHERE id IN ({placeholders})
        ORDER BY updated_at DESC
    """, normalized_ids)
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows


def mark_run_complete(run_id: int, employee: str = ""):
    """Finalize a production run and stamp who closed it out."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE production_runs
        SET status = 'Complete', finalized_at = ?, finalized_by = ?, updated_at = ?
        WHERE id = ?
    """, (now_stamp(), employee.strip(), now_stamp(), run_id))
    conn.commit()
    conn.close()


def apply_run_group_action(run_ids: list[int], action_type: str, action_label: str):
    """Stamp the selected runs with a shared blend or split label."""
    normalized_ids = [int(run_id) for run_id in run_ids if int(run_id) > 0]
    if not normalized_ids:
        return 0

    if action_type == "blend":
        action_sql = "blend_number = ?, split_batch_number = '', batch_type = 'blend'"
    elif action_type == "split":
        action_sql = "split_batch_number = ?, blend_number = '', batch_type = 'split'"
    else:
        raise ValueError(f"Unsupported run action: {action_type}")

    placeholders = ", ".join("?" for _ in normalized_ids)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE production_runs
        SET {action_sql},
            updated_at = ?
        WHERE id IN ({placeholders})
        """,
        [action_label, now_stamp(), *normalized_ids],
    )
    affected_rows = cur.rowcount
    conn.commit()
    conn.close()
    return affected_rows


def touch_run(run_id: int):
    """Refresh a run's updated timestamp after a related sheet changes."""
    if not run_id:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE production_runs SET updated_at = ? WHERE id = ?", (now_stamp(), run_id))
    conn.commit()
    conn.close()


def insert_extraction(employee: str, data: dict) -> int:
    """Insert a new extraction entry and return its id."""
    conn = get_conn()
    cur = conn.cursor()
    sqlite_backend = _is_sqlite_connection(conn)
    params = (
        data["run_id"],
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("entry_time", ""),
        data.get("location", "Pile"),
        data.get("time_on_pile", ""),
        data.get("start_time", ""),
        data.get("stop_time", ""),
        data.get("psf1_speed", ""),
        data.get("psf1_load", ""),
        data.get("psf1_blowback", ""),
        data.get("psf2_speed", ""),
        data.get("psf2_load", ""),
        data.get("psf2_blowback", ""),
        data.get("press_speed", ""),
        data.get("press_load", ""),
        data.get("press_blowback", ""),
        data.get("pressate_ri", ""),
        data.get("chip_bin_steam", ""),
        data.get("chip_chute_temp", ""),
        data.get("comments", ""),
        data.get("photo_path", ""),
        data.get("version_no", 1),
        data.get("previous_entry_id"),
        now_stamp(),
    )
    if sqlite_backend:
        cur.execute("""
            INSERT INTO extraction_entries (
                run_id, employee, operator_initials, entry_date, entry_time, location,
                time_on_pile, start_time, stop_time,
                psf1_speed, psf1_load, psf1_blowback,
                psf2_speed, psf2_load, psf2_blowback,
                press_speed, press_load, press_blowback,
                pressate_ri, chip_bin_steam, chip_chute_temp,
                comments, photo_path, version_no, previous_entry_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, params)
        entry_id = int(cur.lastrowid)
    else:
        cur.execute("""
            INSERT INTO extraction_entries (
                run_id, employee, operator_initials, entry_date, entry_time, location,
                time_on_pile, start_time, stop_time,
                psf1_speed, psf1_load, psf1_blowback,
                psf2_speed, psf2_load, psf2_blowback,
                press_speed, press_load, press_blowback,
                pressate_ri, chip_bin_steam, chip_chute_temp,
                comments, photo_path, version_no, previous_entry_id, created_at
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, params)
        entry_id = int(cur.fetchone()[0])
    conn.commit()
    conn.close()
    touch_run(data["run_id"])
    return entry_id


def insert_filtration(employee: str, data: dict) -> int:
    """Insert a new filtration entry plus its repeating child rows."""
    conn = get_conn()
    cur = conn.cursor()
    sqlite_backend = _is_sqlite_connection(conn)
    params = (
        data["run_id"],
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("clarification_sequential_no", ""),
        data.get("retentate_flow_set_point", ""),
        data.get("zero_refract", ""),
        data.get("startup_time", ""),
        data.get("shutdown_time", ""),
        data.get("start_time", ""),
        data.get("stop_time", ""),
        data.get("comments", ""),
        data.get("photo_path", ""),
        data.get("version_no", 1),
        data.get("previous_entry_id"),
        now_stamp(),
    )
    if sqlite_backend:
        cur.execute("""
            INSERT INTO filtration_entries (
                run_id, employee, operator_initials, entry_date,
                clarification_sequential_no, retentate_flow_set_point, zero_refract,
                startup_time, shutdown_time, start_time, stop_time,
                comments, photo_path, version_no, previous_entry_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, params)
        entry_id = int(cur.lastrowid)
    else:
        cur.execute("""
            INSERT INTO filtration_entries (
                run_id, employee, operator_initials, entry_date,
                clarification_sequential_no, retentate_flow_set_point, zero_refract,
                startup_time, shutdown_time, start_time, stop_time,
                comments, photo_path, version_no, previous_entry_id, created_at
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, params)
        entry_id = int(cur.fetchone()[0])

    # Child rows are inserted after the parent so they can reference the generated parent id.
    for row in data.get("rows", []):
        cur.execute("""
            INSERT INTO filtration_rows (
                filtration_entry_id, row_group, row_no, row_time,
                feed_ri, retentate_ri, permeate_ri, perm_flow_c, perm_flow_d
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id,
            row.get("row_group", "main"),
            row.get("row_no", 1),
            row.get("row_time", ""),
            row.get("feed_ri", ""),
            row.get("retentate_ri", ""),
            row.get("permeate_ri", ""),
            row.get("perm_flow_c", ""),
            row.get("perm_flow_d", ""),
        ))

    conn.commit()
    conn.close()
    touch_run(data["run_id"])
    return entry_id


def insert_evaporation(employee: str, data: dict) -> int:
    """Insert a new evaporation entry plus its repeating child rows."""
    conn = get_conn()
    cur = conn.cursor()
    sqlite_backend = _is_sqlite_connection(conn)
    params = (
        data["run_id"],
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("evaporator_no", ""),
        data.get("startup_time", ""),
        data.get("shutdown_time", ""),
        data.get("feed_ri", ""),
        data.get("concentrate_ri", ""),
        data.get("steam_pressure", ""),
        data.get("vacuum", ""),
        data.get("sump_level", ""),
        data.get("product_temp", ""),
        data.get("comments", ""),
        data.get("photo_path", ""),
        data.get("version_no", 1),
        data.get("previous_entry_id"),
        now_stamp(),
    )
    if sqlite_backend:
        cur.execute("""
            INSERT INTO evaporation_entries (
                run_id, employee, operator_initials, entry_date, evaporator_no,
                startup_time, shutdown_time, feed_ri, concentrate_ri, steam_pressure,
                vacuum, sump_level, product_temp, comments, photo_path,
                version_no, previous_entry_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, params)
        entry_id = int(cur.lastrowid)
    else:
        cur.execute("""
            INSERT INTO evaporation_entries (
                run_id, employee, operator_initials, entry_date, evaporator_no,
                startup_time, shutdown_time, feed_ri, concentrate_ri, steam_pressure,
                vacuum, sump_level, product_temp, comments, photo_path,
                version_no, previous_entry_id, created_at
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, params)
        entry_id = int(cur.fetchone()[0])

    # Child rows are inserted after the parent so they can reference the generated parent id.
    for row in data.get("rows", []):
        cur.execute("""
            INSERT INTO evaporation_rows (
                evaporation_entry_id, row_no, row_time, feed_rate,
                evap_temp, row_vacuum, row_concentrate_ri
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id,
            row.get("row_no", 1),
            row.get("row_time", ""),
            row.get("feed_rate", ""),
            row.get("evap_temp", ""),
            row.get("row_vacuum", ""),
            row.get("row_concentrate_ri", ""),
        ))

    conn.commit()
    conn.close()
    touch_run(data["run_id"])
    return entry_id


def update_run(
    run_id: int,
    batch_number: str,
    split_batch_number: str,
    blend_number: str,
    run_number: str,
    batch_type: str,
    reused_batch: int,
    product_name: str,
    shift_name: str,
    notes: str,
    final_edit_initials: str,
    final_edit_notes: str,
) -> None:
    """Persist edits to the run header and final review metadata."""
    normalized_run_number = run_number.strip() or batch_number.strip()
    normalized_batch_number = batch_number.strip() or normalized_run_number

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE production_runs
        SET batch_number = ?,
            split_batch_number = ?,
            blend_number = ?,
            run_number = ?,
            batch_type = ?,
            reused_batch = ?,
            product_name = ?,
            shift_name = ?,
            notes = ?,
            final_edit_initials = ?,
            final_edit_notes = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        normalized_batch_number,
        split_batch_number.strip(),
        blend_number.strip(),
        normalized_run_number,
        batch_type.strip() or "standard",
        int(reused_batch),
        product_name.strip(),
        shift_name.strip(),
        notes.strip(),
        final_edit_initials.strip().upper(),
        final_edit_notes.strip(),
        now_stamp(),
        run_id,
    ))
    conn.commit()
    conn.close()


def get_extraction_entry(entry_id: int):
    """Fetch a saved extraction entry for correction or display."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM extraction_entries WHERE id = ?", (entry_id,))
    columns = [col[0] for col in cur.description]
    row = row_to_dict(columns, cur.fetchone())
    conn.close()
    return row


def update_extraction(entry_id: int, employee: str, data: dict) -> None:
    """Update an existing extraction entry and increment its version number."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE extraction_entries
        SET employee = ?, operator_initials = ?, entry_date = ?, entry_time = ?, location = ?,
            time_on_pile = ?, start_time = ?, stop_time = ?, psf1_speed = ?, psf1_load = ?,
            psf1_blowback = ?, psf2_speed = ?, psf2_load = ?, psf2_blowback = ?,
            press_speed = ?, press_load = ?, press_blowback = ?, pressate_ri = ?,
            chip_bin_steam = ?, chip_chute_temp = ?, comments = ?, photo_path = ?,
            version_no = COALESCE(version_no, 1) + 1
        WHERE id = ?
    """, (
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("entry_time", ""),
        data.get("location", "Pile"),
        data.get("time_on_pile", ""),
        data.get("start_time", ""),
        data.get("stop_time", ""),
        data.get("psf1_speed", ""),
        data.get("psf1_load", ""),
        data.get("psf1_blowback", ""),
        data.get("psf2_speed", ""),
        data.get("psf2_load", ""),
        data.get("psf2_blowback", ""),
        data.get("press_speed", ""),
        data.get("press_load", ""),
        data.get("press_blowback", ""),
        data.get("pressate_ri", ""),
        data.get("chip_bin_steam", ""),
        data.get("chip_chute_temp", ""),
        data.get("comments", ""),
        data.get("photo_path", ""),
        entry_id,
    ))
    conn.commit()
    conn.close()


def get_filtration_entry(entry_id: int):
    """Fetch a saved filtration entry together with its ordered child rows."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM filtration_entries WHERE id = ?", (entry_id,))
    entry_columns = [col[0] for col in cur.description]
    entry = row_to_dict(entry_columns, cur.fetchone())
    cur.execute("""
        SELECT * FROM filtration_rows
        WHERE filtration_entry_id = ?
        ORDER BY row_group, row_no
    """, (entry_id,))
    row_columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(row_columns, cur.fetchall())
    conn.close()
    return entry, rows


def update_filtration(entry_id: int, employee: str, data: dict) -> None:
    """Replace an existing filtration entry and its child rows with corrected values."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE filtration_entries
        SET employee = ?, operator_initials = ?, entry_date = ?, clarification_sequential_no = ?,
            retentate_flow_set_point = ?, zero_refract = ?, startup_time = ?, shutdown_time = ?,
            start_time = ?, stop_time = ?, comments = ?, photo_path = ?,
            version_no = COALESCE(version_no, 1) + 1
        WHERE id = ?
    """, (
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("clarification_sequential_no", ""),
        data.get("retentate_flow_set_point", ""),
        data.get("zero_refract", ""),
        data.get("startup_time", ""),
        data.get("shutdown_time", ""),
        data.get("start_time", ""),
        data.get("stop_time", ""),
        data.get("comments", ""),
        data.get("photo_path", ""),
        entry_id,
    ))
    # Rebuild the child rows from the submitted form so the saved set always matches the current screen.
    cur.execute("DELETE FROM filtration_rows WHERE filtration_entry_id = ?", (entry_id,))
    for row in data.get("rows", []):
        cur.execute("""
            INSERT INTO filtration_rows (
                filtration_entry_id, row_group, row_no, row_time,
                feed_ri, retentate_ri, permeate_ri, perm_flow_c, perm_flow_d
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id,
            row.get("row_group", "main"),
            row.get("row_no", 1),
            row.get("row_time", ""),
            row.get("feed_ri", ""),
            row.get("retentate_ri", ""),
            row.get("permeate_ri", ""),
            row.get("perm_flow_c", ""),
            row.get("perm_flow_d", ""),
        ))
    conn.commit()
    conn.close()


def get_evaporation_entry(entry_id: int):
    """Fetch a saved evaporation entry together with its ordered child rows."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM evaporation_entries WHERE id = ?", (entry_id,))
    entry_columns = [col[0] for col in cur.description]
    entry = row_to_dict(entry_columns, cur.fetchone())
    cur.execute("""
        SELECT * FROM evaporation_rows
        WHERE evaporation_entry_id = ?
        ORDER BY row_no
    """, (entry_id,))
    row_columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(row_columns, cur.fetchall())
    conn.close()
    return entry, rows


def get_latest_evaporation_for_run(run_id: int):
    """Fetch the latest evaporation entry recorded for a specific run."""
    conn = get_conn()
    cur = conn.cursor()
    if _is_sqlite_connection(conn):
        cur.execute("""
            SELECT * FROM evaporation_entries
            WHERE run_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (run_id,))
    else:
        cur.execute("""
            SELECT TOP 1 * FROM evaporation_entries
            WHERE run_id = ?
            ORDER BY id DESC
        """, (run_id,))
    entry_columns = [col[0] for col in cur.description]
    entry = row_to_dict(entry_columns, cur.fetchone())
    rows = []
    if entry:
        cur.execute("""
            SELECT * FROM evaporation_rows
            WHERE evaporation_entry_id = ?
            ORDER BY row_no
        """, (entry["id"],))
        row_columns = [col[0] for col in cur.description]
        rows = rows_to_dicts(row_columns, cur.fetchall())
    conn.close()
    return entry, rows


def update_evaporation(entry_id: int, employee: str, data: dict) -> None:
    """Replace an existing evaporation entry and its child rows with corrected values."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE evaporation_entries
        SET employee = ?, operator_initials = ?, entry_date = ?, evaporator_no = ?,
            startup_time = ?, shutdown_time = ?, feed_ri = ?, concentrate_ri = ?,
            steam_pressure = ?, vacuum = ?, sump_level = ?, product_temp = ?,
            comments = ?, photo_path = ?, version_no = COALESCE(version_no, 1) + 1
        WHERE id = ?
    """, (
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("evaporator_no", ""),
        data.get("startup_time", ""),
        data.get("shutdown_time", ""),
        data.get("feed_ri", ""),
        data.get("concentrate_ri", ""),
        data.get("steam_pressure", ""),
        data.get("vacuum", ""),
        data.get("sump_level", ""),
        data.get("product_temp", ""),
        data.get("comments", ""),
        data.get("photo_path", ""),
        entry_id,
    ))
    # Rebuild the child rows from the submitted form so the saved set always matches the current screen.
    cur.execute("DELETE FROM evaporation_rows WHERE evaporation_entry_id = ?", (entry_id,))
    for row in data.get("rows", []):
        cur.execute("""
            INSERT INTO evaporation_rows (
                evaporation_entry_id, row_no, row_time, feed_rate,
                evap_temp, row_vacuum, row_concentrate_ri
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id,
            row.get("row_no", 1),
            row.get("row_time", ""),
            row.get("feed_rate", ""),
            row.get("evap_temp", ""),
            row.get("row_vacuum", ""),
            row.get("row_concentrate_ri", ""),
        ))
    conn.commit()
    conn.close()


def get_sheet_entry(entry_id: int):
    """Fetch a saved generic stage sheet by id."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sheet_entries WHERE id = ?", (entry_id,))
    columns = [col[0] for col in cur.description]
    row = row_to_dict(columns, cur.fetchone())
    conn.close()
    return row


def get_latest_sheet_entry_for_run_stage(run_id: int, stage_key: str):
    """Fetch the most recent generic stage entry for a run/stage combination."""
    conn = get_conn()
    cur = conn.cursor()
    if _is_sqlite_connection(conn):
        cur.execute("""
            SELECT * FROM sheet_entries
            WHERE run_id = ? AND stage_key = ?
            ORDER BY id DESC
            LIMIT 1
        """, (run_id, stage_key))
    else:
        cur.execute("""
            SELECT TOP 1 * FROM sheet_entries
            WHERE run_id = ? AND stage_key = ?
            ORDER BY id DESC
        """, (run_id, stage_key))
    columns = [col[0] for col in cur.description]
    row = row_to_dict(columns, cur.fetchone())
    conn.close()
    return row


def update_sheet_entry(entry_id: int, employee: str, data: dict) -> None:
    """Update a generic stage sheet and increment its version number."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE sheet_entries
        SET employee = ?, operator_initials = ?, entry_date = ?, comments = ?,
            payload_json = ?, version_no = COALESCE(version_no, 1) + 1
        WHERE id = ?
    """, (
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("comments", ""),
        data.get("payload_json", "{}"),
        entry_id,
    ))
    conn.commit()
    conn.close()


def insert_sheet_entry(employee: str, data: dict) -> int:
    """Insert a new generic stage sheet and return its id."""
    conn = get_conn()
    cur = conn.cursor()
    sqlite_backend = _is_sqlite_connection(conn)
    params = (
        data["run_id"],
        data["stage_key"],
        data["stage_title"],
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("comments", ""),
        data.get("payload_json", "{}"),
        data.get("version_no", 1),
        data.get("previous_entry_id"),
        now_stamp(),
    )
    if sqlite_backend:
        cur.execute("""
            INSERT INTO sheet_entries (
                run_id, stage_key, stage_title, employee, operator_initials,
                entry_date, comments, payload_json, version_no, previous_entry_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, params)
        entry_id = int(cur.lastrowid)
    else:
        cur.execute("""
            INSERT INTO sheet_entries (
                run_id, stage_key, stage_title, employee, operator_initials,
                entry_date, comments, payload_json, version_no, previous_entry_id, created_at
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, params)
        entry_id = int(cur.fetchone()[0])
    conn.commit()
    conn.close()
    touch_run(data["run_id"])
    return entry_id


def insert_field_change_log(
    run_id: int,
    entry_table: str,
    record_id: int,
    changes: list[dict],
) -> None:
    """Insert the field-level correction rows captured by the edit forms."""
    if not changes:
        return

    conn = get_conn()
    cur = conn.cursor()
    # Each element in `changes` already matches the columns expected by `field_change_log`.
    for change in changes:
        cur.execute("""
            INSERT INTO field_change_log (
                run_id, entry_table, record_id, field_name, original_value, corrected_value, field_value, correction_reason,
                change_initials, changed_by_employee, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            entry_table,
            record_id,
            change.get("field_name", ""),
            change.get("original_value", ""),
            change.get("corrected_value", ""),
            change.get("field_value", ""),
            change.get("correction_reason", ""),
            change.get("change_initials", ""),
            change.get("changed_by_employee", ""),
            now_stamp(),
        ))

    conn.commit()
    conn.close()


def insert_audit(table_name: str, record_id: int, action_type: str, changed_by: str, old_data: str = "", new_data: str = ""):
    """Insert a high-level audit record describing a create, update, or finalize action."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO audit_log (table_name, record_id, action_type, changed_by, old_data, new_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (table_name, record_id, action_type, changed_by, old_data, new_data, now_stamp()))
    conn.commit()
    conn.close()


def get_field_change_history(run_id: int | None = None, limit: int = 200):
    """Return recent field-level correction history, optionally filtered to one run."""
    conn = get_conn()
    cur = conn.cursor()
    sqlite_backend = _is_sqlite_connection(conn)
    safe_limit = max(1, int(limit))
    if run_id:
        if sqlite_backend:
            cur.execute(f"""
                SELECT
                    f.*,
                    r.batch_number,
                    r.run_number,
                    r.blend_number
                FROM field_change_log f
                LEFT JOIN production_runs r ON r.id = f.run_id
                WHERE f.run_id = ?
                ORDER BY f.created_at DESC
                LIMIT {safe_limit}
            """, (run_id,))
        else:
            cur.execute(f"""
                SELECT TOP ({safe_limit})
                    f.*,
                    r.batch_number,
                    r.run_number,
                    r.blend_number
                FROM field_change_log f
                LEFT JOIN production_runs r ON r.id = f.run_id
                WHERE f.run_id = ?
                ORDER BY f.created_at DESC
            """, (run_id,))
    else:
        if sqlite_backend:
            cur.execute(f"""
                SELECT
                    f.*,
                    r.batch_number,
                    r.run_number,
                    r.blend_number
                FROM field_change_log f
                LEFT JOIN production_runs r ON r.id = f.run_id
                ORDER BY f.created_at DESC
                LIMIT {safe_limit}
            """)
        else:
            cur.execute(f"""
                SELECT TOP ({safe_limit})
                    f.*,
                    r.batch_number,
                    r.run_number,
                    r.blend_number
                FROM field_change_log f
                LEFT JOIN production_runs r ON r.id = f.run_id
                ORDER BY f.created_at DESC
            """)
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows


def last_12_hour_activity(hours: int = 12, limit: int = 300):
    """Return a flat recent-activity feed across all supported entry tables."""
    conn = get_conn()
    cur = conn.cursor()
    sqlite_backend = _is_sqlite_connection(conn)
    safe_hours = max(1, int(hours))
    safe_limit = max(1, int(limit))
    # The UNION keeps dashboard rendering simple by projecting every section into one common shape.
    if sqlite_backend:
        age_filter = f"-{safe_hours} hours"
        cur.execute(f"""
            SELECT *
            FROM (
                SELECT
                    r.id AS run_id,
                    e.id AS record_id,
                    'extraction_entries' AS entry_table,
                    e.created_at AS activity_time,
                    'Extraction' AS section,
                    '' AS stage_key,
                    e.employee,
                    e.operator_initials,
                    r.run_number,
                    r.batch_number,
                    r.blend_number,
                    r.status,
                    e.comments,
                    e.start_time AS start_label,
                    e.stop_time AS end_label
                FROM extraction_entries e
                LEFT JOIN production_runs r ON r.id = e.run_id
                WHERE datetime(replace(e.created_at, 'T', ' ')) >= datetime('now', ?)

                UNION ALL

                SELECT
                    r.id AS run_id,
                    f.id AS record_id,
                    'filtration_entries' AS entry_table,
                    f.created_at AS activity_time,
                    'Filtration' AS section,
                    '' AS stage_key,
                    f.employee,
                    f.operator_initials,
                    r.run_number,
                    r.batch_number,
                    r.blend_number,
                    r.status,
                    f.comments,
                    f.startup_time AS start_label,
                    f.shutdown_time AS end_label
                FROM filtration_entries f
                LEFT JOIN production_runs r ON r.id = f.run_id
                WHERE datetime(replace(f.created_at, 'T', ' ')) >= datetime('now', ?)

                UNION ALL

                SELECT
                    r.id AS run_id,
                    v.id AS record_id,
                    'evaporation_entries' AS entry_table,
                    v.created_at AS activity_time,
                    'Evaporation' AS section,
                    '' AS stage_key,
                    v.employee,
                    v.operator_initials,
                    r.run_number,
                    r.batch_number,
                    r.blend_number,
                    r.status,
                    v.comments,
                    v.startup_time AS start_label,
                    v.shutdown_time AS end_label
                FROM evaporation_entries v
                LEFT JOIN production_runs r ON r.id = v.run_id
                WHERE datetime(replace(v.created_at, 'T', ' ')) >= datetime('now', ?)

                UNION ALL

                SELECT
                    r.id AS run_id,
                    s.id AS record_id,
                    'sheet_entries' AS entry_table,
                    s.created_at AS activity_time,
                    s.stage_title AS section,
                    s.stage_key AS stage_key,
                    s.employee,
                    s.operator_initials,
                    r.run_number,
                    r.batch_number,
                    r.blend_number,
                    r.status,
                    s.comments,
                    '' AS start_label,
                    '' AS end_label
                FROM sheet_entries s
                LEFT JOIN production_runs r ON r.id = s.run_id
                WHERE datetime(replace(s.created_at, 'T', ' ')) >= datetime('now', ?)
            ) activity
            ORDER BY datetime(replace(activity_time, 'T', ' ')) DESC
            LIMIT {safe_limit}
        """, (age_filter, age_filter, age_filter, age_filter))
    else:
        cur.execute(f"""
            SELECT TOP ({safe_limit}) *
            FROM (
                SELECT
                    r.id AS run_id,
                    e.id AS record_id,
                    'extraction_entries' AS entry_table,
                    e.created_at AS activity_time,
                    'Extraction' AS section,
                    '' AS stage_key,
                    e.employee,
                    e.operator_initials,
                    r.run_number,
                    r.batch_number,
                    r.blend_number,
                    r.status,
                    e.comments,
                    e.start_time AS start_label,
                    e.stop_time AS end_label
                FROM extraction_entries e
                LEFT JOIN production_runs r ON r.id = e.run_id
                WHERE TRY_CONVERT(datetime2, e.created_at) >= DATEADD(HOUR, -{safe_hours}, GETDATE())

                UNION ALL

                SELECT
                    r.id AS run_id,
                    f.id AS record_id,
                    'filtration_entries' AS entry_table,
                    f.created_at AS activity_time,
                    'Filtration' AS section,
                    '' AS stage_key,
                    f.employee,
                    f.operator_initials,
                    r.run_number,
                    r.batch_number,
                    r.blend_number,
                    r.status,
                    f.comments,
                    f.startup_time AS start_label,
                    f.shutdown_time AS end_label
                FROM filtration_entries f
                LEFT JOIN production_runs r ON r.id = f.run_id
                WHERE TRY_CONVERT(datetime2, f.created_at) >= DATEADD(HOUR, -{safe_hours}, GETDATE())

                UNION ALL

                SELECT
                    r.id AS run_id,
                    v.id AS record_id,
                    'evaporation_entries' AS entry_table,
                    v.created_at AS activity_time,
                    'Evaporation' AS section,
                    '' AS stage_key,
                    v.employee,
                    v.operator_initials,
                    r.run_number,
                    r.batch_number,
                    r.blend_number,
                    r.status,
                    v.comments,
                    v.startup_time AS start_label,
                    v.shutdown_time AS end_label
                FROM evaporation_entries v
                LEFT JOIN production_runs r ON r.id = v.run_id
                WHERE TRY_CONVERT(datetime2, v.created_at) >= DATEADD(HOUR, -{safe_hours}, GETDATE())

                UNION ALL

                SELECT
                    r.id AS run_id,
                    s.id AS record_id,
                    'sheet_entries' AS entry_table,
                    s.created_at AS activity_time,
                    s.stage_title AS section,
                    s.stage_key AS stage_key,
                    s.employee,
                    s.operator_initials,
                    r.run_number,
                    r.batch_number,
                    r.blend_number,
                    r.status,
                    s.comments,
                    '' AS start_label,
                    '' AS end_label
                FROM sheet_entries s
                LEFT JOIN production_runs r ON r.id = s.run_id
                WHERE TRY_CONVERT(datetime2, s.created_at) >= DATEADD(HOUR, -{safe_hours}, GETDATE())
            ) activity
            ORDER BY activity_time DESC
        """)
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows
