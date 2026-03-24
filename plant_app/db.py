import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

DB_PATH = Path(__file__).resolve().parent / "plant.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_column(cur: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    cur.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cur.fetchall()}
    if column not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_number TEXT UNIQUE NOT NULL,
        product_name TEXT,
        shift_name TEXT,
        operator_id TEXT,
        split_batch_number TEXT,
        run_number TEXT,
        blend_number TEXT,
        notes TEXT,
        status TEXT DEFAULT 'Open',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS extraction_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_number TEXT NOT NULL,
        employee TEXT NOT NULL,
        operator_initials TEXT,
        entry_date TEXT,
        entry_time TEXT,
        start_time TEXT,
        stop_time TEXT,
        location TEXT,
        time_on_pipe_or_pile TEXT,
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
        notes TEXT,
        created_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS filtration_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_number TEXT NOT NULL,
        employee TEXT NOT NULL,
        operator_initials TEXT,
        entry_date TEXT,
        clarification_sequential_no TEXT,
        retentate_flow_set_point TEXT,
        zero_refract TEXT,
        startup_time TEXT,
        shutdown_time TEXT,
        row1_time TEXT,
        row1_feed_ri TEXT,
        row1_retentate_ri TEXT,
        row1_permeate_ri TEXT,
        row1_perm_flow_c TEXT,
        row1_perm_flow_d TEXT,
        row2_time TEXT,
        row2_feed_ri TEXT,
        row2_retentate_ri TEXT,
        row2_permeate_ri TEXT,
        row2_perm_flow_c TEXT,
        row2_perm_flow_d TEXT,
        row3_time TEXT,
        row3_feed_ri TEXT,
        row3_retentate_ri TEXT,
        row3_permeate_ri TEXT,
        row3_perm_flow_c TEXT,
        row3_perm_flow_d TEXT,
        dia_row1_time TEXT,
        dia_row1_feed_ri TEXT,
        dia_row1_retentate_ri TEXT,
        dia_row1_permeate_ri TEXT,
        dia_row2_time TEXT,
        dia_row2_feed_ri TEXT,
        dia_row2_retentate_ri TEXT,
        dia_row2_permeate_ri TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS evaporation_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_number TEXT NOT NULL,
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
        row1_time TEXT,
        row1_feed_rate TEXT,
        row1_evap_temp TEXT,
        row1_vacuum TEXT,
        row1_concentrate_ri TEXT,
        row2_time TEXT,
        row2_feed_rate TEXT,
        row2_evap_temp TEXT,
        row2_vacuum TEXT,
        row2_concentrate_ri TEXT,
        row3_time TEXT,
        row3_feed_rate TEXT,
        row3_evap_temp TEXT,
        row3_vacuum TEXT,
        row3_concentrate_ri TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    );
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_batches_number ON batches(batch_number);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_extraction_batch ON extraction_entries(batch_number);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_filtration_batch ON filtration_entries(batch_number);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_evaporation_batch ON evaporation_entries(batch_number);")

    ensure_column(cur, "batches", "run_number", "TEXT")
    ensure_column(cur, "batches", "blend_number", "TEXT")
    ensure_column(cur, "extraction_entries", "start_time", "TEXT")
    ensure_column(cur, "extraction_entries", "stop_time", "TEXT")

    conn.commit()

    cur.execute(
        """
        INSERT OR IGNORE INTO users (employee_number, full_name, password, role, active, created_at)
        VALUES (?, ?, ?, ?, 1, ?)
        """,
        ("1001", "Operator 1", "test123", "operator", now_stamp()),
    )
    cur.execute(
        """
        INSERT OR IGNORE INTO users (employee_number, full_name, password, role, active, created_at)
        VALUES (?, ?, ?, ?, 1, ?)
        """,
        ("2001", "Supervisor 1", "test123", "supervisor", now_stamp()),
    )
    conn.commit()
    conn.close()


def validate_user(employee: str, password: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM users WHERE employee_number = ? AND password = ? AND active = 1",
        (employee.strip(), password.strip()),
    )
    row = cur.fetchone()
    conn.close()
    return row is not None


