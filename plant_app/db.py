"""Local SQLite persistence helpers for authentication, runs, entries, and audit history."""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "plant.db"
DEFAULT_ADMIN_PASSCODE = "1234"
LEGACY_DEFAULT_ADMIN_PASSWORD = "LagAdmin2024!"
LEGACY_SAMPLE_PASSWORD = "test123"


def _env_text(name: str, default: str = "") -> str:
    """Return a trimmed environment value, falling back when missing or blank."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    trimmed = raw_value.strip()
    return trimmed if trimmed else default


def _valid_passcode(value: str) -> bool:
    """Return True when the supplied credential is exactly four numeric digits."""
    candidate = (value or "").strip()
    return len(candidate) == 4 and candidate.isdigit()


def _configured_admin_passcode() -> str:
    """Return the seeded admin passcode, preferring an explicit passcode env override."""
    for env_name in ("PLANT_APP_ADMIN_PASSCODE", "PLANT_APP_ADMIN_PASSWORD"):
        candidate = (os.getenv(env_name, "") or "").strip()
        if _valid_passcode(candidate):
            return candidate
    return DEFAULT_ADMIN_PASSCODE


def database_path() -> Path:
    """Return the local database file used by the portable app."""
    configured = _env_text("PLANT_APP_DB_PATH", str(DEFAULT_DB_PATH))
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return path


def _open_sqlite_conn():
    """Open the bundled SQLite database used by the local app."""
    db_path = database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_conn():
    """Open the local SQLite application database."""
    return _open_sqlite_conn()


def backend_status() -> dict[str, str]:
    """Return the local database target for diagnostics."""
    return {
        "backend": "sqlite",
        "database_path": str(database_path()),
        "export_mode": "flash_drive_pdf",
    }


def now_stamp() -> str:
    """Return a consistent timestamp string for inserts, updates, and audit rows."""
    return datetime.now().isoformat(timespec="seconds")


def row_to_dict(columns: list[str], row) -> dict | None:
    """Convert a database row into a plain dictionary."""
    if row is None:
        return None
    return dict(zip(columns, row))


def rows_to_dicts(columns: list[str], rows) -> list[dict]:
    """Convert a list of database rows into plain dictionaries."""
    return [row_to_dict(columns, row) for row in rows]


def column_exists(conn, cur, table_name: str, column_name: str) -> bool:
    """Return True when a table already has the requested column."""
    cur.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cur.fetchall())


def column_is_nullable(conn, cur, table_name: str, column_name: str) -> bool:
    """Return True when an existing column permits NULL values."""
    cur.execute(f"PRAGMA table_info({table_name})")
    for row in cur.fetchall():
        if row[1] == column_name:
            return not bool(row[3])
    return True


def add_column_if_missing(conn, cur, table_name: str, column_name: str, sqlite_type: str) -> None:
    """Add a nullable column when an existing installation is behind the app schema."""
    if column_exists(conn, cur, table_name, column_name):
        return
    cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sqlite_type}")


def make_column_nullable_if_needed(conn, cur, table_name: str, column_name: str, _column_type: str = "") -> None:
    """SQLite keeps existing column nullability as-is; new installs already use nullable columns."""
    return None


def _table_exists(conn, cur, table_name: str) -> bool:
    """Return True when the named table already exists in the database."""
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cur.fetchone() is not None


def ensure_core_schema(conn) -> None:
    """Create the local SQLite tables when the app is installed on a fresh drive."""
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_number TEXT UNIQUE NOT NULL,
            full_name TEXT,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'operator',
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            initials TEXT,
            theme_preference TEXT DEFAULT 'light',
            font_scale_preference TEXT DEFAULT '1'
        );

        CREATE TABLE IF NOT EXISTS production_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_number TEXT,
            split_batch_number TEXT,
            blend_number TEXT,
            run_number TEXT,
            batch_type TEXT DEFAULT 'standard',
            reused_batch INTEGER DEFAULT 0,
            product_name TEXT,
            shift_name TEXT,
            operator_id TEXT,
            notes TEXT,
            status TEXT DEFAULT 'Open',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            final_edit_initials TEXT,
            final_edit_notes TEXT,
            finalized_at TEXT,
            finalized_by TEXT
        );

        CREATE TABLE IF NOT EXISTS extraction_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            employee TEXT NOT NULL,
            operator_initials TEXT,
            entry_date TEXT,
            entry_time TEXT,
            location TEXT DEFAULT 'Pile',
            time_on_pile TEXT,
            start_time TEXT,
            stop_time TEXT,
            psf1_speed TEXT,
            psf1_load TEXT,
            psf1_blowback TEXT,
            psf2_speed TEXT,
            psf2_load TEXT,
            psf2_blowback TEXT,
            press_speed TEXT,
            press_load TEXT,
            press_blowback TEXT,
            pressate_ri TEXT,
            chip_bin_steam TEXT,
            chip_chute_temp TEXT,
            comments TEXT,
            photo_path TEXT,
            signature_data TEXT,
            signature_signed_at TEXT,
            version_no INTEGER DEFAULT 1,
            previous_entry_id INTEGER,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS filtration_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            employee TEXT NOT NULL,
            operator_initials TEXT,
            entry_date TEXT,
            cycle_volume_set_point TEXT,
            clarification_sequential_no TEXT,
            retentate_flow_set_point TEXT,
            zero_refract TEXT,
            startup_time TEXT,
            shutdown_time TEXT,
            start_time TEXT,
            stop_time TEXT,
            comments TEXT,
            photo_path TEXT,
            signature_data TEXT,
            signature_signed_at TEXT,
            payload_json TEXT,
            completion_status TEXT DEFAULT 'Complete',
            version_no INTEGER DEFAULT 1,
            previous_entry_id INTEGER,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS filtration_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filtration_entry_id INTEGER NOT NULL,
            row_group TEXT,
            row_no INTEGER,
            row_time TEXT,
            operator_initials TEXT,
            fic1_gpm TEXT,
            tit1 TEXT,
            tit2 TEXT,
            dpt TEXT,
            dpm TEXT,
            perm_total TEXT,
            f12_gpm TEXT,
            feed_ri TEXT,
            retentate_ri TEXT,
            permeate_ri TEXT,
            perm_flow_c TEXT,
            perm_flow_d TEXT,
            qic1_ntu_turbidity TEXT,
            pressure_pt1 TEXT,
            pressure_pt2 TEXT,
            pressure_pt3 TEXT
        );

        CREATE TABLE IF NOT EXISTS evaporation_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            employee TEXT NOT NULL,
            operator_initials TEXT,
            entry_date TEXT,
            evaporator_no TEXT,
            startup_time TEXT,
            shutdown_time TEXT,
            feed_ri TEXT,
            concentrate_ri TEXT,
            steam_pressure TEXT,
            vacuum TEXT,
            sump_level TEXT,
            product_temp TEXT,
            comments TEXT,
            photo_path TEXT,
            signature_data TEXT,
            signature_signed_at TEXT,
            version_no INTEGER DEFAULT 1,
            previous_entry_id INTEGER,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS evaporation_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaporation_entry_id INTEGER NOT NULL,
            row_no INTEGER,
            row_time TEXT,
            feed_rate TEXT,
            evap_temp TEXT,
            row_vacuum TEXT,
            row_concentrate_ri TEXT
        );

        CREATE TABLE IF NOT EXISTS sheet_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            stage_key TEXT NOT NULL,
            stage_title TEXT NOT NULL,
            employee TEXT NOT NULL,
            operator_initials TEXT,
            entry_date TEXT,
            comments TEXT,
            signature_data TEXT,
            signature_signed_at TEXT,
            payload_json TEXT NOT NULL,
            completion_status TEXT DEFAULT 'Complete',
            version_no INTEGER DEFAULT 1,
            previous_entry_id INTEGER,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS voided_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            stage_key TEXT NOT NULL,
            voided_by TEXT,
            voided_at TEXT NOT NULL,
            UNIQUE(run_id, stage_key)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            changed_by TEXT,
            old_data TEXT,
            new_data TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS field_change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            entry_table TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            original_value TEXT,
            corrected_value TEXT,
            field_value TEXT,
            correction_reason TEXT,
            change_initials TEXT NOT NULL,
            changed_by_employee TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_runs_updated_at ON production_runs(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_extraction_created_at ON extraction_entries(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_filtration_created_at ON filtration_entries(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_sheet_created_at ON sheet_entries(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_sheet_run_stage_created ON sheet_entries(run_id, stage_key, created_at DESC);
    """)
    conn.commit()


