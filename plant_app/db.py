import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "plant.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            employee TEXT NOT NULL,
            batch_number TEXT NOT NULL,
            machine_id INTEGER NOT NULL,
            machine_name TEXT NOT NULL,
            blowback TEXT,
            pressate_ri TEXT,
            pressate_flow TEXT,
            chip_bin_steam TEXT,
            chip_chute_temp TEXT
        );
        """
    )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_entries_batch ON entries(batch_number);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_entries_time ON entries(created_at);")

    conn.commit()
    conn.close()


def insert_entry(
    employee: str,
    batch_number: str,
    machine_id: int,
    machine_name: str,
    blowback: str,
    pressate_ri: str,
    pressate_flow: str,
    chip_bin_steam: str,
    chip_chute_temp: str,
) -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO entries (
            created_at, employee, batch_number, machine_id, machine_name,
            blowback, pressate_ri, pressate_flow, chip_bin_steam, chip_chute_temp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            datetime.now().isoformat(timespec="seconds"),
            employee,
            batch_number,
            machine_id,
            machine_name,
            blowback,
            pressate_ri,
            pressate_flow,
            chip_bin_steam,
            chip_chute_temp,
        ),
    )

    conn.commit()
    conn.close()


def recent_batches(limit: int = 25):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            batch_number,
            MAX(created_at) AS last_seen,
            COUNT(*) AS entry_count
        FROM entries
        GROUP BY batch_number
        ORDER BY last_seen DESC
        LIMIT ?;
        """,
        (limit,),
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def batch_entries(batch_number: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM entries
        WHERE batch_number = ?
        ORDER BY created_at DESC;
        """,
        (batch_number,),
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def plant_status():
    """
    Current stage = machine_name from the most recent entry for each batch.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT e.batch_number,
               e.machine_name AS current_stage,
               e.created_at AS last_seen
        FROM entries e
        JOIN (
            SELECT batch_number, MAX(created_at) AS max_time
            FROM entries
            GROUP BY batch_number
        ) x
        ON e.batch_number = x.batch_number AND e.created_at = x.max_time
        ORDER BY e.created_at DESC;
        """
    )

    rows = cur.fetchall()
    conn.close()
    return rows