"""Local SQLite persistence helpers for authentication, runs, stage entries, and audit history."""

import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / os.getenv("PLANT_APP_SQLITE_PATH", "plant.db")


def get_conn():
    """Open the local SQLite database used by the desktop app."""
    conn = sqlite3.connect(SQLITE_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA cache_size = -20000")
    return conn


def now_stamp() -> str:
    """Return a consistent timestamp string for inserts, updates, and audit rows."""
    return datetime.now().isoformat(timespec="seconds")


def row_to_dict(columns: list[str], row) -> dict | None:
    """Convert a sqlite row into a plain dictionary."""
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(zip(columns, row))


def rows_to_dicts(columns: list[str], rows) -> list[dict]:
    """Convert a list of database rows into plain dictionaries."""
    return [row_to_dict(columns, row) for row in rows]


def ensure_column(cur: sqlite3.Cursor, table_name: str, column_name: str, column_sql: str) -> None:
    """Add a column to an existing SQLite table when older local databases are missing it."""
    columns = {row["name"] for row in cur.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def init_db() -> None:
    """Create the local SQLite schema when needed and seed fallback local users."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
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
        )
    """)
    cur.execute("""
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
        )
    """)
    cur.execute("""
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
            version_no INTEGER DEFAULT 1,
            previous_entry_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS filtration_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            employee TEXT NOT NULL,
            operator_initials TEXT,
            entry_date TEXT,
            clarification_sequential_no TEXT,
            retentate_flow_set_point TEXT,
            zero_refract TEXT,
            startup_time TEXT,
            shutdown_time TEXT,
            start_time TEXT,
            stop_time TEXT,
            comments TEXT,
            photo_path TEXT,
            version_no INTEGER DEFAULT 1,
            previous_entry_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS filtration_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filtration_entry_id INTEGER NOT NULL,
            row_group TEXT,
            row_no INTEGER,
            row_time TEXT,
            feed_ri TEXT,
            retentate_ri TEXT,
            permeate_ri TEXT,
            perm_flow_c TEXT,
            perm_flow_d TEXT
        )
    """)
    cur.execute("""
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
            version_no INTEGER DEFAULT 1,
            previous_entry_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evaporation_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaporation_entry_id INTEGER NOT NULL,
            row_no INTEGER,
            row_time TEXT,
            feed_rate TEXT,
            evap_temp TEXT,
            row_vacuum TEXT,
            row_concentrate_ri TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            changed_by TEXT,
            old_data TEXT,
            new_data TEXT,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sheet_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            stage_key TEXT NOT NULL,
            stage_title TEXT NOT NULL,
            employee TEXT NOT NULL,
            operator_initials TEXT,
            entry_date TEXT,
            comments TEXT,
            payload_json TEXT NOT NULL,
            version_no INTEGER DEFAULT 1,
            previous_entry_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            entry_table TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            field_value TEXT,
            change_initials TEXT NOT NULL,
            changed_by_employee TEXT NOT NULL,
            created_at TEXT NOT NULL,
            original_value TEXT,
            corrected_value TEXT,
            correction_reason TEXT
        )
    """)

    ensure_column(cur, "users", "initials", "TEXT")
    ensure_column(cur, "users", "theme_preference", "TEXT DEFAULT 'light'")
    ensure_column(cur, "users", "font_scale_preference", "TEXT DEFAULT '1'")
    ensure_column(cur, "production_runs", "final_edit_initials", "TEXT")
    ensure_column(cur, "production_runs", "final_edit_notes", "TEXT")
    ensure_column(cur, "production_runs", "finalized_at", "TEXT")
    ensure_column(cur, "production_runs", "finalized_by", "TEXT")
    ensure_column(cur, "field_change_log", "original_value", "TEXT")
    ensure_column(cur, "field_change_log", "corrected_value", "TEXT")
    ensure_column(cur, "field_change_log", "correction_reason", "TEXT")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_employee_number ON users(employee_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_updated_at ON production_runs(updated_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_batch_number ON production_runs(batch_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_extraction_run_created ON extraction_entries(run_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_extraction_created_at ON extraction_entries(created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_filtration_run_created ON filtration_entries(run_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_filtration_created_at ON filtration_entries(created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_filtration_rows_entry_row ON filtration_rows(filtration_entry_id, row_group, row_no)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_evaporation_run_created ON evaporation_entries(run_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_evaporation_created_at ON evaporation_entries(created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_evaporation_rows_entry_row ON evaporation_rows(evaporation_entry_id, row_no)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sheet_run_stage_created ON sheet_entries(run_id, stage_key, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sheet_created_at ON sheet_entries(created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_table_record_created ON audit_log(table_name, record_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_field_change_run_created ON field_change_log(run_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_field_change_created_at ON field_change_log(created_at DESC)")

    cur.execute("""
        INSERT OR IGNORE INTO users (
            employee_number, full_name, password, role, initials,
            active, created_at, theme_preference, font_scale_preference
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "1001",
        "Operator 1", "test123", "operator", "OP",
        1, now_stamp(), "light", "1",
    ))
    cur.execute("""
        INSERT OR IGNORE INTO users (
            employee_number, full_name, password, role, initials,
            active, created_at, theme_preference, font_scale_preference
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "2001",
        "Supervisor 1", "test123", "supervisor", "SU",
        1, now_stamp(), "light", "1",
    ))
    conn.commit()
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
    conn = get_conn()
    cur = conn.cursor()
    # One shared timestamp is used for both created/updated values on the first insert.
    stamp = now_stamp()
    cur.execute("""
        INSERT INTO production_runs (
            batch_number, split_batch_number, blend_number, run_number, batch_type,
            reused_batch, product_name, shift_name, operator_id, notes, status,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?)
    """, (
        batch_number.strip(),
        split_batch_number.strip(),
        blend_number.strip(),
        run_number.strip(),
        batch_type.strip() or "standard",
        int(reused_batch),
        product_name.strip(),
        shift_name.strip(),
        operator_id.strip(),
        notes.strip(),
        stamp,
        stamp,
    ))
    run_id = cur.lastrowid
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
    safe_limit = max(1, int(limit))
    cur.execute("""
        SELECT *
        FROM production_runs
        ORDER BY updated_at DESC
        LIMIT ?
    """, (safe_limit,))
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
    """, (
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
    ))
    entry_id = cur.lastrowid
    conn.commit()
    conn.close()
    touch_run(data["run_id"])
    return entry_id


def insert_filtration(employee: str, data: dict) -> int:
    """Insert a new filtration entry plus its repeating child rows."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO filtration_entries (
            run_id, employee, operator_initials, entry_date,
            clarification_sequential_no, retentate_flow_set_point, zero_refract,
            startup_time, shutdown_time, start_time, stop_time,
            comments, photo_path, version_no, previous_entry_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
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
    ))
    entry_id = cur.lastrowid

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
    cur.execute("""
        INSERT INTO evaporation_entries (
            run_id, employee, operator_initials, entry_date, evaporator_no,
            startup_time, shutdown_time, feed_ri, concentrate_ri, steam_pressure,
            vacuum, sump_level, product_temp, comments, photo_path,
            version_no, previous_entry_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
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
    ))
    entry_id = cur.lastrowid

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
        batch_number.strip(),
        split_batch_number.strip(),
        blend_number.strip(),
        run_number.strip(),
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
    cur.execute("""
        INSERT INTO sheet_entries (
            run_id, stage_key, stage_title, employee, operator_initials,
            entry_date, comments, payload_json, version_no, previous_entry_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
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
    ))
    entry_id = cur.lastrowid
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
    if run_id:
        safe_limit = max(1, int(limit))
        cur.execute("""
            SELECT
                f.*,
                r.batch_number,
                r.run_number,
                r.blend_number
            FROM field_change_log f
            LEFT JOIN production_runs r ON r.id = f.run_id
            WHERE f.run_id = ?
            ORDER BY f.created_at DESC
            LIMIT ?
        """, (run_id, safe_limit))
    else:
        safe_limit = max(1, int(limit))
        cur.execute("""
            SELECT
                f.*,
                r.batch_number,
                r.run_number,
                r.blend_number
            FROM field_change_log f
            LEFT JOIN production_runs r ON r.id = f.run_id
            ORDER BY f.created_at DESC
            LIMIT ?
        """, (safe_limit,))
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
    threshold = (datetime.now() - timedelta(hours=safe_hours)).isoformat(timespec="seconds")
    # The UNION keeps dashboard rendering simple by projecting every section into one common shape.
    cur.execute("""
        SELECT *
        FROM (
            SELECT
                e.id AS record_id,
                'extraction_entries' AS entry_table,
                e.created_at AS activity_time,
                'Extraction' AS section,
                e.employee,
                e.operator_initials,
                r.run_number,
                r.batch_number,
                r.blend_number,
                e.comments,
                e.start_time AS start_label,
                e.stop_time AS end_label
            FROM extraction_entries e
            LEFT JOIN production_runs r ON r.id = e.run_id
            WHERE e.created_at >= ?

            UNION ALL

            SELECT
                f.id AS record_id,
                'filtration_entries' AS entry_table,
                f.created_at AS activity_time,
                'Filtration' AS section,
                f.employee,
                f.operator_initials,
                r.run_number,
                r.batch_number,
                r.blend_number,
                f.comments,
                f.startup_time AS start_label,
                f.shutdown_time AS end_label
            FROM filtration_entries f
            LEFT JOIN production_runs r ON r.id = f.run_id
            WHERE f.created_at >= ?

            UNION ALL

            SELECT
                v.id AS record_id,
                'evaporation_entries' AS entry_table,
                v.created_at AS activity_time,
                'Evaporation' AS section,
                v.employee,
                v.operator_initials,
                r.run_number,
                r.batch_number,
                r.blend_number,
                v.comments,
                v.startup_time AS start_label,
                v.shutdown_time AS end_label
            FROM evaporation_entries v
            LEFT JOIN production_runs r ON r.id = v.run_id
            WHERE v.created_at >= ?

            UNION ALL

            SELECT
                s.id AS record_id,
                'sheet_entries' AS entry_table,
                s.created_at AS activity_time,
                s.stage_title AS section,
                s.employee,
                s.operator_initials,
                r.run_number,
                r.batch_number,
                r.blend_number,
                s.comments,
                '' AS start_label,
                '' AS end_label
            FROM sheet_entries s
            LEFT JOIN production_runs r ON r.id = s.run_id
            WHERE s.created_at >= ?
        ) activity
        ORDER BY activity_time DESC
        LIMIT ?
    """, (threshold, threshold, threshold, threshold, safe_limit))
    columns = [col[0] for col in cur.description]
    rows = rows_to_dicts(columns, cur.fetchall())
    conn.close()
    return rows