def get_user(employee: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT employee_number, full_name, role
        FROM users
        WHERE employee_number = ? AND active = 1
        """,
        (employee.strip(),),
    )
    row = cur.fetchone()
    conn.close()
    return row


def upsert_batch(
    batch_number: str,
    product_name: str,
    shift_name: str,
    operator_id: str,
    split_batch_number: str = "",
    run_number: str = "",
    blend_number: str = "",
    notes: str = "",
) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    stamp = now_stamp()
    cur.execute("SELECT id FROM batches WHERE batch_number = ?", (batch_number.strip(),))
    row = cur.fetchone()
    if row:
        cur.execute(
            """
            UPDATE batches
            SET product_name = ?, shift_name = ?, operator_id = ?, split_batch_number = ?, run_number = ?, blend_number = ?, notes = ?, updated_at = ?
            WHERE batch_number = ?
            """,
            (
                product_name.strip(),
                shift_name.strip(),
                operator_id.strip(),
                split_batch_number.strip(),
                run_number.strip(),
                blend_number.strip(),
                notes.strip(),
                stamp,
                batch_number.strip(),
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO batches (
                batch_number, product_name, shift_name, operator_id,
                split_batch_number, run_number, blend_number, notes, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?)
            """,
            (
                batch_number.strip(),
                product_name.strip(),
                shift_name.strip(),
                operator_id.strip(),
                split_batch_number.strip(),
                run_number.strip(),
                blend_number.strip(),
                notes.strip(),
                stamp,
                stamp,
            ),
        )
    conn.commit()
    conn.close()
    return row is not None


def get_batch(batch_number: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM batches WHERE batch_number = ?", (batch_number.strip(),))
    row = cur.fetchone()
    conn.close()
    return row


def list_batches(limit: int = 50):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM batches ORDER BY updated_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def touch_batch(batch_number: str, status: Optional[str] = None) -> None:
    conn = get_conn()
    cur = conn.cursor()
    if status:
        cur.execute(
            "UPDATE batches SET updated_at = ?, status = ? WHERE batch_number = ?",
            (now_stamp(), status, batch_number),
        )
    else:
        cur.execute(
            "UPDATE batches SET updated_at = ? WHERE batch_number = ?",
            (now_stamp(), batch_number),
        )
    conn.commit()
    conn.close()


def close_batch(batch_number: str) -> None:
    touch_batch(batch_number, "Complete")


def insert_extraction(employee: str, data: dict) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO extraction_entries (
            batch_number, employee, operator_initials, entry_date, entry_time, start_time, stop_time, location,
            time_on_pipe_or_pile, psf1_speed, psf1_load, psf1_blowback,
            psf2_speed, psf2_load, psf2_blowback,
            press_speed, press_load, press_blowback,
            pressate_ri, chip_bin_steam, chip_chute_temp, notes, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("batch_number", ""),
            employee,
            data.get("operator_initials", ""),
            data.get("entry_date", ""),
            data.get("entry_time", ""),
            data.get("start_time", ""),
            data.get("stop_time", ""),
            data.get("location", ""),
            data.get("time_on_pipe_or_pile", ""),
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
            data.get("notes", ""),
            now_stamp(),
        ),
    )
    conn.commit()
    conn.close()
    if data.get("batch_number"):
        touch_batch(data["batch_number"])


def insert_filtration(employee: str, data: dict) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO filtration_entries (
            batch_number, employee, operator_initials, entry_date, clarification_sequential_no,
            retentate_flow_set_point, zero_refract, startup_time, shutdown_time,
            row1_time, row1_feed_ri, row1_retentate_ri, row1_permeate_ri, row1_perm_flow_c, row1_perm_flow_d,
            row2_time, row2_feed_ri, row2_retentate_ri, row2_permeate_ri, row2_perm_flow_c, row2_perm_flow_d,
            row3_time, row3_feed_ri, row3_retentate_ri, row3_permeate_ri, row3_perm_flow_c, row3_perm_flow_d,
            dia_row1_time, dia_row1_feed_ri, dia_row1_retentate_ri, dia_row1_permeate_ri,
            dia_row2_time, dia_row2_feed_ri, dia_row2_retentate_ri, dia_row2_permeate_ri,
            notes, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("batch_number", ""),
            employee,
            data.get("operator_initials", ""),
            data.get("entry_date", ""),
            data.get("clarification_sequential_no", ""),
            data.get("retentate_flow_set_point", ""),
            data.get("zero_refract", ""),
            data.get("startup_time", ""),
            data.get("shutdown_time", ""),
            data.get("row1_time", ""),
            data.get("row1_feed_ri", ""),
            data.get("row1_retentate_ri", ""),
            data.get("row1_permeate_ri", ""),
            data.get("row1_perm_flow_c", ""),
            data.get("row1_perm_flow_d", ""),
            data.get("row2_time", ""),
            data.get("row2_feed_ri", ""),
            data.get("row2_retentate_ri", ""),
            data.get("row2_permeate_ri", ""),
            data.get("row2_perm_flow_c", ""),
            data.get("row2_perm_flow_d", ""),
            data.get("row3_time", ""),
            data.get("row3_feed_ri", ""),
            data.get("row3_retentate_ri", ""),
            data.get("row3_permeate_ri", ""),
            data.get("row3_perm_flow_c", ""),
            data.get("row3_perm_flow_d", ""),
            data.get("dia_row1_time", ""),
            data.get("dia_row1_feed_ri", ""),
            data.get("dia_row1_retentate_ri", ""),
            data.get("dia_row1_permeate_ri", ""),
            data.get("dia_row2_time", ""),
            data.get("dia_row2_feed_ri", ""),
            data.get("dia_row2_retentate_ri", ""),
            data.get("dia_row2_permeate_ri", ""),
            data.get("notes", ""),
            now_stamp(),
        ),
    )
    conn.commit()
    conn.close()
    if data.get("batch_number"):
        touch_batch(data["batch_number"])


