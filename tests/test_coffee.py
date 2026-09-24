"""Coffee preferences: reference data, ratings, migration, API and the ambient CSS."""

import sqlite3

import pytest

from musprepping.api.main import FRONTEND_DIR, app
from musprepping.db import queries
from musprepping.db.connection import connect
from musprepping.db.schema import init_db


@pytest.fixture
def conn(tmp_path):
    conn = connect(tmp_path / "coffee-db-test.db")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "coffee-api-test.db"
    monkeypatch.setenv("MUSPREPPING_DB", str(path))
    conn = connect(path)
    init_db(conn)
    queries.insert_employee(conn, "Sofie Lindberg", "Projektleder", "Digital")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def client(db):
    return app.test_client()


# --- Reference data and DB behaviour --------------------------------------------

def test_coffee_keys_match_office_machine(conn):
    keys = {c["key"] for c in queries.get_coffees(conn)}
    assert keys == {"espresso", "lungo", "cappuccino", "latte", "americano", "hot_water"}


def test_new_favorite_demotes_old_one(conn):
    employee_id = queries.insert_employee(conn, "Ahmad")
    queries.set_employee_coffee(conn, employee_id, 1, "favorit")
    queries.set_employee_coffee(conn, employee_id, 2, "favorit")
    profile = queries.get_coffee_profile(conn, employee_id)
    assert profile["favorite"]["id"] == 2
    assert [c["id"] for c in profile["likes"]] == [1]


