from datetime import date

import pytest

from musprepping.api.main import app
from musprepping.db import queries
from musprepping.db.connection import connect
from musprepping.db.schema import init_db

CURRENT_YEAR = date.today().year


# --- DB-level tests --------------------------------------------------------------

@pytest.fixture
def conn(tmp_path):
    conn = connect(tmp_path / "children-test.db")
    init_db(conn)
    yield conn
    conn.close()


def test_child_crud(conn):
    employee_id = queries.insert_employee(conn, "Sofie Lindberg")
    child_id = queries.insert_child(conn, employee_id, "Emil", 2018, "fodbold, Minecraft")
    conn.commit()

    child = queries.get_child(conn, child_id)
    assert child["name"] == "Emil"
    assert child["birth_year"] == 2018
    assert child["interests"] == "fodbold, Minecraft"

    queries.update_child(conn, child_id, "Emil Lindberg", 2019, "fodbold")
    updated = queries.get_child(conn, child_id)
    assert updated["name"] == "Emil Lindberg"
    assert updated["birth_year"] == 2019
    assert updated["interests"] == "fodbold"

    assert queries.delete_child(conn, child_id) is True
    assert queries.get_child(conn, child_id) is None
    assert queries.delete_child(conn, child_id) is False


def test_get_children_orders_with_nulls_last(conn):
    employee_id = queries.insert_employee(conn, "Ahmad")
    queries.insert_child(conn, employee_id, "Ida", 2015)
    queries.insert_child(conn, employee_id, "Bo", None)
    queries.insert_child(conn, employee_id, "Emil", 2018)
    queries.insert_child(conn, employee_id, "Anna", 2015)
    conn.commit()

    names = [c["name"] for c in queries.get_children(conn, employee_id)]
    # birth_year ASC, nulls last; ties broken by name COLLATE NOCASE
    assert names == ["Anna", "Ida", "Emil", "Bo"]


def test_delete_employee_cascades_children(conn):
    employee_id = queries.insert_employee(conn, "Mette")
    queries.insert_child(conn, employee_id, "Emil", 2018)
    conn.commit()
    queries.delete_employee(conn, employee_id)
    assert conn.execute("SELECT COUNT(*) FROM children").fetchone()[0] == 0


def test_get_employees_includes_trimmed_children(conn):
    employee_id = queries.insert_employee(conn, "Jonas")
    queries.insert_child(conn, employee_id, "Emil", 2018, "fodbold")
    conn.commit()
    [jonas] = queries.get_employees(conn)
    assert jonas["children"] == [{"id": 1, "name": "Emil", "birth_year": 2018}]


# --- API-level tests ---------------------------------------------------------------

@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "children-api-test.db"
    monkeypatch.setenv("MUSPREPPING_DB", str(path))
    conn = connect(path)
    init_db(conn)
    sofie = queries.insert_employee(conn, "Sofie Lindberg", "Projektleder", "Digital")
    queries.insert_session(conn, sofie, "2026-10-01")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def client(db):
    return app.test_client()


def test_create_child(client):
    r = client.post("/api/employees/1/children", json={"name": "Emil", "birth_year": "2018", "interests": "fodbold"})
    assert r.status_code == 201, r.text
    child = r.get_json()
    assert child["name"] == "Emil"
    assert child["birth_year"] == 2018
    assert child["interests"] == "fodbold"


def test_create_child_unknown_employee(client):
    assert client.post("/api/employees/999/children", json={"name": "Emil"}).status_code == 404


@pytest.mark.parametrize(
    "payload,fragment",
    [
        ({"name": "  "}, "navn"),
        ({"name": "X" * 81}, "80"),
        ({"name": "Emil", "birth_year": "abe"}, "fødselsår"),
        ({"name": "Emil", "birth_year": 1900}, "fødselsår"),
        ({"name": "Emil", "birth_year": CURRENT_YEAR + 1}, "fødselsår"),
        ({"name": "Emil", "interests": "x" * 201}, "200"),
    ],
)
def test_create_child_validation(client, payload, fragment):
    r = client.post("/api/employees/1/children", json=payload)
    assert r.status_code == 400
    assert fragment in r.get_json()["detail"]


def test_create_child_birth_year_as_empty_string_is_allowed(client):
    r = client.post("/api/employees/1/children", json={"name": "Ida", "birth_year": ""})
    assert r.status_code == 201
    assert r.get_json()["birth_year"] is None


def test_update_child(client):
    child_id = client.post("/api/employees/1/children", json={"name": "Emil", "birth_year": "2018"}).get_json()["id"]
    r = client.put(f"/api/children/{child_id}", json={"name": "Emil L.", "birth_year": "2019", "interests": "Minecraft"})
    assert r.status_code == 200
    updated = r.get_json()
    assert updated["name"] == "Emil L."
    assert updated["birth_year"] == 2019
    assert updated["interests"] == "Minecraft"


def test_update_child_404(client):
    assert client.put("/api/children/999", json={"name": "Emil"}).status_code == 404


def test_delete_child(client):
    child_id = client.post("/api/employees/1/children", json={"name": "Emil"}).get_json()["id"]
    assert client.delete(f"/api/children/{child_id}").status_code == 204
    assert client.delete(f"/api/children/{child_id}").status_code == 404


def test_overview_includes_children(client):
    client.post("/api/employees/1/children", json={"name": "Emil", "birth_year": "2018"})
    r = client.get("/api/overview")
    assert r.status_code == 200
    [sofie] = r.get_json()["employees"]
    assert sofie["children"] == [{"id": 1, "name": "Emil", "birth_year": 2018}]


def test_employee_detail_includes_children(client):
    client.post("/api/employees/1/children", json={"name": "Emil", "birth_year": "2018", "interests": "fodbold"})
    r = client.get("/api/employees/1")
    assert r.status_code == 200
    children = r.get_json()["children"]
    assert children[0]["name"] == "Emil"
    assert children[0]["interests"] == "fodbold"


def test_session_detail_includes_children(client):
    client.post("/api/employees/1/children", json={"name": "Emil"})
    session_id = client.get("/api/employees/1").get_json()["sessions"][0]["id"]
    r = client.get(f"/api/sessions/{session_id}")
    assert r.status_code == 200
    assert r.get_json()["children"][0]["name"] == "Emil"


def test_session_guide_includes_children(client):
    client.post("/api/employees/1/children", json={"name": "Emil"})
    session_id = client.get("/api/employees/1").get_json()["sessions"][0]["id"]
    r = client.get(f"/api/sessions/{session_id}/guide")
    assert r.status_code == 200
    assert r.get_json()["children"][0]["name"] == "Emil"


def test_frontend_serves_children_js(client):
    r = client.get("/children.js")
    assert r.status_code == 200
    assert "javascript" in r.content_type
    assert "childrenTip" in r.text
