from datetime import date

import pytest

from musprepping.db import queries
from musprepping.db.connection import connect
from musprepping.db.schema import init_db
from musprepping.ingest.loader import ingest_path

TODAY = date(2026, 9, 1)

EMPLOYEE_HEADER = "navn,rolle,team,ansat_siden,styrker,note\n"
HIGHLIGHT_HEADER = "medarbejder,titel,beskrivelse,dato\n"
MUS_HEADER = "medarbejder,dato\n"


@pytest.fixture
def conn(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    yield conn
    conn.close()


def test_folder_loads_employees_before_the_rest(conn, tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    # alphabetically "hoejdepunkter" comes before "medarbejdere"; the loader must not care
    (inbox / "hoejdepunkter_a.csv").write_text(HIGHLIGHT_HEADER + "Sofie,Lancering,,2026-05-01\n", encoding="utf-8")
    (inbox / "medarbejdere_a.csv").write_text(EMPLOYEE_HEADER + "Sofie,PL,Digital,2021-03-01,overblik;humor,\n", encoding="utf-8")
    (inbox / "mus_a.csv").write_text(MUS_HEADER + "sofie,2026-10-01\n", encoding="utf-8")
    (inbox / "noter.csv").write_text("x\n1\n", encoding="utf-8")

    report = ingest_path(conn, inbox, today=TODAY)
    assert report.rejected == []
    assert (report.employees_loaded, report.highlights_loaded, report.sessions_loaded) == (1, 1, 1)
    assert report.skipped_files == ["noter.csv"]

    [sofie] = queries.get_employees(conn)
    assert {s["key"] for s in sofie["strengths"]} == {"overblik", "humor"}
    assert sofie["next_mus"]["scheduled_for"] == "2026-10-01"


def test_bad_rows_are_rejected_and_the_rest_loads(conn, tmp_path):
    f = tmp_path / "medarbejdere_x.csv"
    f.write_text(
        EMPLOYEE_HEADER
        + "Ahmad,Udvikler,,2023-08-15,mod,\n"
        + ",Uden navn,,,,\n"
        + "Mette,,,2099-01-01,,\n"
        + "Jonas,,,,superkraft,\n"
        + "ahmad,Dublet,,,,\n",
        encoding="utf-8",
    )
    report = ingest_path(conn, f, today=TODAY)
    assert report.employees_loaded == 1
    reasons = {line: reason for _, line, reason in report.rejected}
    assert "mangler navn" in reasons[3]
    assert "fremtiden" in reasons[4]
    assert "superkraft" in reasons[5]
    assert "findes allerede" in reasons[6]


def test_highlight_and_mus_validation(conn, tmp_path):
    queries.insert_employee(conn, "Sofie")
    conn.commit()
    h = tmp_path / "hoejdepunkter_x.csv"
    h.write_text(HIGHLIGHT_HEADER + "Ukendt,Noget,,\nSofie,,,\nSofie,Fremtid,,2026-12-24\n", encoding="utf-8")
    m = tmp_path / "mus_x.csv"
    m.write_text(MUS_HEADER + "Sofie,\nSofie,2026-13-01\nSofie,2027-01-15\n", encoding="utf-8")

    report = ingest_path(conn, h, today=TODAY)
    assert report.highlights_loaded == 0
    assert len(report.rejected) == 3

    report = ingest_path(conn, m, today=TODAY)
    assert report.sessions_loaded == 1  # MUS dates may be in the future
    assert len(report.rejected) == 2


def test_excel_bom_is_handled(conn, tmp_path):
    f = tmp_path / "medarbejdere_excel.csv"
    f.write_bytes(("﻿" + EMPLOYEE_HEADER + "Sofie,,,,,\n").encode("utf-8"))
    assert ingest_path(conn, f, today=TODAY).employees_loaded == 1


def test_sample_inbox_loads_cleanly(conn):
    from pathlib import Path

    inbox = Path(__file__).resolve().parent.parent / "data" / "inbox"
    report = ingest_path(conn, inbox, today=TODAY)
    assert report.rejected == []
    assert report.employees_loaded >= 3