def ensure_schema_migrations(conn) -> None:
    """Apply small additive schema updates needed by newer forms."""
    cur = conn.cursor()
    if not _table_exists(conn, cur, "voided_stages"):
        cur.execute("""
            CREATE TABLE voided_stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                stage_key TEXT NOT NULL,
                voided_by TEXT,
                voided_at TEXT NOT NULL,
                UNIQUE(run_id, stage_key)
            )
        """)
        conn.commit()
    additions = (
        ("extraction_entries", "signature_data", "TEXT"),
        ("extraction_entries", "signature_signed_at", "TEXT"),
        ("filtration_entries", "signature_data", "TEXT"),
        ("filtration_entries", "signature_signed_at", "TEXT"),
        ("filtration_entries", "completion_status", "TEXT"),
        ("evaporation_entries", "signature_data", "TEXT"),
        ("evaporation_entries", "signature_signed_at", "TEXT"),
        ("sheet_entries", "signature_data", "TEXT"),
        ("sheet_entries", "signature_signed_at", "TEXT"),
        ("sheet_entries", "completion_status", "TEXT"),
        ("voided_stages", "voided_by", "TEXT"),
        ("filtration_entries", "cycle_volume_set_point", "TEXT"),
        ("filtration_entries", "payload_json", "TEXT"),
        ("filtration_rows", "operator_initials", "TEXT"),
        ("filtration_rows", "fic1_gpm", "TEXT"),
        ("filtration_rows", "tit1", "TEXT"),
        ("filtration_rows", "tit2", "TEXT"),
        ("filtration_rows", "dpt", "TEXT"),
        ("filtration_rows", "dpm", "TEXT"),
        ("filtration_rows", "perm_total", "TEXT"),
        ("filtration_rows", "f12_gpm", "TEXT"),
        ("filtration_rows", "qic1_ntu_turbidity", "TEXT"),
        ("filtration_rows", "pressure_pt1", "TEXT"),
        ("filtration_rows", "pressure_pt2", "TEXT"),
        ("filtration_rows", "pressure_pt3", "TEXT"),
    )
    for table_name, column_name, sqlite_type in additions:
        add_column_if_missing(conn, cur, table_name, column_name, sqlite_type)
    cur.execute("UPDATE filtration_entries SET completion_status = ? WHERE completion_status IS NULL OR completion_status = ''", ("Complete",))
    cur.execute("UPDATE sheet_entries SET completion_status = ? WHERE completion_status IS NULL OR completion_status = ''", ("Complete",))
    conn.commit()


