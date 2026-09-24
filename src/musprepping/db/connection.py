"""SQLite connection handling (stdlib sqlite3, no ORM)."""

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_FILENAME = "musprepping.db"


def db_path() -> Path:
    """Database file location: $MUSPREPPING_DB if set, else ./musprepping.db."""
    return Path(os.environ.get("MUSPREPPING_DB", DEFAULT_DB_FILENAME))


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(
        path if path is not None else db_path(), check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
