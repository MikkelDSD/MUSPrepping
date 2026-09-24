# MUSPrepping 💛

Forbered medarbejderudviklingssamtaler, der får folk til at vokse.

MUSPrepping helps a manager prepare for MUS (the annual employee development review) with the focus on
what people remember most: **sincere, specific recognition**. For each employee the manager picks
strengths, notes concrete highlights, and gets a warm Danish praise text in the tone of their choice.
The manager then edits it into their own words and prints a one-page conversation guide.

Everything runs locally at <http://localhost:8125>. The data is a SQLite file on the manager's own computer.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) (`winget install astral-sh.uv` on Windows,
  `brew install uv` on macOS, or see the uv docs)

Alternatively, open the repo in a GitHub Codespace or a VS Code Dev Container.
`.devcontainer/` sets everything up for you.

## Getting started

```
uv sync
uv run seed
uv run start
```

Then open <http://localhost:8125>.

- `uv run seed`: creates the SQLite database and loads the fictional demo team in `data/inbox/`
- `uv run start`: starts the app (API + UI) on port 8125
- `uv run ingest <path>`: loads more CSV files, e.g. your real team exported from Excel
- `uv run pytest`: runs the test suite

## What the app does

| Page | What it's for |
|------|---------------|
| **Oversigt** (`#/`) | The whole team, upcoming MUS dates, and a progress ring per person (strengths · highlights · praise · goals) |
| **Medarbejder** (`#/medarbejder/<id>`) | Toggle strengths, log concrete highlights, plan a MUS |
| **Forberedelse** (`#/mus/<id>`) | 1) choose what to recognise, 2) generate praise (*varm / begejstret / rolig*) with "Ny variant" and free editing, 3) development goals, wishes, private notes. Everything autosaves. |
| **Samtaleguide** (`#/mus/<id>/guide`) | Printable one-pager: welcome, praise, appreciative questions, goals, closing |

## Importing a team from CSV

Files in a folder are matched by name prefix; employees load first. Bad rows are skipped and reported.

| File | Columns |
|------|---------|
| `medarbejdere_*.csv` | `navn, rolle, team, ansat_siden, styrker, note` (`styrker` = `;`-separated keys from `db/schema.py`) |
| `hoejdepunkter_*.csv` | `medarbejder, titel, beskrivelse, dato` |
| `mus_*.csv` | `medarbejder, dato` |

## Repo layout

```
src/musprepping/ingest/     CSV parsing, validation, loading
src/musprepping/db/         SQLite schema, connection, queries
src/musprepping/api/        Flask routes + static file serving (port 8125)
src/musprepping/praise.py   Danish phrase library and praise generator
src/musprepping/frontend/   index.html, app.js, api.js, style.css (no build step)
tests/                      pytest suite
tickets/                    open tickets, in markdown
data/inbox/                 fictional demo team as CSV
.github/workflows/          runs the tests on push and pull requests
```

See `CLAUDE.md` for architecture notes and conventions.