def _seed_admin_user(conn) -> None:
    """Insert the admin account if no admin-role user exists yet."""
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE role = 'admin'")
    if cur.fetchone():
        return
    admin_password = _configured_admin_passcode()
    cur.execute("""
        INSERT INTO users (employee_number, full_name, password, role, active, created_at, initials, theme_preference, font_scale_preference)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("admin", "Lag Admin", admin_password, "admin", 1,
          datetime.now().isoformat(timespec="seconds"), "LA", "light", "1"))
    conn.commit()


def _migrate_legacy_user_passcodes(conn) -> None:
    """Convert seeded legacy credentials to four-digit passcodes without touching custom accounts."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET password = ?
        WHERE employee_number = ? AND role = 'admin' AND password = ?
        """,
        (_configured_admin_passcode(), "admin", LEGACY_DEFAULT_ADMIN_PASSWORD),
    )
    cur.execute(
        """
        UPDATE users
        SET password = employee_number
        WHERE employee_number IN (?, ?) AND password = ?
        """,
        ("1001", "2001", LEGACY_SAMPLE_PASSWORD),
    )
    conn.commit()


def init_db() -> None:
    """Validate and prepare the local SQLite database file."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1")
            cur.fetchone()
        finally:
            cur.close()
        ensure_core_schema(conn)
        ensure_schema_migrations(conn)
        _seed_admin_user(conn)
        _migrate_legacy_user_passcodes(conn)
    finally:
        conn.close()


def validate_user(employee: str, passcode: str) -> bool:
    """Return True when the supplied employee number and four-digit passcode match an active user."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT 1
        FROM users
        WHERE employee_number = ? AND password = ? AND active = 1
    """, (employee.strip(), passcode.strip()))
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


def get_completed_stage_keys_for_run(run_id: int) -> set:
    """Return the set of stage keys that have at least one complete entry for this run."""
    conn = get_conn()
    cur = conn.cursor()
    completed = set()
    cur.execute(
        """
        SELECT DISTINCT stage_key
        FROM sheet_entries
        WHERE run_id = ?
          AND COALESCE(completion_status, 'Complete') = 'Complete'
        """,
        (run_id,),
    )
    for row in cur.fetchall():
        completed.add(row[0])
    conn.close()
    return completed


def get_voided_stage_keys_for_run(run_id: int) -> set:
    """Return the set of stage keys that have been voided for this run."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT stage_key FROM voided_stages WHERE run_id = ?", (run_id,))
    keys = {row[0] for row in cur.fetchall()}
    conn.close()
    return keys


def get_voided_stages_for_run(run_id: int) -> dict:
    """Return voided stage metadata keyed by stage_key for print/review display."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT stage_key, voided_by, voided_at FROM voided_stages WHERE run_id = ?", (run_id,))
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return {row["stage_key"]: row for row in rows}


