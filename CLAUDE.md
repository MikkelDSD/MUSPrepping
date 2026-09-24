# MUSPrepping

Helps a manager prepare for MUS (*medarbejderudviklingssamtaler*, the Danish annual employee development review), with the emphasis on warm, specific recognition. Python with Flask, data in SQLite, UI in Danish.

## Architecture

`src/musprepping/` is a straight pipeline: **ingest → db → api → frontend**, plus `praise.py` for the wording.

- `ingest/loader.py` parses and validates CSV rows into `employees`/`highlights`/`mus_sessions`; `ingest/cli.py` wires it to `uv run ingest`/`uv run seed`.
- `db/schema.py` defines the SQLite schema and the `strengths` reference data (upserted by `init_db`, so edits reach existing databases on the next start). `db/connection.py` opens a raw `sqlite3` connection (no ORM, `PRAGMA foreign_keys = ON`, `row_factory = sqlite3.Row`). `db/queries.py` holds every SQL query as a plain function taking `conn` as its first argument. This is the only place SQL lives, and query functions never commit; the caller owns the transaction.
- `praise.py` is the phrase library and `generate_praise()`, a pure function (no DB). Every strength `key` in `schema.STRENGTHS` needs phrases in `STRENGTH_PHRASES` (a test enforces it). Passing the same `seed` gives the same text.
- `api/main.py` is a thin Flask layer: route handlers validate, call `queries.py`/`praise.py`, `conn.commit()`, and return dicts as JSON. Errors are `{"detail": ...}` (same shape as FastAPI's, so it matches brewops). It also serves `frontend/` as static files, so the API and UI are one process on port 8125.
- `frontend/` is vanilla JS/HTML/CSS with no framework and no build step. `app.js` is a hash-routed SPA (`#/`, `#/medarbejder/1`, `#/mus/1`, …) that fetches the JSON API via `api.js` and renders with template literals + `innerHTML`. Always pass user text through `esc()`.

## GitHub Pages + local API

`.github/workflows/pages.yml` publishes `src/musprepping/frontend/` to <https://mikkeldsd.github.io/MUSPrepping/>. Only the UI is public. Opened from Pages, `api.js` calls `http://127.0.0.1:8125`, so the boss runs `uv run start` locally and employee data never leaves their machine. Consequences:

- The frontend must keep working from a sub-path: relative asset URLs only, no server-side routes (use `#/…`), no external resources (tests enforce this).
- The API allows the Pages origin via CORS, including Chrome's `Access-Control-Allow-Private-Network` preflight. Change the allowed origins with `MUSPREPPING_ALLOWED_ORIGINS` (comma-separated).
- If the API is unreachable, the UI shows the "start MUSPrepping on your computer" screen instead of an error.

## Running and testing

- `uv run start`: run the app at http://localhost:8125.
- `uv run seed`: rebuild `musprepping.db` from scratch and ingest `data/inbox` (fictional demo team).
- `uv run ingest <path>`: load more CSVs (e.g. the real team exported from Excel).
- `uv run pytest`: run the test suite (`tests/`). Each test gets its own throwaway SQLite db via `tmp_path`; API tests use Flask's `test_client()`, no server needed.

## Conventions

- Dates are `'YYYY-MM-DD'` strings. Highlight and hire dates may not be in the future; MUS dates may.
- SQL join aliases are consistent across queries: `e` employees, `s` strengths, `es` employee_strengths, `h` highlights, `ms` mus_sessions.
- Keep new endpoints thin: put the SQL in `db/queries.py`, not in `api/main.py`.
- Code, API paths and docs in English; everything the user sees (UI text, praise, API error `detail`) in Danish.
- `brewops/` in this folder is a separate repo, ignored by git and pytest. Don't touch it.
