"""Flask app: JSON API + static frontend, one process, port 8125."""

import mimetypes
import random
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from flask import Flask, abort, g, jsonify, request
from werkzeug.exceptions import HTTPException

from musprepping import praise
from musprepping.db import queries
from musprepping.db.connection import connect
from musprepping.db.schema import WEAKNESS_EMOJIS, init_db

HOST = "127.0.0.1"
PORT = 8125

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# Windows can map .js to text/plain in the registry, which breaks ES module loading.
mimetypes.add_type("text/javascript", ".js")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.json.ensure_ascii = False  # keep æøå readable in responses


def get_db() -> sqlite3.Connection:
    """One connection per request, closed in teardown."""
    if "db" not in g:
        g.db = connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.errorhandler(HTTPException)
def json_errors(err: HTTPException):
    if request.path.startswith("/api/"):
        return jsonify({"detail": err.description}), err.code
    return err


# --- Parsing helpers -----------------------------------------------------------

def json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def text(body: dict, key: str) -> str:
    value = body.get(key)
    return value.strip() if isinstance(value, str) else ""


def parse_date(value, *, allow_future: bool = True, required: bool = False) -> str | None:
    """Accept 'YYYY-MM-DD' (what <input type=date> sends). Empty → None unless required."""
    if not isinstance(value, str) or not value.strip():
        if required:
            abort(400, description="vælg en dato")
        return None
    try:
        d = date.fromisoformat(value.strip())
    except ValueError:
        abort(400, description=f"ugyldig dato {value!r}")
    if not allow_future and d > date.today():
        abort(400, description="datoen ligger i fremtiden")
    return d.isoformat()


def employee_fields(body: dict, current: dict | None = None) -> dict:
    """`current` (the employee's existing row, on an update) supplies defaults for
    fields the caller omits entirely, so a PUT without coffee_likes/coffee_dislikes
    doesn't wipe them."""
    name = text(body, "name")
    if not name:
        abort(400, description="husk at skrive et navn")
    current = current or {}
    coffee_likes = current.get("coffee_likes", "")
    if "coffee_likes" in body:
        coffee_likes = text(body, "coffee_likes")
        if len(coffee_likes) > 200:
            abort(400, description="kaffe – gerne må højst være 200 tegn")
    coffee_dislikes = current.get("coffee_dislikes", "")
    if "coffee_dislikes" in body:
        coffee_dislikes = text(body, "coffee_dislikes")
        if len(coffee_dislikes) > 200:
            abort(400, description="kaffe – helst ikke må højst være 200 tegn")
    return {
        "name": name,
        "role": text(body, "role"),
        "team": text(body, "team"),
        "start_date": parse_date(body.get("start_date"), allow_future=False),
        "personal_note": text(body, "personal_note"),
        "coffee_likes": coffee_likes,
        "coffee_dislikes": coffee_dislikes,
    }


def employee_or_404(conn: sqlite3.Connection, employee_id) -> dict:
    employee = queries.get_employee(conn, employee_id) if isinstance(employee_id, int) else None
    if employee is None:
        abort(404, description=f"ingen medarbejder med id {employee_id}")
    return employee


def session_or_404(conn: sqlite3.Connection, session_id: int) -> dict:
    session = queries.get_session(conn, session_id)
    if session is None:
        abort(404, description=f"ingen samtale med id {session_id}")
    return session


def id_list(value) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(i, int) for i in value):
        abort(400, description="forventede en liste af id'er")
    return value


# --- Frontend ------------------------------------------------------------------

@app.get("/")
def index():
    return app.send_static_file("index.html")


# --- API -----------------------------------------------------------------------

@app.get("/api/status")
def status():
    return {"ok": True, "app": "MUSPrepping"}


@app.get("/api/overview")
def overview():
    conn = get_db()
    employees = queries.get_employees(conn)
    for e in employees:
        e["progress"] = queries.prep_progress(e, e["next_mus"])
    return {"employees": employees, "upcoming": queries.get_upcoming_sessions(conn)}


@app.get("/api/strengths")
def strengths():
    return jsonify(queries.get_strengths(get_db()))


@app.get("/api/tones")
def tones():
    return jsonify([{"key": k, "label": t["label"]} for k, t in praise.TONES.items()])


@app.post("/api/employees")
def create_employee():
    conn = get_db()
    employee_id = queries.insert_employee(conn, **employee_fields(json_body()))
    conn.commit()
    return queries.get_employee(conn, employee_id), 201


