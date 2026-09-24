"""Command-line entry points: `uv run ingest` and `uv run seed`."""

import argparse
import sys
from pathlib import Path

from musprepping.db.connection import connect
from musprepping.db.schema import init_db, reset_db
from musprepping.ingest.loader import IngestReport, ingest_path

DEFAULT_INBOX = Path("data") / "inbox"


def _print_report(report: IngestReport) -> None:
    print(f"Files processed:     {report.files}")
    print(f"Employees loaded:    {report.employees_loaded}")
    print(f"Highlights loaded:   {report.highlights_loaded}")
    print(f"MUS sessions loaded: {report.sessions_loaded}")
    if report.skipped_files:
        print(f"Skipped (unrecognized filename): {', '.join(report.skipped_files)}")
    if report.rejected:
        print(f"Rejected rows:       {len(report.rejected)}")
        for file, line, reason in report.rejected[:20]:
            print(f"  {file}:{line}  {reason}")
        if len(report.rejected) > 20:
            print(f"  ... and {len(report.rejected) - 20} more")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest employee/highlight/MUS CSV files.")
    parser.add_argument(
        "path", nargs="?", default=str(DEFAULT_INBOX),
        help="CSV file or folder of CSVs (default: data/inbox)",
    )
    args = parser.parse_args(argv)
    path = Path(args.path)
    if not path.exists():
        print(f"[FAIL] path not found: {path}")
        return 1

    conn = connect()
    init_db(conn)
    report = ingest_path(conn, path)
    _print_report(report)
    conn.close()
    return 0


def seed() -> int:
    """Rebuild the database from scratch and ingest data/inbox."""
    if not DEFAULT_INBOX.exists():
        print(f"[FAIL] {DEFAULT_INBOX} not found — run from the repo root.")
        return 1
    conn = connect()
    reset_db(conn)
    report = ingest_path(conn, DEFAULT_INBOX)
    _print_report(report)
    conn.close()
    print("[OK] database seeded.")
    return 0


def main_entry() -> None:  # console script wrapper
    sys.exit(main())


def seed_entry() -> None:  # console script wrapper
    sys.exit(seed())
