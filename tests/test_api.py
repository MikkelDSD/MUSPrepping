import pytest

from musprepping.api.main import app
from musprepping.db import queries
from musprepping.db.connection import connect
from musprepping.db.schema import WEAKNESS_EMOJIS, init_db

PAGES_ORIGIN = "https://mikkeldsd.github.io"


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "api-test.db"
    monkeypatch.setenv("MUSPREPPING_DB", str(path))
    monkeypatch.delenv("MUSPREPPING_ALLOWED_ORIGINS", raising=False)
    conn = connect(path)
    init_db(conn)
    sofie = queries.insert_employee(conn, "Sofie Lindberg", "Projektleder", "Digital")
    queries.add_employee_strength_by_key(conn, sofie, "overblik")
    queries.insert_highlight(conn, sofie, "Lancerede kundeportalen", "", "2026-05-20")
    queries.insert_session(conn, sofie, "2026-10-01")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def client(db):
    return app.test_client()


def test_overview(client):
    r = client.get("/api/overview")
    assert r.status_code == 200
    data = r.get_json()
    [sofie] = data["employees"]
    assert sofie["strengths"][0]["key"] == "overblik"
    assert sofie["next_mus"]["scheduled_for"] == "2026-10-01"
    assert sofie["progress"]["done"] == 2
    assert data["upcoming"][0]["employee_name"] == "Sofie Lindberg"


def test_create_update_delete_employee(client):
    r = client.post("/api/employees", json={"name": "  Ahmad Rahimi ", "role": "Udvikler", "start_date": ""})
    assert r.status_code == 201, r.text
    employee = r.get_json()
    assert employee["name"] == "Ahmad Rahimi"
    assert employee["start_date"] is None

    r = client.put(f"/api/employees/{employee['id']}", json={"name": "Ahmad R.", "team": "Digital"})
    assert r.status_code == 200
    assert r.get_json()["team"] == "Digital"

    assert client.delete(f"/api/employees/{employee['id']}").status_code == 204
    assert client.get(f"/api/employees/{employee['id']}").status_code == 404


@pytest.mark.parametrize(
    "payload,fragment",
    [
        ({"name": "   "}, "navn"),
        ({"name": "X", "start_date": "igår"}, "ugyldig dato"),
        ({"name": "X", "start_date": "2999-01-01"}, "fremtiden"),
    ],
)
def test_create_employee_validation(client, payload, fragment):
    r = client.post("/api/employees", json=payload)
    assert r.status_code == 400
    assert fragment in r.get_json()["detail"]


def test_employee_detail_404_is_json(client):
    r = client.get("/api/employees/999")
    assert r.status_code == 404
    assert "ingen medarbejder" in r.get_json()["detail"]


def test_toggle_strength(client):
    r = client.post("/api/employees/1/strengths", json={"strength_id": 1})
    assert r.get_json() == {"strength_id": 1, "selected": True}
    r = client.post("/api/employees/1/strengths", json={"strength_id": 1})
    assert r.get_json()["selected"] is False
    assert client.post("/api/employees/1/strengths", json={"strength_id": 999}).status_code == 400


def test_highlights(client):
    r = client.post("/api/employees/1/highlights", json={"title": "Holdt tale", "happened_on": "2026-06-01"})
    assert r.status_code == 201
    highlight_id = r.get_json()["id"]
    assert client.post("/api/employees/1/highlights", json={"title": ""}).status_code == 400
    assert client.delete(f"/api/highlights/{highlight_id}").status_code == 204
    assert client.delete(f"/api/highlights/{highlight_id}").status_code == 404


def test_weaknesses(client):
    r = client.post("/api/employees/1/weaknesses", json={"title": "Kommer for sent"})
    assert r.status_code == 201
    created = r.get_json()
    assert created["emoji"] in WEAKNESS_EMOJIS

    detail = client.get("/api/employees/1").get_json()
    assert [(w["title"], w["emoji"]) for w in detail["weaknesses"]] == [("Kommer for sent", created["emoji"])]
    assert client.get("/api/sessions/1/guide").get_json()["weaknesses"] == detail["weaknesses"]

    assert client.post("/api/employees/1/weaknesses", json={"title": "  "}).status_code == 400
    assert client.post("/api/employees/999/weaknesses", json={"title": "X"}).status_code == 404
    assert client.delete(f"/api/weaknesses/{created['id']}").status_code == 204
    assert client.delete(f"/api/weaknesses/{created['id']}").status_code == 404


def test_session_lifecycle(client):
    r = client.post("/api/employees/1/sessions", json={"scheduled_for": "2026-11-05"})
    assert r.status_code == 201
    session_id = r.get_json()["id"]

    r = client.patch(f"/api/sessions/{session_id}", json={
        "praise_text": "Tak for alt, Sofie.",
        "tone": "begejstret",
        "status": "afholdt",
        "employee_id": 42,  # not updatable, silently ignored
    })
    assert r.status_code == 200
    session = r.get_json()
    assert session["praise_text"] == "Tak for alt, Sofie."
    assert session["employee_id"] == 1

    detail = client.get(f"/api/sessions/{session_id}").get_json()
    assert detail["employee"]["name"] == "Sofie Lindberg"
    assert detail["selected_strength_ids"] == [8]

    guide = client.get(f"/api/sessions/{session_id}/guide").get_json()
    assert guide["questions"]
    assert guide["highlights"][0]["title"] == "Lancerede kundeportalen"

    assert client.delete(f"/api/sessions/{session_id}").status_code == 204


@pytest.mark.parametrize(
    "payload",
    [{"status": "aflyst"}, {"tone": "sarkastisk"}, {"scheduled_for": "snart"}],
)
def test_session_update_validation(client, payload):
    assert client.patch("/api/sessions/1", json=payload).status_code == 400


def test_generate_praise(client):
    r = client.post("/api/praise", json={
        "employee_id": 1, "strength_ids": [8], "highlight_ids": [1], "tone": "varm", "seed": 7,
    })
    assert r.status_code == 200
    praise = r.get_json()
    assert "Sofie" in praise["text"]
    assert "Lancerede kundeportalen" in praise["text"]
    # same seed, same words
    again = client.post("/api/praise", json={
        "employee_id": 1, "strength_ids": [8], "highlight_ids": [1], "tone": "varm", "seed": 7,
    }).get_json()
    assert again["text"] == praise["text"]


def test_generate_praise_validation(client):
    assert client.post("/api/praise", json={"employee_id": 999}).status_code == 404
    assert client.post("/api/praise", json={"employee_id": 1, "strength_ids": "8"}).status_code == 400
    assert client.post("/api/praise", json={"employee_id": 1, "tone": "sur"}).status_code == 400


def test_cors_allows_github_pages(client):
    r = client.get("/api/status", headers={"Origin": PAGES_ORIGIN})
    assert r.headers["Access-Control-Allow-Origin"] == PAGES_ORIGIN

    preflight = client.options("/api/sessions/1", headers={
        "Origin": PAGES_ORIGIN,
        "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Private-Network": "true",
    })
    assert preflight.status_code == 200
    assert "PATCH" in preflight.headers["Access-Control-Allow-Methods"]
    assert preflight.headers["Access-Control-Allow-Private-Network"] == "true"


def test_cors_rejects_other_origins(client):
    r = client.get("/api/overview", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in r.headers