@app.get("/api/employees/<int:employee_id>")
def employee_detail(employee_id: int):
    conn = get_db()
    employee = employee_or_404(conn, employee_id)
    return {
        "employee": employee,
        "strengths": queries.get_strengths(conn),
        "selected_strength_ids": [s["id"] for s in queries.get_employee_strengths(conn, employee_id)],
        "highlights": queries.get_highlights(conn, employee_id),
        "weaknesses": queries.get_weaknesses(conn, employee_id),
        "sessions": queries.get_sessions(conn, employee_id),
        "coffee": queries.get_coffee_profile(conn, employee_id),
        "coffees": queries.get_coffees(conn),
        "children": queries.get_children(conn, employee_id),
    }


@app.put("/api/employees/<int:employee_id>")
def update_employee(employee_id: int):
    conn = get_db()
    current = employee_or_404(conn, employee_id)
    queries.update_employee(conn, employee_id, **employee_fields(json_body(), current))
    conn.commit()
    return queries.get_employee(conn, employee_id)


@app.delete("/api/employees/<int:employee_id>")
def delete_employee(employee_id: int):
    conn = get_db()
    employee_or_404(conn, employee_id)
    queries.delete_employee(conn, employee_id)
    conn.commit()
    return "", 204


@app.post("/api/employees/<int:employee_id>/strengths")
def toggle_strength(employee_id: int):
    conn = get_db()
    employee_or_404(conn, employee_id)
    strength_id = json_body().get("strength_id")
    if not isinstance(strength_id, int) or not queries.get_strengths_by_ids(conn, [strength_id]):
        abort(400, description=f"ukendt styrke {strength_id!r}")
    selected = queries.toggle_employee_strength(conn, employee_id, strength_id)
    conn.commit()
    return {"strength_id": strength_id, "selected": selected}


@app.post("/api/employees/<int:employee_id>/highlights")
def create_highlight(employee_id: int):
    conn = get_db()
    employee_or_404(conn, employee_id)
    body = json_body()
    title = text(body, "title")
    if not title:
        abort(400, description="giv højdepunktet en kort titel")
    happened_on = parse_date(body.get("happened_on"), allow_future=False)
    highlight_id = queries.insert_highlight(conn, employee_id, title, text(body, "description"), happened_on)
    conn.commit()
    return {"id": highlight_id}, 201


@app.delete("/api/highlights/<int:highlight_id>")
def delete_highlight(highlight_id: int):
    conn = get_db()
    if not queries.delete_highlight(conn, highlight_id):
        abort(404, description=f"intet højdepunkt med id {highlight_id}")
    conn.commit()
    return "", 204


@app.post("/api/employees/<int:employee_id>/weaknesses")
def create_weakness(employee_id: int):
    conn = get_db()
    employee_or_404(conn, employee_id)
    title = text(json_body(), "title")
    if not title:
        abort(400, description="beskriv udviklingsområdet med et par ord")
    emoji = random.choice(WEAKNESS_EMOJIS)
    weakness_id = queries.insert_weakness(conn, employee_id, title, emoji)
    conn.commit()
    return {"id": weakness_id, "emoji": emoji}, 201


@app.delete("/api/weaknesses/<int:weakness_id>")
def delete_weakness(weakness_id: int):
    conn = get_db()
    if not queries.delete_weakness(conn, weakness_id):
        abort(404, description=f"intet udviklingsområde med id {weakness_id}")
    conn.commit()
    return "", 204


@app.post("/api/employees/<int:employee_id>/sessions")
def create_session(employee_id: int):
    conn = get_db()
    employee_or_404(conn, employee_id)
    scheduled_for = parse_date(json_body().get("scheduled_for"), required=True)
    session_id = queries.insert_session(conn, employee_id, scheduled_for)
    conn.commit()
    return queries.get_session(conn, session_id), 201


@app.get("/api/sessions/<int:session_id>")
def session_detail(session_id: int):
    conn = get_db()
    session = session_or_404(conn, session_id)
    employee_id = session["employee_id"]
    return {
        "session": session,
        "employee": queries.get_employee(conn, employee_id),
        "strengths": queries.get_strengths(conn),
        "selected_strength_ids": [s["id"] for s in queries.get_employee_strengths(conn, employee_id)],
        "highlights": queries.get_highlights(conn, employee_id),
        "coffee": queries.get_coffee_profile(conn, employee_id),
        "children": queries.get_children(conn, employee_id),
    }


@app.patch("/api/sessions/<int:session_id>")
def update_session(session_id: int):
    conn = get_db()
    session_or_404(conn, session_id)
    fields = {k: v for k, v in json_body().items() if k in queries.MUS_FIELDS and isinstance(v, str)}
    if "scheduled_for" in fields:
        fields["scheduled_for"] = parse_date(fields["scheduled_for"], required=True)
    if fields.get("status", "planlagt") not in queries.MUS_STATUSES:
        abort(400, description=f"ukendt status {fields['status']!r}")
    if fields.get("tone", praise.DEFAULT_TONE) not in praise.TONES:
        abort(400, description=f"ukendt tone {fields['tone']!r}")
    queries.update_session(conn, session_id, **fields)
    conn.commit()
    return queries.get_session(conn, session_id)


