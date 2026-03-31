import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "plant.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    # OneDrive-backed directories can block SQLite sidecar journal files.
    # Keep the rollback journal in memory so writes still succeed.
    conn.execute("PRAGMA journal_mode=MEMORY;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_column(cur: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    if column not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def table_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def recreate_legacy_entry_tables(cur: sqlite3.Cursor) -> None:
    extraction_cols = table_columns(cur, "extraction_entries")
    if "batch_number" in extraction_cols:
        cur.execute("ALTER TABLE extraction_entries RENAME TO extraction_entries_legacy")
        cur.execute("""
        CREATE TABLE extraction_entries (
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
        );
        """)
        cur.execute("""
        INSERT INTO extraction_entries (
            id, run_id, employee, operator_initials, entry_date, entry_time, location,
            time_on_pile, start_time, stop_time, psf1_speed, psf1_load, psf1_blowback,
            psf2_speed, psf2_load, psf2_blowback, press_speed, press_load, press_blowback,
            pressate_ri, chip_bin_steam, chip_chute_temp, comments, photo_path,
            version_no, previous_entry_id, created_at
        )
        SELECT
            id, NULL, employee, operator_initials, entry_date, entry_time,
            COALESCE(location, 'Pile'),
            COALESCE(time_on_pile, time_on_pipe_or_pile, ''),
            COALESCE(start_time, ''),
            COALESCE(stop_time, ''),
            COALESCE(psf1_speed, ''), COALESCE(psf1_load, ''), COALESCE(psf1_blowback, ''),
            COALESCE(psf2_speed, ''), COALESCE(psf2_load, ''), COALESCE(psf2_blowback, ''),
            COALESCE(press_speed, ''), COALESCE(press_load, ''), COALESCE(press_blowback, ''),
            COALESCE(pressate_ri, ''), COALESCE(chip_bin_steam, ''), COALESCE(chip_chute_temp, ''),
            COALESCE(comments, notes, ''), COALESCE(photo_path, ''),
            COALESCE(version_no, 1), previous_entry_id, created_at
        FROM extraction_entries_legacy
        """)
        cur.execute("DROP TABLE extraction_entries_legacy")

    filtration_cols = table_columns(cur, "filtration_entries")
    if "batch_number" in filtration_cols:
        cur.execute("ALTER TABLE filtration_entries RENAME TO filtration_entries_legacy")
        cur.execute("""
        CREATE TABLE filtration_entries (
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
        );
        """)
        cur.execute("""
        INSERT INTO filtration_entries (
            id, run_id, employee, operator_initials, entry_date, clarification_sequential_no,
            retentate_flow_set_point, zero_refract, startup_time, shutdown_time,
            start_time, stop_time, comments, photo_path, version_no, previous_entry_id, created_at
        )
        SELECT
            id, NULL, employee, operator_initials, entry_date, clarification_sequential_no,
            retentate_flow_set_point, zero_refract, startup_time, shutdown_time,
            COALESCE(start_time, ''), COALESCE(stop_time, ''),
            COALESCE(comments, notes, ''), COALESCE(photo_path, ''),
            COALESCE(version_no, 1), previous_entry_id, created_at
        FROM filtration_entries_legacy
        """)
        cur.execute("""
        INSERT INTO filtration_rows (
            filtration_entry_id, row_group, row_no, row_time,
            feed_ri, retentate_ri, permeate_ri, perm_flow_c, perm_flow_d
        )
        SELECT id, 'main', 1, COALESCE(row1_time, ''), COALESCE(row1_feed_ri, ''), COALESCE(row1_retentate_ri, ''), COALESCE(row1_permeate_ri, ''), COALESCE(row1_perm_flow_c, ''), COALESCE(row1_perm_flow_d, '')
        FROM filtration_entries_legacy
        UNION ALL
        SELECT id, 'main', 2, COALESCE(row2_time, ''), COALESCE(row2_feed_ri, ''), COALESCE(row2_retentate_ri, ''), COALESCE(row2_permeate_ri, ''), COALESCE(row2_perm_flow_c, ''), COALESCE(row2_perm_flow_d, '')
        FROM filtration_entries_legacy
        UNION ALL
        SELECT id, 'main', 3, COALESCE(row3_time, ''), COALESCE(row3_feed_ri, ''), COALESCE(row3_retentate_ri, ''), COALESCE(row3_permeate_ri, ''), COALESCE(row3_perm_flow_c, ''), COALESCE(row3_perm_flow_d, '')
        FROM filtration_entries_legacy
        UNION ALL
        SELECT id, 'dia', 1, COALESCE(dia_row1_time, ''), COALESCE(dia_row1_feed_ri, ''), COALESCE(dia_row1_retentate_ri, ''), COALESCE(dia_row1_permeate_ri, ''), '', ''
        FROM filtration_entries_legacy
        UNION ALL
        SELECT id, 'dia', 2, COALESCE(dia_row2_time, ''), COALESCE(dia_row2_feed_ri, ''), COALESCE(dia_row2_retentate_ri, ''), COALESCE(dia_row2_permeate_ri, ''), '', ''
        FROM filtration_entries_legacy
        """)
        cur.execute("DROP TABLE filtration_entries_legacy")

    evaporation_cols = table_columns(cur, "evaporation_entries")
    if "batch_number" in evaporation_cols:
        cur.execute("ALTER TABLE evaporation_entries RENAME TO evaporation_entries_legacy")
        cur.execute("""
        CREATE TABLE evaporation_entries (
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
        );
        """)
        cur.execute("""
        INSERT INTO evaporation_entries (
            id, run_id, employee, operator_initials, entry_date, evaporator_no,
            startup_time, shutdown_time, feed_ri, concentrate_ri, steam_pressure,
            vacuum, sump_level, product_temp, comments, photo_path,
            version_no, previous_entry_id, created_at
        )
        SELECT
            id, NULL, employee, operator_initials, entry_date, evaporator_no,
            startup_time, shutdown_time, feed_ri, concentrate_ri, steam_pressure,
            vacuum, sump_level, product_temp, COALESCE(comments, notes, ''), COALESCE(photo_path, ''),
            COALESCE(version_no, 1), previous_entry_id, created_at
        FROM evaporation_entries_legacy
        """)
        cur.execute("""
        INSERT INTO evaporation_rows (
            evaporation_entry_id, row_no, row_time, feed_rate,
            evap_temp, row_vacuum, row_concentrate_ri
        )
        SELECT id, 1, COALESCE(row1_time, ''), COALESCE(row1_feed_rate, ''), COALESCE(row1_evap_temp, ''), COALESCE(row1_vacuum, ''), COALESCE(row1_concentrate_ri, '')
        FROM evaporation_entries_legacy
        UNION ALL
        SELECT id, 2, COALESCE(row2_time, ''), COALESCE(row2_feed_rate, ''), COALESCE(row2_evap_temp, ''), COALESCE(row2_vacuum, ''), COALESCE(row2_concentrate_ri, '')
        FROM evaporation_entries_legacy
        UNION ALL
        SELECT id, 3, COALESCE(row3_time, ''), COALESCE(row3_feed_rate, ''), COALESCE(row3_evap_temp, ''), COALESCE(row3_vacuum, ''), COALESCE(row3_concentrate_ri, '')
        FROM evaporation_entries_legacy
        """)
        cur.execute("DROP TABLE evaporation_entries_legacy")


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_number TEXT UNIQUE NOT NULL,
        full_name TEXT,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'operator',
        initials TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );
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
        finalized_at TEXT,
        finalized_by TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
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
    );
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
    );
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
    );
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
    );
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
    );
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
    );
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
    );
    """)

    cur.execute("""
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
    """)

    recreate_legacy_entry_tables(cur)

    # Migrate older batch-based databases forward so run-based screens can boot
    # against an existing plant.db instead of only on a fresh file.
    ensure_column(cur, "users", "initials", "TEXT")

    ensure_column(cur, "extraction_entries", "run_id", "INTEGER")
    ensure_column(cur, "extraction_entries", "time_on_pile", "TEXT")
    ensure_column(cur, "extraction_entries", "start_time", "TEXT")
    ensure_column(cur, "extraction_entries", "stop_time", "TEXT")
    ensure_column(cur, "extraction_entries", "comments", "TEXT")
    ensure_column(cur, "extraction_entries", "photo_path", "TEXT")
    ensure_column(cur, "extraction_entries", "version_no", "INTEGER DEFAULT 1")
    ensure_column(cur, "extraction_entries", "previous_entry_id", "INTEGER")

    ensure_column(cur, "filtration_entries", "run_id", "INTEGER")
    ensure_column(cur, "filtration_entries", "start_time", "TEXT")
    ensure_column(cur, "filtration_entries", "stop_time", "TEXT")
    ensure_column(cur, "filtration_entries", "comments", "TEXT")
    ensure_column(cur, "filtration_entries", "photo_path", "TEXT")
    ensure_column(cur, "filtration_entries", "version_no", "INTEGER DEFAULT 1")
    ensure_column(cur, "filtration_entries", "previous_entry_id", "INTEGER")

    ensure_column(cur, "evaporation_entries", "run_id", "INTEGER")
    ensure_column(cur, "evaporation_entries", "comments", "TEXT")
    ensure_column(cur, "evaporation_entries", "photo_path", "TEXT")
    ensure_column(cur, "evaporation_entries", "version_no", "INTEGER DEFAULT 1")
    ensure_column(cur, "evaporation_entries", "previous_entry_id", "INTEGER")

    ensure_column(cur, "sheet_entries", "run_id", "INTEGER")
    ensure_column(cur, "sheet_entries", "operator_initials", "TEXT")
    ensure_column(cur, "sheet_entries", "entry_date", "TEXT")
    ensure_column(cur, "sheet_entries", "comments", "TEXT")
    ensure_column(cur, "sheet_entries", "version_no", "INTEGER DEFAULT 1")
    ensure_column(cur, "sheet_entries", "previous_entry_id", "INTEGER")
    ensure_column(cur, "production_runs", "final_edit_initials", "TEXT")
    ensure_column(cur, "production_runs", "final_edit_notes", "TEXT")
    ensure_column(cur, "production_runs", "finalized_at", "TEXT")
    ensure_column(cur, "production_runs", "finalized_by", "TEXT")
    ensure_column(cur, "field_change_log", "original_value", "TEXT")
    ensure_column(cur, "field_change_log", "corrected_value", "TEXT")
    ensure_column(cur, "field_change_log", "correction_reason", "TEXT")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_updated ON production_runs(updated_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_batch ON production_runs(batch_number);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_extraction_run ON extraction_entries(run_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_filtration_run ON filtration_entries(run_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_evaporation_run ON evaporation_entries(run_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sheet_entries_run ON sheet_entries(run_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sheet_entries_stage ON sheet_entries(stage_key);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_field_change_log_run ON field_change_log(run_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_field_change_log_record ON field_change_log(entry_table, record_id);")

    conn.commit()

    cur.execute("""
        INSERT OR IGNORE INTO users (employee_number, full_name, password, role, initials, active, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
    """, ("1001", "Operator 1", "test123", "operator", "OP", now_stamp()))

    cur.execute("""
        INSERT OR IGNORE INTO users (employee_number, full_name, password, role, initials, active, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
    """, ("2001", "Supervisor 1", "test123", "supervisor", "SU", now_stamp()))

    conn.commit()
    conn.close()


def validate_user(employee: str, password: str) -> bool:
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
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT initials FROM users WHERE employee_number = ?", (employee.strip(),))
    row = cur.fetchone()
    conn.close()
    if row and row["initials"]:
        return row["initials"]
    return (employee[:2] if employee else "").upper()


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
    conn = get_conn()
    cur = conn.cursor()
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
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM production_runs WHERE id = ?", (run_id,))
    row = cur.fetchone()
    conn.close()
    return row


def list_runs(limit: int = 50):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM production_runs
        ORDER BY updated_at DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def mark_run_complete(run_id: int, employee: str = ""):
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
    if not run_id:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE production_runs SET updated_at = ? WHERE id = ?", (now_stamp(), run_id))
    conn.commit()
    conn.close()


def insert_extraction(employee: str, data: dict) -> int:
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
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM extraction_entries WHERE id = ?", (entry_id,))
    row = cur.fetchone()
    conn.close()
    return row


def update_extraction(entry_id: int, employee: str, data: dict) -> None:
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
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM filtration_entries WHERE id = ?", (entry_id,))
    entry = cur.fetchone()
    cur.execute("""
        SELECT * FROM filtration_rows
        WHERE filtration_entry_id = ?
        ORDER BY row_group, row_no
    """, (entry_id,))
    rows = cur.fetchall()
    conn.close()
    return entry, rows


def update_filtration(entry_id: int, employee: str, data: dict) -> None:
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
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM evaporation_entries WHERE id = ?", (entry_id,))
    entry = cur.fetchone()
    cur.execute("""
        SELECT * FROM evaporation_rows
        WHERE evaporation_entry_id = ?
        ORDER BY row_no
    """, (entry_id,))
    rows = cur.fetchall()
    conn.close()
    return entry, rows


def get_latest_evaporation_for_run(run_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM evaporation_entries
        WHERE run_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (run_id,))
    entry = cur.fetchone()
    rows = []
    if entry:
        cur.execute("""
            SELECT * FROM evaporation_rows
            WHERE evaporation_entry_id = ?
            ORDER BY row_no
        """, (entry["id"],))
        rows = cur.fetchall()
    conn.close()
    return entry, rows


def update_evaporation(entry_id: int, employee: str, data: dict) -> None:
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
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sheet_entries WHERE id = ?", (entry_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_latest_sheet_entry_for_run_stage(run_id: int, stage_key: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM sheet_entries
        WHERE run_id = ? AND stage_key = ?
        ORDER BY id DESC
        LIMIT 1
    """, (run_id, stage_key))
    row = cur.fetchone()
    conn.close()
    return row


def update_sheet_entry(entry_id: int, employee: str, data: dict) -> None:
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
    if not changes:
        return

    conn = get_conn()
    cur = conn.cursor()
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
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO audit_log (table_name, record_id, action_type, changed_by, old_data, new_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (table_name, record_id, action_type, changed_by, old_data, new_data, now_stamp()))
    conn.commit()
    conn.close()


def get_field_change_history(run_id: int | None = None, limit: int = 200):
    conn = get_conn()
    cur = conn.cursor()
    if run_id:
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
        """, (run_id, limit))
    else:
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
        """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def last_12_hour_activity():
    conn = get_conn()
    cur = conn.cursor()
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
            WHERE datetime(e.created_at) >= datetime('now', '-12 hours')

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
            WHERE datetime(f.created_at) >= datetime('now', '-12 hours')

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
            WHERE datetime(v.created_at) >= datetime('now', '-12 hours')

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
            WHERE datetime(s.created_at) >= datetime('now', '-12 hours')
        ) activity
        ORDER BY activity_time DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows
