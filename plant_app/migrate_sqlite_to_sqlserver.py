"""One-time importer from the local SQLite plant.db into SQL Server."""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import pyodbc

from db import build_sql_connection_string, resolve_sql_database


BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "plant.db"

TABLE_ORDER = [
    "users",
    "production_runs",
    "extraction_entries",
    "filtration_entries",
    "filtration_rows",
    "evaporation_entries",
    "evaporation_rows",
    "audit_log",
    "sheet_entries",
    "field_change_log",
]

IDENTITY_TABLES = set(TABLE_ORDER)


def sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sqlserver_conn():
    explicit_database = os.getenv("PLANT_APP_SQL_DATABASE", "").strip()
    target_database = explicit_database or resolve_sql_database()
    return pyodbc.connect(
        build_sql_connection_string(target_database)
    )


def sqlite_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return [row["name"] for row in cur.fetchall()]


def sqlserver_columns(cur, table: str) -> list[str]:
    cur.execute("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
    """, (table,))
    return [row[0] for row in cur.fetchall()]


def table_row_count(cur, table: str) -> int:
    cur.execute(f"SELECT COUNT(*) FROM dbo.{table}")
    return int(cur.fetchone()[0])


def clear_tables(cur) -> None:
    for table in reversed(TABLE_ORDER):
        cur.execute(f"DELETE FROM dbo.{table}")


def import_table(sqlite_cur: sqlite3.Cursor, sqlserver_cur, table: str) -> int:
    source_columns = sqlite_columns(sqlite_cur, table)
    target_columns = sqlserver_columns(sqlserver_cur, table)
    common_columns = [column for column in target_columns if column in source_columns]

    if not common_columns:
        return 0

    quoted_columns = ", ".join(common_columns)
    placeholders = ", ".join("?" for _ in common_columns)

    sqlite_cur.execute(f"SELECT {quoted_columns} FROM {table}")
    rows = sqlite_cur.fetchall()
    if not rows:
        return 0

    if table in IDENTITY_TABLES and "id" in common_columns:
        sqlserver_cur.execute(f"SET IDENTITY_INSERT dbo.{table} ON")

    sqlserver_cur.fast_executemany = True
    sqlserver_cur.executemany(
        f"INSERT INTO dbo.{table} ({quoted_columns}) VALUES ({placeholders})",
        [tuple(row[column] for column in common_columns) for row in rows],
    )

    if table in IDENTITY_TABLES and "id" in common_columns:
        sqlserver_cur.execute(f"SET IDENTITY_INSERT dbo.{table} OFF")

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import plant.db SQLite data into SQL Server.")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete existing SQL Server rows before importing.",
    )
    args = parser.parse_args()

    if not SQLITE_PATH.exists():
        raise SystemExit(f"SQLite file not found: {SQLITE_PATH}")

    source = sqlite_conn()
    target = sqlserver_conn()

    try:
        source_cur = source.cursor()
        target_cur = target.cursor()

        if args.clear:
            clear_tables(target_cur)
        else:
            populated = [table for table in TABLE_ORDER if table_row_count(target_cur, table) > 0]
            if populated:
                names = ", ".join(populated)
                raise SystemExit(
                    f"SQL Server already has data in: {names}. "
                    "Re-run with --clear if you want to replace it."
                )

        imported_counts: list[tuple[str, int]] = []
        for table in TABLE_ORDER:
            count = import_table(source_cur, target_cur, table)
            imported_counts.append((table, count))

        target.commit()

        print("Import complete.")
        for table, count in imported_counts:
            print(f"{table}: {count}")
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    main()