def toggle_stage_void(run_id: int, stage_key: str, voided_by: str = "") -> bool:
    """Toggle a stage void. Returns True if now voided, False if now restored."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM voided_stages WHERE run_id = ? AND stage_key = ?",
        (run_id, stage_key),
    )
    exists = cur.fetchone() is not None
    if exists:
        cur.execute(
            "DELETE FROM voided_stages WHERE run_id = ? AND stage_key = ?",
            (run_id, stage_key),
        )
    else:
        cur.execute(
            "INSERT INTO voided_stages (run_id, stage_key, voided_by, voided_at) VALUES (?, ?, ?, ?)",
            (run_id, stage_key, voided_by.strip(), datetime.now().isoformat(timespec="seconds")),
        )
    conn.commit()
    conn.close()
    return not exists


def get_user_role(employee: str) -> str:
    """Return the role string for a user, empty string if user not found."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE employee_number = ?", (employee.strip(),))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""


def employee_number_exists(employee: str) -> bool:
    """Return True when an account with that employee number already exists."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE employee_number = ?", (employee.strip(),))
    row = cur.fetchone()
    conn.close()
    return row is not None


def create_pending_user(employee: str, full_name: str, initials: str, passcode: str) -> None:
    """Create a new user with active=0 (pending admin approval)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (employee_number, full_name, password, role, active, created_at, initials, theme_preference, font_scale_preference)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (employee.strip(), full_name.strip(), passcode.strip(), "operator", 0,
          datetime.now().isoformat(timespec="seconds"), initials.strip().upper(), "light", "1"))
    conn.commit()
    conn.close()


def get_all_users() -> list:
    """Return all users ordered by pending first, then by creation date."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, employee_number, full_name, role, active, created_at, initials
        FROM users
        ORDER BY active ASC, created_at DESC
    """)
    columns = [col[0] for col in cur.description]
    rows = [row_to_dict(columns, r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_active_users() -> list:
    """Return only active users ordered alphabetically by full name."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, employee_number, full_name, role, active, created_at, initials
        FROM users
        WHERE active = 1
        ORDER BY full_name ASC
    """)
    columns = [col[0] for col in cur.description]
    rows = [row_to_dict(columns, r) for r in cur.fetchall()]
    conn.close()
    return rows


def approve_user(employee: str) -> None:
    """Set a pending user's account to active."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET active = 1 WHERE employee_number = ?", (employee.strip(),))
    conn.commit()
    conn.close()


def reject_user(employee: str) -> None:
    """Delete a pending user account."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE employee_number = ? AND role != 'admin'", (employee.strip(),))
    conn.commit()
    conn.close()


def deactivate_user(employee: str) -> None:
    """Disable an active user account without deleting it."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET active = 0 WHERE employee_number = ? AND role != 'admin'", (employee.strip(),))
    conn.commit()
    conn.close()


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
    cur.execute("""
        INSERT INTO production_runs (
            batch_number, split_batch_number, blend_number, run_number, batch_type,
            reused_batch, product_name, shift_name, operator_id, notes, status,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?)
    """, params)
    run_id = int(cur.lastrowid)
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


def get_run_by_number(run_number: str):
    """Fetch the most recent run whose run number or batch number matches exactly."""
    normalized = run_number.strip()
    if not normalized:
        return None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM production_runs
        WHERE run_number = ? OR batch_number = ?
        ORDER BY CASE WHEN status = 'Open' THEN 0 ELSE 1 END, updated_at DESC
        LIMIT 1
        """,
        (normalized, normalized),
    )
    columns = [col[0] for col in cur.description]
    row = row_to_dict(columns, cur.fetchone())
    conn.close()
    return row


def list_runs(limit: int = 50):
    """Return the most recently updated production runs for the selection screen."""
    conn = get_conn()
    cur = conn.cursor()
    safe_limit = max(1, int(limit))
    cur.execute(f"""
        SELECT *
        FROM production_runs
        ORDER BY updated_at DESC
        LIMIT {safe_limit}
    """)
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows


