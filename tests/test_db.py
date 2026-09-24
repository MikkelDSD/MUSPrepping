import pytest

from musprepping.db import queries
from musprepping.db.connection import connect
from musprepping.db.schema import STRENGTHS, init_db, reset_db


@pytest.fixture
def conn(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    yield conn
    conn.close()


def test_init_is_idempotent(conn):
    init_db(conn)
    init_db(conn)
    assert len(queries.get_strengths(conn)) == len(STRENGTHS)


def test_employee_crud(conn):
    employee_id = queries.insert_employee(conn, "Sofie Lindberg", "Projektleder", "Digital", "2021-03-01", "Skarp")
    conn.commit()
    assert queries.get_employee(conn, employee_id)["role"] == "Projektleder"
    assert queries.find_employee_by_name(conn, "sofie lindberg")["id"] == employee_id

    queries.update_employee(conn, employee_id, "Sofie L.", "Teamleder")
    assert queries.get_employee(conn, employee_id)["name"] == "Sofie L."

    queries.delete_employee(conn, employee_id)
    assert queries.get_employee(conn, employee_id) is None


def test_toggle_strength(conn):
    employee_id = queries.insert_employee(conn, "Ahmad")
    assert queries.toggle_employee_strength(conn, employee_id, 1) is True
    assert [s["id"] for s in queries.get_employee_strengths(conn, employee_id)] == [1]
    assert queries.toggle_employee_strength(conn, employee_id, 1) is False
    assert queries.get_employee_strengths(conn, employee_id) == []


def test_delete_employee_cascades(conn):
    employee_id = queries.insert_employee(conn, "Mette")
    queries.add_employee_strength_by_key(conn, employee_id, "humor")
    queries.insert_highlight(conn, employee_id, "Reddede dagen")
    queries.insert_session(conn, employee_id, "2026-10-01")
    queries.delete_employee(conn, employee_id)
    for table in ("employee_strengths", "highlights", "mus_sessions"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table


def test_weaknesses(conn):
    employee_id = queries.insert_employee(conn, "Henrik")
    weakness_id = queries.insert_weakness(conn, employee_id, "Kommer for sent", "🦥")
    [weakness] = queries.get_weaknesses(conn, employee_id)
    assert (weakness["title"], weakness["emoji"]) == ("Kommer for sent", "🦥")
    assert queries.delete_weakness(conn, weakness_id) is True
    assert queries.delete_weakness(conn, weakness_id) is False

    queries.insert_weakness(conn, employee_id, "Glemmer nøgler", "🙈")
    queries.delete_employee(conn, employee_id)
    assert conn.execute("SELECT COUNT(*) FROM weaknesses").fetchone()[0] == 0


def test_highlights_by_ids_only_returns_own(conn):
    a = queries.insert_employee(conn, "A")
    b = queries.insert_employee(conn, "B")
    ha = queries.insert_highlight(conn, a, "A's sejr")
    hb = queries.insert_highlight(conn, b, "B's sejr")
    assert [h["id"] for h in queries.get_highlights_by_ids(conn, a, [ha, hb])] == [ha]


def test_sessions_next_and_upcoming(conn):
    employee_id = queries.insert_employee(conn, "Jonas")
    later = queries.insert_session(conn, employee_id, "2026-12-01")
    sooner = queries.insert_session(conn, employee_id, "2026-10-01")
    assert queries.get_next_session(conn, employee_id)["id"] == sooner

    queries.update_session(conn, sooner, status="afholdt", praise_text="Tak!", not_a_column="ignored")
    assert queries.get_session(conn, sooner)["praise_text"] == "Tak!"
    assert queries.get_next_session(conn, employee_id)["id"] == later
    assert [s["id"] for s in queries.get_upcoming_sessions(conn)] == [later]


def test_prep_progress():
    employee = {"strengths": [{"id": 1}], "highlight_count": 0}
    session = {"praise_text": "Du er god", "development_goals": "  "}
    progress = queries.prep_progress(employee, session)
    assert progress["done"] == 2
    assert progress["percent"] == 50
    assert queries.prep_progress(employee, None)["steps"]["ros"] is False


def test_reset_db_clears_data(conn):
    queries.insert_employee(conn, "Sofie")
    conn.commit()
    reset_db(conn)
    assert queries.get_employees(conn) == []
    assert len(queries.get_strengths(conn)) == len(STRENGTHS)
