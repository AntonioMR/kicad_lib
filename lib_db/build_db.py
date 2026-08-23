#!/usr/bin/env python3
"""Regenerate lib/lib_db/catalog.sqlite from the CSV files in lib/lib_db/source/.

Each CSV becomes one SQLite table (all columns as TEXT, plus a computed
IPN_Assigned column) and a "<table>_released" view exposing only rows whose
IPN has actually been assigned.

A component is only usable in a schematic once it has a real IPN. The single
unassigned placeholder is a "-????" suffix (e.g. "IPN_C-????"); any other
suffix counts as assigned. "Approved By"/"Approved On" are production-
readiness metadata and are NOT part of this gate.

The CSV files are the source of truth (reviewed in PRs); this script and
its output are regenerated, not hand-edited.

Usage: python3 build_db.py
"""
import csv
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_DIR = HERE / "source"
DB_PATH = HERE / "catalog.sqlite"
REQUIRED_COLUMNS = {"IPN", "Symbol", "Footprint"}
UNASSIGNED_SUFFIX = "-????"


def ipn_assigned(ipn):
    """True unless the IPN carries the unassigned placeholder suffix '-????'."""
    return bool(ipn) and not ipn.endswith(UNASSIGNED_SUFFIX)


def load_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def build_table(conn, table, columns, rows):
    missing = REQUIRED_COLUMNS - set(columns)
    if missing:
        raise ValueError(f"{table}: missing required column(s): {', '.join(sorted(missing))}")

    all_columns = columns + ["IPN_Assigned"]
    quoted_cols = ", ".join(f'"{c}" TEXT' for c in all_columns)
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.execute(f'CREATE TABLE "{table}" ({quoted_cols})')

    placeholders = ", ".join("?" for _ in all_columns)
    values = []
    for row in rows:
        record = [row.get(c, "") for c in columns]
        record.append("1" if ipn_assigned(row.get("IPN", "")) else "0")
        values.append(record)
    conn.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', values)

    conn.execute(f'DROP VIEW IF EXISTS "{table}_released"')
    conn.execute(
        f'CREATE VIEW "{table}_released" AS '
        f'SELECT * FROM "{table}" WHERE "IPN_Assigned" = \'1\''
    )
    return sum(1 for r in values if r[-1] == "1")


def main():
    csv_files = sorted(SOURCE_DIR.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {SOURCE_DIR}", file=sys.stderr)
        return 1

    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        for csv_path in csv_files:
            table = csv_path.stem
            columns, rows = load_csv(csv_path)
            released = build_table(conn, table, columns, rows)
            print(f"{table}: {len(rows)} row(s), {released} with an assigned IPN")
        conn.commit()
    finally:
        conn.close()

    print(f"Wrote {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