def get_run_stats() -> dict:
    """Return aggregate counts for the admin dashboard."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM production_runs")
    total_runs = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM production_runs WHERE status = 'Open'")
    open_runs = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM production_runs WHERE status != 'Open'")
    completed_runs = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM users WHERE active = 0")
    pending_users = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM users WHERE active = 1")
    active_users = cur.fetchone()[0] or 0
    conn.close()
    return {
        "total_runs": total_runs,
        "open_runs": open_runs,
        "completed_runs": completed_runs,
        "pending_users": pending_users,
        "active_users": active_users,
    }


def list_runs_paginated(
    page: int = 1,
    per_page: int = 25,
    search: str = "",
    status: str = "all",
    batch_type: str = "all",
):
    """Return a page of runs with total count; each row includes a stage_count field."""
    conn = get_conn()
    cur = conn.cursor()

    safe_page = max(1, int(page))
    safe_per_page = max(1, int(per_page))
    offset = (safe_page - 1) * safe_per_page
    like = f"%{search.strip()}%" if search.strip() else "%"

    status_clause = "" if status == "all" else "AND pr.status = ?"
    batch_type_clause = "" if batch_type == "all" else "AND COALESCE(NULLIF(TRIM(pr.batch_type), ''), 'standard') = ?"
    params_count = [like, like, like]
    params_data = [like, like, like]
    if status != "all":
        params_count.append(status)
        params_data.append(status)
    if batch_type != "all":
        params_count.append(batch_type)
        params_data.append(batch_type)

    stage_subquery = (
        "(SELECT COUNT(DISTINCT stage_key) FROM sheet_entries "
        "WHERE run_id = pr.id AND COALESCE(completion_status, 'Complete') = 'Complete')"
    )

    cur.execute(f"""
        SELECT COUNT(*) FROM production_runs pr
        WHERE (pr.run_number LIKE ? OR pr.batch_number LIKE ? OR pr.product_name LIKE ?)
        {status_clause}
        {batch_type_clause}
    """, params_count)
    total = cur.fetchone()[0] or 0

    cur.execute(f"""
        SELECT pr.*, ({stage_subquery}) AS stage_count
        FROM production_runs pr
        WHERE (pr.run_number LIKE ? OR pr.batch_number LIKE ? OR pr.product_name LIKE ?)
        {status_clause}
        {batch_type_clause}
        ORDER BY pr.updated_at DESC
        LIMIT {safe_per_page} OFFSET {offset}
    """, params_data)

    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows, total


def list_open_runs(limit: int = 100):
    """Return currently open runs ordered by the most recent activity."""
    conn = get_conn()
    cur = conn.cursor()
    safe_limit = max(1, int(limit))
    cur.execute(f"""
        SELECT *
        FROM production_runs
        WHERE status = 'Open'
        ORDER BY updated_at DESC
        LIMIT {safe_limit}
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


def list_runs_by_group_label(action_type: str, action_label: str) -> list[dict]:
    """Return runs currently stamped with the supplied split or blend label."""
    normalized = action_label.strip()
    if not normalized:
        return []

    if action_type == "blend":
        column_name = "blend_number"
    elif action_type == "split":
        column_name = "split_batch_number"
    else:
        raise ValueError(f"Unsupported run action: {action_type}")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT *
        FROM production_runs
        WHERE {column_name} = ?
        ORDER BY updated_at DESC
        """,
        (normalized,),
    )
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows


def list_recent_group_labels(action_type: str, limit: int = 12) -> list[dict]:
    """Return recently used blend or split labels so operators can reuse prior batch groupings."""
    if action_type == "blend":
        column_name = "blend_number"
    elif action_type == "split":
        column_name = "split_batch_number"
    else:
        raise ValueError(f"Unsupported run action: {action_type}")

    conn = get_conn()
    cur = conn.cursor()
    safe_limit = max(1, int(limit))

    cur.execute(
        f"""
        SELECT
            {column_name} AS label,
            MAX(updated_at) AS updated_at,
            COUNT(*) AS run_count
        FROM production_runs
        WHERE TRIM(COALESCE({column_name}, '')) != ''
        GROUP BY {column_name}
        ORDER BY MAX(updated_at) DESC
        LIMIT {safe_limit}
        """
    )

    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows


def set_run_product_name(run_id: int, product_name: str) -> None:
    """Update just the product name on an existing run."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE production_runs SET product_name = ?, updated_at = ? WHERE id = ?",
        (product_name.strip(), now_stamp(), run_id),
    )
    conn.commit()
    conn.close()


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


def apply_run_group_action(run_ids: list[int], action_type: str, action_label: str, update_batch_type: bool = True):
    """Stamp the selected runs with a shared blend or split label."""
    normalized_ids = [int(run_id) for run_id in run_ids if int(run_id) > 0]
    if not normalized_ids:
        return 0

    if action_type == "blend":
        action_sql = "blend_number = ?, split_batch_number = ''"
        if update_batch_type:
            action_sql += ", batch_type = 'blend'"
    elif action_type == "split":
        action_sql = "split_batch_number = ?, blend_number = ''"
        if update_batch_type:
            action_sql += ", batch_type = 'split'"
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