def test_unique_index_rejects_second_favorite_via_direct_insert(conn):
    employee_id = queries.insert_employee(conn, "Ahmad")
    conn.execute(
        "INSERT INTO employee_coffees (employee_id, coffee_id, rating) VALUES (?, 1, 'favorit')",
        (employee_id,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO employee_coffees (employee_id, coffee_id, rating) VALUES (?, 2, 'favorit')",
            (employee_id,),
        )


def test_none_rating_deletes_the_row(conn):
    employee_id = queries.insert_employee(conn, "Ahmad")
    queries.set_employee_coffee(conn, employee_id, 1, "kan_lide")
    queries.set_employee_coffee(conn, employee_id, 1, None)
    assert conn.execute(
        "SELECT COUNT(*) FROM employee_coffees WHERE employee_id = ?", (employee_id,)
    ).fetchone()[0] == 0


def test_delete_employee_cascades_coffees(conn):
    employee_id = queries.insert_employee(conn, "Ahmad")
    queries.set_employee_coffee(conn, employee_id, 1, "favorit")
    queries.set_employee_coffee(conn, employee_id, 2, "kan_ikke_lide")
    queries.delete_employee(conn, employee_id)
    assert conn.execute("SELECT COUNT(*) FROM employee_coffees").fetchone()[0] == 0


def test_migration_adds_coffee_columns_and_keeps_data(tmp_path):
    """Hand-build the employees table as it looked before this branch, then check
    that init_db migrates it in place without losing the existing row."""
    path = tmp_path / "old-schema.db"
    old_conn = connect(path)
    old_conn.execute(
        """
        CREATE TABLE employees (
            id            INTEGER PRIMARY KEY,
            name          TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT '',
            team          TEXT NOT NULL DEFAULT '',
            start_date    TEXT,
            personal_note TEXT NOT NULL DEFAULT '',
            created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    old_conn.execute(
        "INSERT INTO employees (name, role, team, personal_note) VALUES (?, ?, ?, ?)",
        ("Sofie Lindberg", "Projektleder", "Digital", "Skarp"),
    )
    old_conn.commit()

    init_db(old_conn)

    columns = {row["name"] for row in old_conn.execute("PRAGMA table_info(employees)")}
    assert {"coffee_likes", "coffee_dislikes"}.issubset(columns)

    row = old_conn.execute("SELECT * FROM employees WHERE name = 'Sofie Lindberg'").fetchone()
    assert row["role"] == "Projektleder"
    assert row["personal_note"] == "Skarp"
    assert row["coffee_likes"] == ""
    assert row["coffee_dislikes"] == ""
    old_conn.close()


# --- API -------------------------------------------------------------------------

def test_api_coffees_list(client):
    r = client.get("/api/coffees")
    assert r.status_code == 200
    assert {c["key"] for c in r.get_json()} == {"espresso", "lungo", "cappuccino", "latte", "americano", "hot_water"}


def test_api_rate_and_clear_coffee(client):
    r = client.post("/api/employees/1/coffees", json={"coffee_id": 4, "rating": "favorit"})
    assert r.status_code == 200
    profile = r.get_json()
    assert profile["favorite"]["key"] == "latte"

    r = client.post("/api/employees/1/coffees", json={"coffee_id": 4, "rating": None})
    assert r.status_code == 200
    assert r.get_json()["favorite"] is None


def test_api_rating_demotes_old_favorite_visibly(client):
    client.post("/api/employees/1/coffees", json={"coffee_id": 1, "rating": "favorit"})
    r = client.post("/api/employees/1/coffees", json={"coffee_id": 2, "rating": "favorit"})
    profile = r.get_json()
    assert profile["favorite"]["key"] == "lungo"
    assert [c["key"] for c in profile["likes"]] == ["espresso"]


def test_api_unknown_coffee_and_bad_rating_are_400(client):
    r = client.post("/api/employees/1/coffees", json={"coffee_id": 999, "rating": "favorit"})
    assert r.status_code == 400
    assert "kaffe" in r.get_json()["detail"]

    r = client.post("/api/employees/1/coffees", json={"coffee_id": 1, "rating": "elsker"})
    assert r.status_code == 400
    assert "vurdering" in r.get_json()["detail"]


def test_api_unknown_employee_is_404(client):
    r = client.post("/api/employees/999/coffees", json={"coffee_id": 1, "rating": "favorit"})
    assert r.status_code == 404


def test_api_coffee_free_text_saved_and_not_wiped_by_put(client):
    r = client.put(
        "/api/employees/1",
        json={"name": "Sofie Lindberg", "coffee_likes": "havremælk", "coffee_dislikes": "sukker"},
    )
    assert r.status_code == 200
    assert r.get_json()["coffee_likes"] == "havremælk"
    assert r.get_json()["coffee_dislikes"] == "sukker"

    # A PUT that omits the coffee fields entirely must not wipe them.
    r = client.put("/api/employees/1", json={"name": "Sofie Lindberg", "role": "Teamleder"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["role"] == "Teamleder"
    assert body["coffee_likes"] == "havremælk"
    assert body["coffee_dislikes"] == "sukker"


def test_api_overview_has_favorite_coffee(client):
    client.post("/api/employees/1/coffees", json={"coffee_id": 5, "rating": "favorit"})
    r = client.get("/api/overview")
    assert r.status_code == 200
    employee = r.get_json()["employees"][0]
    assert employee["favorite_coffee"] == {"label": "Americano", "emoji": "☕"}


def test_api_guide_has_coffee(client):
    client.post("/api/employees/1/coffees", json={"coffee_id": 3, "rating": "kan_lide"})
    session = client.post("/api/employees/1/sessions", json={"scheduled_for": "2026-12-01"}).get_json()
    r = client.get(f"/api/sessions/{session['id']}/guide")
    assert r.status_code == 200
    coffee = r.get_json()["coffee"]
    assert [c["key"] for c in coffee["likes"]] == ["cappuccino"]


# --- Frontend ----------------------------------------------------------------------

def test_style_has_ambient_animation():
    css = (FRONTEND_DIR / "style.css").read_text(encoding="utf-8")
    assert "@keyframes ambient-drift" in css
    ambient_section = css.split("Ambient background")[1]
    assert "pointer-events: none" in ambient_section
