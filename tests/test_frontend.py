"""Frontend-adjacent checks: the app serves its own static files."""

from contextlib import closing

import pytest

from musprepping.api.main import FRONTEND_DIR, app
from musprepping.db.connection import connect
from musprepping.db.schema import init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "static-test.db"
    monkeypatch.setenv("MUSPREPPING_DB", str(path))
    with closing(connect(path)) as conn:
        init_db(conn)
    return app.test_client()


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.content_type
    assert "MUSPrepping" in r.text


def test_static_assets_served(client):
    js = client.get("/app.js")
    assert js.status_code == 200
    assert "javascript" in js.content_type  # ES modules refuse text/plain
    assert "renderPrep" in js.text
    assert client.get("/api.js").status_code == 200
    assert "praise-text" in client.get("/style.css").text


def test_frontend_has_no_external_resources():
    # the SVG namespace is an identifier, not a fetched resource
    allowed = ("http://www.w3.org/2000/svg",)
    for f in FRONTEND_DIR.iterdir():
        content = f.read_text(encoding="utf-8").lower()
        for a in allowed:
            content = content.replace(a, "")
        assert "http://" not in content, f.name
        assert "https://" not in content, f.name
