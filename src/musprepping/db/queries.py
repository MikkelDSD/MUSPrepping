"""Read and write queries. Every SQL statement in the app lives here.

Functions take `conn` first and return plain dicts. Writes do not commit; the
caller (a route handler or the ingest loader) owns the transaction.
Join aliases: `e` employees, `s` strengths, `es` employee_strengths,
`h` highlights, `w` weaknesses, `ms` mus_sessions.
"""

import sqlite3
from typing import Any

MUS_FIELDS = ("scheduled_for", "status", "praise_text", "tone", "development_goals", "employee_wishes", "boss_notes")
MUS_STATUSES = ("planlagt", "afholdt")


# --- Employees -----------------------------------------------------------------

def get_employees(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """All employees, with their strengths, highlight count and next planned MUS."""
    employees = [dict(r) for r in conn.execute("SELECT * FROM employees ORDER BY name COLLATE NOCASE")]
    for e in employees:
        e["strengths"] = get_employee_strengths(conn, e["id"])
        e["highlight_count"] = conn.execute(
            "SELECT COUNT(*) FROM highlights WHERE employee_id = ?", (e["id"],)
        ).fetchone()[0]
        e["next_mus"] = get_next_session(conn, e["id"])
    return employees


def get_employee(conn: sqlite3.Connection, employee_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
    return dict(row) if row else None


def find_employee_by_name(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM employees WHERE name = ? COLLATE NOCASE ORDER BY id LIMIT 1", (name.strip(),)
    ).fetchone()
    return dict(row) if row else None


def insert_employee(
    conn: sqlite3.Connection,
    name: str,
    role: str = "",
    team: str = "",
    start_date: str | None = None,
    personal_note: str = "",
) -> int:
    cur = conn.execute(
        "INSERT INTO employees (name, role, team, start_date, personal_note) VALUES (?, ?, ?, ?, ?)",
        (name, role, team, start_date, personal_note),
    )
    return cur.lastrowid


def update_employee(
    conn: sqlite3.Connection,
    employee_id: int,
    name: str,
    role: str = "",
    team: str = "",
    start_date: str | None = None,
    personal_note: str = "",
) -> None:
    conn.execute(
        "UPDATE employees SET name = ?, role = ?, team = ?, start_date = ?, personal_note = ? WHERE id = ?",
        (name, role, team, start_date, personal_note, employee_id),
    )


def delete_employee(conn: sqlite3.Connection, employee_id: int) -> None:
    """Also removes strengths, highlights and sessions (ON DELETE CASCADE)."""
    conn.execute("DELETE FROM employees WHERE id = ?", (employee_id,))


# --- Strengths -----------------------------------------------------------------

def get_strengths(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM strengths ORDER BY id")]


def get_strengths_by_ids(conn: sqlite3.Connection, strength_ids: list[int]) -> list[dict[str, Any]]:
    ids = [int(i) for i in strength_ids]
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    return [dict(r) for r in conn.execute(f"SELECT * FROM strengths WHERE id IN ({marks}) ORDER BY id", ids)]


def get_employee_strengths(conn: sqlite3.Connection, employee_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT s.* FROM strengths s
        JOIN employee_strengths es ON es.strength_id = s.id
        WHERE es.employee_id = ?
        ORDER BY s.id
        """,
        (employee_id,),
    )
    return [dict(r) for r in rows]


def toggle_employee_strength(conn: sqlite3.Connection, employee_id: int, strength_id: int) -> bool:
    """Add the strength if missing, remove it if present. Returns whether it is now selected."""
    deleted = conn.execute(
        "DELETE FROM employee_strengths WHERE employee_id = ? AND strength_id = ?",
        (employee_id, strength_id),
    ).rowcount
    if not deleted:
        conn.execute(
            "INSERT INTO employee_strengths (employee_id, strength_id) VALUES (?, ?)",
            (employee_id, strength_id),
        )
    return not deleted


def get_strength_keys(conn: sqlite3.Connection) -> set[str]:
    return {r["key"] for r in conn.execute("SELECT key FROM strengths")}


def add_employee_strength_by_key(conn: sqlite3.Connection, employee_id: int, key: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO employee_strengths (employee_id, strength_id)
        SELECT ?, s.id FROM strengths s WHERE s.key = ?
        """,
        (employee_id, key),
    )


# --- Highlights ----------------------------------------------------------------

def get_highlights(conn: sqlite3.Connection, employee_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM highlights WHERE employee_id = ? ORDER BY happened_on DESC, id DESC",
        (employee_id,),
    )
    return [dict(r) for r in rows]


def get_highlights_by_ids(conn: sqlite3.Connection, employee_id: int, highlight_ids: list[int]) -> list[dict[str, Any]]:
    """Only returns highlights that belong to the employee."""
    ids = [int(i) for i in highlight_ids]
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT * FROM highlights WHERE employee_id = ? AND id IN ({marks}) ORDER BY happened_on, id",
        [employee_id, *ids],
    )
    return [dict(r) for r in rows]


def insert_highlight(
    conn: sqlite3.Connection,
    employee_id: int,
    title: str,
    description: str = "",
    happened_on: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO highlights (employee_id, title, description, happened_on) VALUES (?, ?, ?, ?)",
        (employee_id, title, description, happened_on),
    )
    return cur.lastrowid


def delete_highlight(conn: sqlite3.Connection, highlight_id: int) -> bool:
    return conn.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,)).rowcount > 0