@app.delete("/api/sessions/<int:session_id>")
def delete_session(session_id: int):
    conn = get_db()
    session_or_404(conn, session_id)
    queries.delete_session(conn, session_id)
    conn.commit()
    return "", 204


@app.get("/api/sessions/<int:session_id>/guide")
def session_guide(session_id: int):
    conn = get_db()
    session = session_or_404(conn, session_id)
    employee_id = session["employee_id"]
    return {
        "session": session,
        "employee": queries.get_employee(conn, employee_id),
        "strengths": queries.get_employee_strengths(conn, employee_id),
        "highlights": queries.get_highlights(conn, employee_id),
        "weaknesses": queries.get_weaknesses(conn, employee_id),
        "questions": praise.conversation_questions(seed=session_id),
        "coffee": queries.get_coffee_profile(conn, employee_id),
        "children": queries.get_children(conn, employee_id),
    }


@app.post("/api/praise")
def generate_praise():
    conn = get_db()
    body = json_body()
    employee = employee_or_404(conn, body.get("employee_id"))
    strengths = queries.get_strengths_by_ids(conn, id_list(body.get("strength_ids")))
    highlights = queries.get_highlights_by_ids(conn, employee["id"], id_list(body.get("highlight_ids")))
    tone = body.get("tone") or praise.DEFAULT_TONE
    if tone not in praise.TONES:
        abort(400, description=f"ukendt tone {tone!r}")
    seed = body.get("seed")
    return praise.generate_praise(
        employee["name"], strengths, highlights, tone=tone, seed=seed if isinstance(seed, int) else None
    )


# --- Coffee ----------------------------------------------------------------------

@app.get("/api/coffees")
def coffees():
    return jsonify(queries.get_coffees(get_db()))


@app.post("/api/employees/<int:employee_id>/coffees")
def rate_coffee(employee_id: int):
    conn = get_db()
    employee_or_404(conn, employee_id)
    body = json_body()
    coffee_id = body.get("coffee_id")
    if not isinstance(coffee_id, int) or queries.get_coffee(conn, coffee_id) is None:
        abort(400, description=f"ukendt kaffe {coffee_id!r}")
    rating = body.get("rating")
    if rating is not None and rating not in queries.RATINGS:
        abort(400, description=f"ukendt vurdering {rating!r}")
    queries.set_employee_coffee(conn, employee_id, coffee_id, rating)
    conn.commit()
    return queries.get_coffee_profile(conn, employee_id)


# --- Children --------------------------------------------------------------------

def parse_birth_year(value) -> int | None:
    """Accept an int or a numeric string (the HTML form sends strings); empty → None."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        year = int(value)
    except (TypeError, ValueError):
        abort(400, description=f"ugyldigt fødselsår {value!r}")
    current_year = date.today().year
    if not (1940 <= year <= current_year):
        abort(400, description=f"fødselsår skal være mellem 1940 og {current_year}")
    return year


def child_fields(body: dict) -> dict:
    name = text(body, "name")
    if not name:
        abort(400, description="husk at skrive barnets navn")
    if len(name) > 80:
        abort(400, description="navnet må højst være 80 tegn")
    interests = text(body, "interests")
    if len(interests) > 200:
        abort(400, description="interesser må højst være 200 tegn")
    return {
        "name": name,
        "birth_year": parse_birth_year(body.get("birth_year")),
        "interests": interests,
    }


def child_or_404(conn: sqlite3.Connection, child_id: int) -> dict:
    child = queries.get_child(conn, child_id)
    if child is None:
        abort(404, description=f"intet barn med id {child_id}")
    return child


@app.post("/api/employees/<int:employee_id>/children")
def create_child(employee_id: int):
    conn = get_db()
    employee_or_404(conn, employee_id)
    child_id = queries.insert_child(conn, employee_id, **child_fields(json_body()))
    conn.commit()
    return queries.get_child(conn, child_id), 201


@app.put("/api/children/<int:child_id>")
def update_child(child_id: int):
    conn = get_db()
    child_or_404(conn, child_id)
    queries.update_child(conn, child_id, **child_fields(json_body()))
    conn.commit()
    return queries.get_child(conn, child_id)


@app.delete("/api/children/<int:child_id>")
def delete_child(child_id: int):
    conn = get_db()
    if not queries.delete_child(conn, child_id):
        abort(404, description=f"intet barn med id {child_id}")
    conn.commit()
    return "", 204


def run() -> None:
    with closing(connect()) as conn:
        init_db(conn)
    print(f"MUSPrepping kører på http://localhost:{PORT}")
    app.run(host=HOST, port=PORT)
