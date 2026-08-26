#!/usr/bin/env python3
"""Regenerate lib/lib_db/ipn_registry.csv from the CSV files in lib/lib_db/source/.

Collects every row across all source/*.csv families that has an assigned IPN
(any suffix other than the "-????" placeholder), keeps only the common
columns (IPN, Family, Part Number, Description, Value, Symbol, Footprint,
Manufacturer, Manufacturer Part Number), and writes them sorted by IPN.

Sorting by IPN groups same-prefix rows together regardless of which family
they come from, which is what makes this file useful for finding the next
free number for a given prefix — the Family column is for locating the
component's symbol library, not for grouping the IPN sequence.

The CSV files in source/ are the source of truth (reviewed in PRs); this
script and its output are regenerated, not hand-edited.

An IPN is a permanent identifier: once assigned it can never be reassigned
to a different part. If ipn_registry.csv already exists, every IPN it
already carries is checked against the row about to replace it — Part
Number, Value, Manufacturer and Manufacturer Part Number must match
exactly. A mismatch aborts the whole run without writing the file, since it
means an existing IPN is being pointed at a different part. Description,
Symbol and Footprint are exempt from this check and may be freely updated
(e.g. a corrected footprint, a reworded description) — new IPNs are always
accepted.

Usage: python3 build_ipn_registry.py
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_DIR = HERE / "source"
REGISTRY_PATH = HERE / "ipn_registry.csv"
UNASSIGNED_SUFFIX = "-????"
COMMON_COLUMNS = [
    "Part Number",
    "Description",
    "Value",
    "Symbol",
    "Footprint",
    "Manufacturer",
    "Manufacturer Part Number",
]
OUTPUT_COLUMNS = ["IPN", "Family"] + COMMON_COLUMNS
IMMUTABLE_COLUMNS = [
    "Part Number",
    "Value",
    "Manufacturer",
    "Manufacturer Part Number",
]


def ipn_assigned(ipn):
    """True unless the IPN carries the unassigned placeholder suffix '-????'."""
    return bool(ipn) and not ipn.endswith(UNASSIGNED_SUFFIX)


def load_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def load_existing_registry(path):
    """Existing IPN -> row dict, or {} if no registry has been generated yet."""
    if not path.exists():
        return {}
    _, rows = load_csv(path)
    return {row["IPN"]: row for row in rows if row.get("IPN")}


def find_ipn_conflicts(entries, existing):
    """Entries whose IPN was already registered to a different part.

    Returns a list of (entry, existing_row, changed_columns) tuples.
    """
    conflicts = []
    for entry in entries:
        old = existing.get(entry["IPN"])
        if old is None:
            continue
        changed = [c for c in IMMUTABLE_COLUMNS if old.get(c, "") != entry.get(c, "")]
        if changed:
            conflicts.append((entry, old, changed))
    return conflicts


def main():
    csv_files = sorted(SOURCE_DIR.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {SOURCE_DIR}", file=sys.stderr)
        return 1

    required = {"IPN"} | set(COMMON_COLUMNS)
    entries = []
    for csv_path in csv_files:
        family = csv_path.stem
        columns, rows = load_csv(csv_path)
        missing = required - set(columns)
        if missing:
            raise ValueError(f"{family}: missing required column(s): {', '.join(sorted(missing))}")

        for row in rows:
            if not ipn_assigned(row.get("IPN", "")):
                continue
            entry = {"IPN": row.get("IPN", ""), "Family": family}
            entry.update({c: row.get(c, "") for c in COMMON_COLUMNS})
            entries.append(entry)

    entries.sort(key=lambda e: e["IPN"])

    existing = load_existing_registry(REGISTRY_PATH)
    conflicts = find_ipn_conflicts(entries, existing)
    if conflicts:
        print("IPN conflict: the following IPN(s) are already registered to a "
              "different part and cannot be reassigned:", file=sys.stderr)
        for entry, old, changed in conflicts:
            print(f"\n  IPN {entry['IPN']} ({entry['Family']}):", file=sys.stderr)
            for column in changed:
                print(f"    {column}: registered {old.get(column, '')!r} "
                      f"!= new {entry.get(column, '')!r}", file=sys.stderr)
        print(f"\nAborted — {REGISTRY_PATH} was not modified.", file=sys.stderr)
        return 1

    with REGISTRY_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(entries)

    print(f"{len(entries)} assigned IPN(s) across {len(csv_files)} family file(s)")
    print(f"Wrote {REGISTRY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