def insert_evaporation(employee: str, data: dict) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO evaporation_entries (
            batch_number, employee, operator_initials, entry_date, evaporator_no, startup_time, shutdown_time,
            feed_ri, concentrate_ri, steam_pressure, vacuum, sump_level, product_temp,
            row1_time, row1_feed_rate, row1_evap_temp, row1_vacuum, row1_concentrate_ri,
            row2_time, row2_feed_rate, row2_evap_temp, row2_vacuum, row2_concentrate_ri,
            row3_time, row3_feed_rate, row3_evap_temp, row3_vacuum, row3_concentrate_ri,
            notes, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["batch_number"],
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
            data.get("row1_time", ""),
            data.get("row1_feed_rate", ""),
            data.get("row1_evap_temp", ""),
            data.get("row1_vacuum", ""),
            data.get("row1_concentrate_ri", ""),
            data.get("row2_time", ""),
            data.get("row2_feed_rate", ""),
            data.get("row2_evap_temp", ""),
            data.get("row2_vacuum", ""),
            data.get("row2_concentrate_ri", ""),
            data.get("row3_time", ""),
            data.get("row3_feed_rate", ""),
            data.get("row3_evap_temp", ""),
            data.get("row3_vacuum", ""),
            data.get("row3_concentrate_ri", ""),
            data.get("notes", ""),
            now_stamp(),
        ),
    )
    conn.commit()
    conn.close()
    touch_batch(data["batch_number"])


def recent_activity(limit: int = 40, hours: Optional[int] = None):
    conn = get_conn()
    cur = conn.cursor()
    where_clause = ""
    params = []
    if hours is not None:
        cutoff = datetime.now().timestamp() - (hours * 3600)
        where_clause = "WHERE datetime(created_at) >= datetime(?, 'unixepoch')"
        params.append(int(cutoff))
    cur.execute(
        f"""
        SELECT created_at, batch_number, employee, operator_initials, entry_date, 'Extraction' AS stage,
               COALESCE(location, '') || CASE WHEN COALESCE(pressate_ri, '') <> '' THEN ' | Pressate RI: ' || pressate_ri ELSE '' END AS summary,
               notes
        FROM extraction_entries
        {where_clause}
        UNION ALL
        SELECT created_at, batch_number, employee, operator_initials, entry_date, 'Filtration' AS stage,
               COALESCE(clarification_sequential_no, '') || CASE WHEN COALESCE(retentate_flow_set_point, '') <> '' THEN ' | Set Point: ' || retentate_flow_set_point ELSE '' END AS summary,
               notes
        FROM filtration_entries
        {where_clause}
        UNION ALL
        SELECT created_at, batch_number, employee, operator_initials, entry_date, 'Evaporation' AS stage,
               COALESCE(evaporator_no, '') || CASE WHEN COALESCE(concentrate_ri, '') <> '' THEN ' | Concentrate RI: ' || concentrate_ri ELSE '' END AS summary,
               notes
        FROM evaporation_entries
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (*params, *params, *params, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def batch_history(batch_number: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT created_at, employee, 'Extraction' AS stage,
               'Location: ' || COALESCE(location, '') || ' | Pressate RI: ' || COALESCE(pressate_ri, '') || ' | Notes: ' || COALESCE(notes, '') AS details
        FROM extraction_entries WHERE batch_number = ?
        UNION ALL
        SELECT created_at, employee, 'Filtration' AS stage,
               'Seq No: ' || COALESCE(clarification_sequential_no, '') || ' | Set Point: ' || COALESCE(retentate_flow_set_point, '') || ' | Notes: ' || COALESCE(notes, '') AS details
        FROM filtration_entries WHERE batch_number = ?
        UNION ALL
        SELECT created_at, employee, 'Evaporation' AS stage,
               'Evaporator: ' || COALESCE(evaporator_no, '') || ' | Concentrate RI: ' || COALESCE(concentrate_ri, '') || ' | Notes: ' || COALESCE(notes, '') AS details
        FROM evaporation_entries WHERE batch_number = ?
        ORDER BY created_at DESC
        """,
        (batch_number, batch_number, batch_number),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def plant_status():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT batch_number, status, updated_at AS last_seen FROM batches ORDER BY updated_at DESC")
    rows = cur.fetchall()
    conn.close()
    return rows