def set_run_batch_type(run_ids: list[int], batch_type: str):
    """Normalize one or more runs to a specific batch type without touching their labels."""
    normalized_ids = [int(run_id) for run_id in run_ids if int(run_id) > 0]
    if not normalized_ids:
        return 0

    placeholders = ", ".join("?" for _ in normalized_ids)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE production_runs
        SET batch_type = ?,
            updated_at = ?
        WHERE id IN ({placeholders})
        """,
        [batch_type.strip() or "standard", now_stamp(), *normalized_ids],
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
        data.get("signature_data", ""),
        data.get("signature_signed_at", ""),
        data.get("version_no", 1),
        data.get("previous_entry_id"),
        now_stamp(),
    )
    cur.execute("""
        INSERT INTO extraction_entries (
            run_id, employee, operator_initials, entry_date, entry_time, location,
            time_on_pile, start_time, stop_time,
            psf1_speed, psf1_load, psf1_blowback,
            psf2_speed, psf2_load, psf2_blowback,
            press_speed, press_load, press_blowback,
            pressate_ri, chip_bin_steam, chip_chute_temp,
            comments, photo_path, signature_data, signature_signed_at,
            version_no, previous_entry_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, params)
    entry_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    touch_run(data["run_id"])
    return entry_id


def insert_filtration(employee: str, data: dict) -> int:
    """Insert a new filtration entry plus its repeating child rows."""
    conn = get_conn()
    cur = conn.cursor()
    params = (
        data["run_id"],
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("cycle_volume_set_point", ""),
        data.get("clarification_sequential_no", ""),
        data.get("retentate_flow_set_point", ""),
        data.get("zero_refract", ""),
        data.get("startup_time", ""),
        data.get("shutdown_time", ""),
        data.get("start_time", ""),
        data.get("stop_time", ""),
        data.get("comments", ""),
        data.get("photo_path", ""),
        data.get("signature_data", ""),
        data.get("signature_signed_at", ""),
        data.get("payload_json", "{}"),
        data.get("completion_status", "Complete"),
        data.get("version_no", 1),
        data.get("previous_entry_id"),
        now_stamp(),
    )
    cur.execute("""
        INSERT INTO filtration_entries (
            run_id, employee, operator_initials, entry_date,
            cycle_volume_set_point,
            clarification_sequential_no, retentate_flow_set_point, zero_refract,
            startup_time, shutdown_time, start_time, stop_time,
            comments, photo_path, signature_data, signature_signed_at,
            payload_json, completion_status, version_no, previous_entry_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, params)
    entry_id = int(cur.lastrowid)

    # Child rows are inserted after the parent so they can reference the generated parent id.
    for row in data.get("rows", []):
        cur.execute("""
            INSERT INTO filtration_rows (
                filtration_entry_id, row_group, row_no, row_time,
                operator_initials, fic1_gpm, tit1, tit2, dpt, dpm, perm_total, f12_gpm,
                feed_ri, retentate_ri, permeate_ri, perm_flow_c, perm_flow_d,
                qic1_ntu_turbidity, pressure_pt1, pressure_pt2, pressure_pt3
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id,
            row.get("row_group", "main"),
            row.get("row_no", 1),
            row.get("row_time", ""),
            row.get("operator_initials", ""),
            row.get("fic1_gpm", ""),
            row.get("tit1", ""),
            row.get("tit2", ""),
            row.get("dpt", ""),
            row.get("dpm", ""),
            row.get("perm_total", ""),
            row.get("f12_gpm", ""),
            row.get("feed_ri", ""),
            row.get("retentate_ri", ""),
            row.get("permeate_ri", ""),
            row.get("perm_flow_c", ""),
            row.get("perm_flow_d", ""),
            row.get("qic1_ntu_turbidity", ""),
            row.get("pressure_pt1", ""),
            row.get("pressure_pt2", ""),
            row.get("pressure_pt3", ""),
        ))

    conn.commit()
    conn.close()
    touch_run(data["run_id"])
    return entry_id


def insert_evaporation(employee: str, data: dict) -> int:
    """Insert a new evaporation entry plus its repeating child rows."""
    conn = get_conn()
    cur = conn.cursor()
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
        data.get("signature_data", ""),
        data.get("signature_signed_at", ""),
        data.get("version_no", 1),
        data.get("previous_entry_id"),
        now_stamp(),
    )
    cur.execute("""
        INSERT INTO evaporation_entries (
            run_id, employee, operator_initials, entry_date, evaporator_no,
            startup_time, shutdown_time, feed_ri, concentrate_ri, steam_pressure,
            vacuum, sump_level, product_temp, comments, photo_path,
            signature_data, signature_signed_at, version_no, previous_entry_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, params)
    entry_id = int(cur.lastrowid)

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


def get_latest_extraction_for_run(run_id: int):
    """Fetch the latest extraction entry recorded for a specific run."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM extraction_entries
        WHERE run_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (run_id,),
    )
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
            signature_data = ?, signature_signed_at = ?,
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
        data.get("signature_data", ""),
        data.get("signature_signed_at", ""),
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