# --- Weaknesses ----------------------------------------------------------------

def get_weaknesses(conn: sqlite3.Connection, employee_id: int) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM weaknesses WHERE employee_id = ? ORDER BY id DESC", (employee_id,))
    return [dict(r) for r in rows]


def insert_weakness(conn: sqlite3.Connection, employee_id: int, title: str, emoji: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO weaknesses (employee_id, title, emoji) VALUES (?, ?, ?)",
        (employee_id, title, emoji),
    )
    return cur.lastrowid


def delete_weakness(conn: sqlite3.Connection, weakness_id: int) -> bool:
    return conn.execute("DELETE FROM weaknesses WHERE id = ?", (weakness_id,)).rowcount > 0


# --- MUS sessions --------------------------------------------------------------

def get_sessions(conn: sqlite3.Connection, employee_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM mus_sessions WHERE employee_id = ? ORDER BY scheduled_for DESC, id DESC",
        (employee_id,),
    )
    return [dict(r) for r in rows]


def get_next_session(conn: sqlite3.Connection, employee_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM mus_sessions
        WHERE employee_id = ? AND status = 'planlagt'
        ORDER BY scheduled_for, id LIMIT 1
        """,
        (employee_id,),
    ).fetchone()
    return dict(row) if row else None


def get_upcoming_sessions(conn: sqlite3.Connection, limit: int = 6) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT ms.*, e.name AS employee_name, e.role AS employee_role
        FROM mus_sessions ms
        JOIN employees e ON e.id = ms.employee_id
        WHERE ms.status = 'planlagt'
        ORDER BY ms.scheduled_for, ms.id
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(r) for r in rows]


def get_session(conn: sqlite3.Connection, session_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM mus_sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def insert_session(conn: sqlite3.Connection, employee_id: int, scheduled_for: str) -> int:
    cur = conn.execute(
        "INSERT INTO mus_sessions (employee_id, scheduled_for) VALUES (?, ?)",
        (employee_id, scheduled_for),
    )
    return cur.lastrowid


def update_session(conn: sqlite3.Connection, session_id: int, **fields: str) -> None:
    """Update any subset of MUS_FIELDS; other keys are ignored."""
    updates = {k: v for k, v in fields.items() if k in MUS_FIELDS}
    if not updates:
        return
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(f"UPDATE mus_sessions SET {assignments} WHERE id = ?", [*updates.values(), session_id])


def delete_session(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute("DELETE FROM mus_sessions WHERE id = ?", (session_id,))


# --- Derived -------------------------------------------------------------------

def prep_progress(employee: dict[str, Any], session: dict[str, Any] | None) -> dict[str, Any]:
    """The four prep steps behind the dashboard's progress ring. Pure – no SQL.

    `employee` is a row from get_employees() (needs `strengths` and `highlight_count`).
    """
    steps = {
        "styrker": bool(employee.get("strengths")),
        "hoejdepunkter": bool(employee.get("highlight_count")),
        "ros": bool(session and session["praise_text"].strip()),
        "udvikling": bool(session and session["development_goals"].strip()),
    }
    done = sum(steps.values())
    return {"steps": steps, "done": done, "total": len(steps), "percent": round(100 * done / len(steps))}
