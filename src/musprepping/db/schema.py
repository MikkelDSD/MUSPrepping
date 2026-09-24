"""Schema and reference data.

Dates are stored as 'YYYY-MM-DD' strings; created_at columns as naive local time
'YYYY-MM-DD HH:MM:SS'.
"""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT '',
    team          TEXT NOT NULL DEFAULT '',
    start_date    TEXT,
    personal_note TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS strengths (
    id       INTEGER PRIMARY KEY,
    key      TEXT NOT NULL UNIQUE,
    label    TEXT NOT NULL,
    category TEXT NOT NULL,
    emoji    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS employee_strengths (
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    strength_id INTEGER NOT NULL REFERENCES strengths(id) ON DELETE CASCADE,
    PRIMARY KEY (employee_id, strength_id)
);

CREATE TABLE IF NOT EXISTS highlights (
    id          INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    happened_on TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS mus_sessions (
    id                INTEGER PRIMARY KEY,
    employee_id       INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    scheduled_for     TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'planlagt' CHECK (status IN ('planlagt', 'afholdt')),
    praise_text       TEXT NOT NULL DEFAULT '',
    tone              TEXT NOT NULL DEFAULT 'varm',
    development_goals TEXT NOT NULL DEFAULT '',
    employee_wishes   TEXT NOT NULL DEFAULT '',
    boss_notes        TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_highlights_employee ON highlights(employee_id);
CREATE INDEX IF NOT EXISTS idx_mus_sessions_employee ON mus_sessions(employee_id);

CREATE TABLE IF NOT EXISTS children (
    id          INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    birth_year  INTEGER,
    interests   TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_children_employee ON children(employee_id);
"""

# The strengths catalogue. key is the machine-readable name used in CSVs and by
# praise.py to look up phrases; keep the two in sync when adding one.
STRENGTHS = [
    (1, "samarbejde", "Samarbejde", "Relationer", "🤝"),
    (2, "hjaelpsomhed", "Hjælpsomhed", "Relationer", "💛"),
    (3, "positiv_energi", "Positiv energi", "Relationer", "☀️"),
    (4, "humor", "Humor", "Relationer", "😄"),
    (5, "faglighed", "Faglighed", "Faglighed", "🎓"),
    (6, "laeringslyst", "Læringslyst", "Faglighed", "🌱"),
    (7, "kreativitet", "Kreativitet", "Faglighed", "🎨"),
    (8, "overblik", "Overblik", "Faglighed", "🧭"),
    (9, "initiativ", "Initiativ", "Drivkraft", "🚀"),
    (10, "paalidelighed", "Pålidelighed", "Drivkraft", "⚓"),
    (11, "mod", "Mod", "Drivkraft", "🦁"),
    (12, "kundefokus", "Kundefokus", "Drivkraft", "🎯"),
    (13, "ledelse", "Går forrest", "Drivkraft", "🌟"),
]


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and upsert reference data. Safe to call repeatedly; edits to
    STRENGTHS reach existing databases on the next start."""
    conn.executescript(SCHEMA)
    conn.executemany(
        """
        INSERT INTO strengths (id, key, label, category, emoji) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            key = excluded.key, label = excluded.label,
            category = excluded.category, emoji = excluded.emoji
        """,
        STRENGTHS,
    )
    conn.commit()


def reset_db(conn: sqlite3.Connection) -> None:
    """Drop all data and recreate the schema (used by `uv run seed`)."""
    conn.executescript(
        """
        DROP TABLE IF EXISTS children;
        DROP TABLE IF EXISTS mus_sessions;
        DROP TABLE IF EXISTS highlights;
        DROP TABLE IF EXISTS employee_strengths;
        DROP TABLE IF EXISTS strengths;
        DROP TABLE IF EXISTS employees;
        """
    )
    init_db(conn)