def get_latest_filtration_for_run(run_id: int):
    """Fetch the latest filtration entry recorded for a specific run."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM filtration_entries
        WHERE run_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (run_id,),
    )
    entry_columns = [col[0] for col in cur.description]
    entry = row_to_dict(entry_columns, cur.fetchone())
    rows = []
    if entry:
        cur.execute(
            """
            SELECT *
            FROM filtration_rows
            WHERE filtration_entry_id = ?
            ORDER BY row_group, row_no
            """,
            (entry["id"],),
        )
        row_columns = [col[0] for col in cur.description]
        rows = rows_to_dicts(row_columns, cur.fetchall())
    conn.close()
    return entry, rows


def get_latest_filtration_draft():
    """Fetch the most recent incomplete Microflow Filtration entry."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM filtration_entries
        WHERE COALESCE(completion_status, 'Complete') = 'Draft'
        ORDER BY id DESC
        LIMIT 1
        """
    )
    entry_columns = [col[0] for col in cur.description]
    entry = row_to_dict(entry_columns, cur.fetchone())
    rows = []
    if entry:
        cur.execute(
            """
            SELECT *
            FROM filtration_rows
            WHERE filtration_entry_id = ?
            ORDER BY row_group, row_no
            """,
            (entry["id"],),
        )
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
            cycle_volume_set_point = ?, retentate_flow_set_point = ?, zero_refract = ?, startup_time = ?, shutdown_time = ?,
            start_time = ?, stop_time = ?, comments = ?, photo_path = ?,
            signature_data = ?, signature_signed_at = ?, payload_json = ?,
            completion_status = ?,
            version_no = COALESCE(version_no, 1) + 1
        WHERE id = ?
    """, (
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("clarification_sequential_no", ""),
        data.get("cycle_volume_set_point", ""),
        data.get("retentate_flow_set_point", ""),
        data.get("zero_refract", ""),
        data.get("startup_time", ""),
        data.get("shutdown_time", ""),
        data.get("start_time", ""),
        data.get("stop_time", ""),
        data.get("comments", ""),
        data.get("photo_path", ""),
        data.get("signature_data", ""),
        data.get("signature_signed_at", ""),
        data.get("payload_json", "{}"),
        data.get("completion_status", "Complete"),
        entry_id,
    ))
    # Rebuild the child rows from the submitted form so the saved set always matches the current screen.
    cur.execute("DELETE FROM filtration_rows WHERE filtration_entry_id = ?", (entry_id,))
    for row in data.get("rows", []):
        cur.execute("""
            INSERT INTO filtration_rows (
                filtration_entry_id, row_group, row_no, row_time,
                operator_initials, fic1_gpm, tit1, tit2, dpt, dpm, perm_total, f12_gpm,
                feed_ri, retentate_ri, permeate_ri, perm_flow_c, perm_flow_d,
                qic1_ntu_turbidity, pressure_pt1, pressure_pt2, pressure_pt3
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id,
            row.get("row_group", "main"),
            row.get("row_no", 1),
            row.get("row_time", ""),
            row.get("operator_initials", ""),
            row.get("fic1_gpm", ""),
            row.get("tit1", ""),
            row.get("tit2", ""),
            row.get("dpt", ""),
            row.get("dpm", ""),
            row.get("perm_total", ""),
            row.get("f12_gpm", ""),
            row.get("feed_ri", ""),
            row.get("retentate_ri", ""),
            row.get("permeate_ri", ""),
            row.get("perm_flow_c", ""),
            row.get("perm_flow_d", ""),
            row.get("qic1_ntu_turbidity", ""),
            row.get("pressure_pt1", ""),
            row.get("pressure_pt2", ""),
            row.get("pressure_pt3", ""),
        ))
    conn.commit()
    conn.close()


def list_all_extraction_entries(search: str = "", limit: int = 300) -> list[dict]:
    """Return extraction entries joined to their run number, newest first."""
    conn = get_conn()
    cur = conn.cursor()
    pattern = f"%{search}%"
    cur.execute(
        """
        SELECT e.id, e.run_id, e.employee, e.operator_initials, e.entry_date, e.entry_time,
               e.location, e.start_time, e.stop_time, e.comments, e.version_no, e.created_at,
               r.run_number
        FROM extraction_entries e
        LEFT JOIN production_runs r ON r.id = e.run_id
        WHERE ? = '' OR r.run_number LIKE ? OR e.employee LIKE ? OR e.entry_date LIKE ?
        ORDER BY e.created_at DESC
        LIMIT ?
        """,
        (search, pattern, pattern, pattern, limit),
    )
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows


def list_all_filtration_entries(search: str = "", limit: int = 300) -> list[dict]:
    """Return filtration entries joined to their run number, newest first."""
    conn = get_conn()
    cur = conn.cursor()
    pattern = f"%{search}%"
    cur.execute(
        """
        SELECT e.id, e.run_id, e.employee, e.operator_initials, e.entry_date,
               e.cycle_volume_set_point, e.startup_time, e.shutdown_time,
               e.completion_status, e.comments, e.version_no, e.created_at,
               r.run_number
        FROM filtration_entries e
        LEFT JOIN production_runs r ON r.id = e.run_id
        WHERE ? = '' OR r.run_number LIKE ? OR e.employee LIKE ? OR e.entry_date LIKE ?
        ORDER BY e.created_at DESC
        LIMIT ?
        """,
        (search, pattern, pattern, pattern, limit),
    )
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows


def list_all_clarifier_entries(search: str = "", limit: int = 300) -> list[dict]:
    """Return standalone clarifier sheet entries, newest first."""
    import json as _json
    conn = get_conn()
    cur = conn.cursor()
    pattern = f"%{search}%"
    cur.execute(
        """
        SELECT e.id, e.employee, e.operator_initials, e.entry_date,
               e.completion_status, e.version_no, e.created_at, e.payload_json
        FROM sheet_entries e
        WHERE e.stage_key = 'clarifier'
          AND (? = '' OR e.operator_initials LIKE ? OR e.employee LIKE ? OR e.entry_date LIKE ?)
        ORDER BY e.created_at DESC
        LIMIT ?
        """,
        (search, pattern, pattern, pattern, limit),
    )
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    for row in rows:
        try:
            payload = _json.loads(row.get("payload_json") or "{}")
            row["clarification_sequential_no"] = payload.get("clarification_sequential_no", "")
        except (TypeError, ValueError):
            row["clarification_sequential_no"] = ""
    return rows


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
    cur.execute("""
        SELECT * FROM evaporation_entries
        WHERE run_id = ?
        ORDER BY id DESC
        LIMIT 1
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
            comments = ?, photo_path = ?, signature_data = ?, signature_signed_at = ?,
            version_no = COALESCE(version_no, 1) + 1
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
        data.get("signature_data", ""),
        data.get("signature_signed_at", ""),
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
    cur.execute("""
        SELECT * FROM sheet_entries
        WHERE run_id = ? AND stage_key = ?
        ORDER BY id DESC
        LIMIT 1
    """, (run_id, stage_key))
    columns = [col[0] for col in cur.description]
    row = row_to_dict(columns, cur.fetchone())
    conn.close()
    return row


def get_latest_standalone_sheet_draft(stage_key: str):
    """Fetch the newest draft generic sheet that is not tied to a run."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM sheet_entries
        WHERE run_id IS NULL
          AND stage_key = ?
          AND COALESCE(completion_status, 'Complete') = 'Draft'
        ORDER BY id DESC
        LIMIT 1
        """,
        (stage_key,),
    )
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
            signature_data = ?, signature_signed_at = ?, payload_json = ?,
            completion_status = ?,
            version_no = COALESCE(version_no, 1) + 1
        WHERE id = ?
    """, (
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("comments", ""),
        data.get("signature_data", ""),
        data.get("signature_signed_at", ""),
        data.get("payload_json", "{}"),
        data.get("completion_status", "Complete"),
        entry_id,
    ))
    conn.commit()
    conn.close()


def insert_sheet_entry(employee: str, data: dict) -> int:
    """Insert a new generic stage sheet and return its id."""
    conn = get_conn()
    cur = conn.cursor()
    params = (
        data["run_id"],
        data["stage_key"],
        data["stage_title"],
        employee,
        data.get("operator_initials", ""),
        data.get("entry_date", ""),
        data.get("comments", ""),
        data.get("signature_data", ""),
        data.get("signature_signed_at", ""),
        data.get("payload_json", "{}"),
        data.get("completion_status", "Complete"),
        data.get("version_no", 1),
        data.get("previous_entry_id"),
        now_stamp(),
    )
    cur.execute("""
        INSERT INTO sheet_entries (
            run_id, stage_key, stage_title, employee, operator_initials,
            entry_date, comments, signature_data, signature_signed_at,
            payload_json, completion_status, version_no, previous_entry_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, params)
    entry_id = int(cur.lastrowid)
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
    safe_limit = max(1, int(limit))
    if run_id:
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
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows


def last_12_hour_activity(hours: int = 12, limit: int = 300):
    """Return a flat recent-activity feed across all supported entry tables."""
    conn = get_conn()
    cur = conn.cursor()
    safe_hours = max(1, int(hours))
    safe_limit = max(1, int(limit))
    # The UNION keeps dashboard rendering simple by projecting every section into one common shape.
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
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows
