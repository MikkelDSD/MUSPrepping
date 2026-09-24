"""CSV ingestion: parse, validate, load.

Lets the boss bring in the team from a spreadsheet instead of typing it all.
File conventions for an inbox folder (matched by filename prefix):

- ``medarbejdere_*.csv``   columns: navn, rolle, team, ansat_siden, styrker, note
                           (styrker is a ';'-separated list of strength keys,
                           see db/schema.py STRENGTHS)
- ``hoejdepunkter_*.csv``  columns: medarbejder, titel, beskrivelse, dato
- ``mus_*.csv``            columns: medarbejder, dato

Employees are matched by name (case-insensitive), so employee files are always
loaded before the others. Dates are 'YYYY-MM-DD'; highlight dates may not be in
the future. Rows that fail validation are skipped and reported; the rest of the
file still loads.
"""

import csv
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from musprepping.db import queries

# Load order matters: highlights and sessions reference employees by name.
KINDS = ("medarbejdere", "hoejdepunkter", "mus")


@dataclass
class IngestReport:
    files: int = 0
    employees_loaded: int = 0
    highlights_loaded: int = 0
    sessions_loaded: int = 0
    rejected: list[tuple[str, int, str]] = field(default_factory=list)  # (file, line, reason)
    skipped_files: list[str] = field(default_factory=list)


def _kind(path: Path) -> str | None:
    name = path.name.lower()
    return next((k for k in KINDS if name.startswith(k + "_") or name == k + ".csv"), None)


def _parse_date(value: str | None, today: date, allow_future: bool) -> tuple[str | None, str | None]:
    """Returns (iso_date, rejection_reason). Empty input is (None, None)."""
    value = (value or "").strip()
    if not value:
        return None, None
    try:
        d = date.fromisoformat(value)
    except ValueError:
        return None, f"ugyldig dato {value!r} (forventede YYYY-MM-DD)"
    if not allow_future and d > today:
        return None, f"datoen {value!r} ligger i fremtiden"
    return d.isoformat(), None


def _employee_id(conn: sqlite3.Connection, row: dict) -> tuple[int | None, str | None]:
    name = (row.get("medarbejder") or "").strip()
    if not name:
        return None, "mangler medarbejder"
    employee = queries.find_employee_by_name(conn, name)
    if employee is None:
        return None, f"ukendt medarbejder {name!r}"
    return employee["id"], None


def _load_employee(conn: sqlite3.Connection, row: dict, today: date, strength_keys: set[str]) -> str | None:
    name = (row.get("navn") or "").strip()
    if not name:
        return "mangler navn"
    if queries.find_employee_by_name(conn, name):
        return f"{name!r} findes allerede"
    start_date, reason = _parse_date(row.get("ansat_siden"), today, allow_future=False)
    if reason:
        return reason
    keys = [k.strip() for k in (row.get("styrker") or "").split(";") if k.strip()]
    unknown = [k for k in keys if k not in strength_keys]
    if unknown:
        return f"ukendte styrker {', '.join(unknown)}"
    employee_id = queries.insert_employee(
        conn,
        name,
        (row.get("rolle") or "").strip(),
        (row.get("team") or "").strip(),
        start_date,
        (row.get("note") or "").strip(),
    )
    for key in keys:
        queries.add_employee_strength_by_key(conn, employee_id, key)
    return None


def _load_highlight(conn: sqlite3.Connection, row: dict, today: date) -> str | None:
    employee_id, reason = _employee_id(conn, row)
    if reason:
        return reason
    title = (row.get("titel") or "").strip()
    if not title:
        return "mangler titel"
    happened_on, reason = _parse_date(row.get("dato"), today, allow_future=False)
    if reason:
        return reason
    queries.insert_highlight(conn, employee_id, title, (row.get("beskrivelse") or "").strip(), happened_on)
    return None


def _load_session(conn: sqlite3.Connection, row: dict, today: date) -> str | None:
    employee_id, reason = _employee_id(conn, row)
    if reason:
        return reason
    scheduled_for, reason = _parse_date(row.get("dato"), today, allow_future=True)
    if reason:
        return reason
    if scheduled_for is None:
        return "mangler dato"
    queries.insert_session(conn, employee_id, scheduled_for)
    return None


def ingest_file(conn: sqlite3.Connection, path: Path, report: IngestReport, today: date) -> None:
    kind = _kind(path)
    if kind is None:
        report.skipped_files.append(path.name)
        return
    report.files += 1
    strength_keys = queries.get_strength_keys(conn)

    # utf-8-sig: Excel's "CSV UTF-8" export starts with a BOM.
    with path.open(newline="", encoding="utf-8-sig") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):  # header is line 1
            if kind == "medarbejdere":
                reason = _load_employee(conn, row, today, strength_keys)
            elif kind == "hoejdepunkter":
                reason = _load_highlight(conn, row, today)
            else:
                reason = _load_session(conn, row, today)

            if reason is not None:
                report.rejected.append((path.name, line_no, reason))
            elif kind == "medarbejdere":
                report.employees_loaded += 1
            elif kind == "hoejdepunkter":
                report.highlights_loaded += 1
            else:
                report.sessions_loaded += 1
    conn.commit()


def ingest_path(conn: sqlite3.Connection, path: Path, today: date | None = None) -> IngestReport:
    """Ingest a CSV file, or every CSV in a folder (employees first, then by name)."""
    today = today or date.today()
    report = IngestReport()
    if path.is_dir():
        files = sorted(path.glob("*.csv"), key=lambda p: (KINDS.index(_kind(p)) if _kind(p) else len(KINDS), p.name))
    else:
        files = [path]
    for f in files:
        ingest_file(conn, f, report, today)
    return report
