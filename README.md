# Tournament Planner

A clean Flask tournament management system supporting
**Round Robin** and **Knockout** formats with sport-aware result modes.

---

## Features

| Feature                                      | Status |
| -------------------------------------------- | ------ |
| Round Robin + Knockout formats               | ✅     |
| Football, Cricket, Basketball, Esports       | ✅     |
| Score-based & Winner-only result modes       | ✅     |
| IPL-style daily spread scheduling            | ✅     |
| Manual schedule editing with hard validation | ✅     |
| Manual lock (auto-scheduler won't overwrite) | ✅     |
| Round Robin: results in any order            | ✅     |
| Knockout: round-gated progression            | ✅     |
| Standings with correct tiebreakers           | ✅     |
| Chronological Schedule View                  | ✅     |
| Fixtures PDF export (Round Robin)            | ✅     |
| Odd/even team count with byes                | ✅     |
| Case-insensitive duplicate team protection   | ✅     |
| CSRF protection on all POST forms            | ✅     |

---

## Quick Start

```bash
pip install -r requirements.txt
python seed.py          # optional demo data
python app.py
# → http://localhost:5000
```

---

## Result Entry

### Round Robin

All pending matches are editable in any order. No round-based locking.
Use the **Edit** button on completed matches to correct results —
standings are fully recalculated.

### Knockout

Only the current round is open for result entry. Future rounds are
unlocked automatically when all current-round matches are complete.

---

## Sport Modes

| Sport      | Mode        | Outcomes              |
| ---------- | ----------- | --------------------- |
| Football   | Score-based | Win / Draw / Loss     |
| Basketball | Score-based | Win / Loss (no draws) |
| Cricket    | Winner-only | Win / Tie / No Result |
| Esports    | Winner-only | Win only              |
| Generic    | Score-based | Win / Draw / Loss     |

Knockout: ties/draws are always blocked regardless of sport.

---

## Fixtures PDF Export

Available for Round Robin tournaments. Click **⬇ PDF** on the Fixtures or
Schedule pages.

Layout:

- **Scheduled**: grouped by date in chronological order
- **Unscheduled**: separate section at the bottom
- **Unscheduled entirely**: grouped by round

---

## Team Name Uniqueness

Team names are case-insensitively unique per tournament, enforced at two layers:

1. **Python layer**: fast UI feedback before DB round-trip
2. **Database layer**: `name_key` column (normalised lowercase) has a
   `UNIQUE` constraint per tournament — prevents duplicates even if Python
   check is bypassed

---

## Architecture

```
app.py                  Flask app factory + CSRF init
models.py               SQLAlchemy models + sport constants
fixture_engine.py       Berger round-robin + knockout generation
scheduler.py            IPL-style daily spread scheduler + manual validation
routes/
  tournament_routes.py  Create, delete, generate fixtures, run scheduler
  team_routes.py        Add, edit, delete teams (case-insensitive checks)
  match_routes.py       Results, edits, manual schedule with lock
  standings_routes.py   Standings, progress, schedule view, PDF export
  admin_routes.py       Event configuration, sports & departments management
templates/              Jinja2 HTML templates
static/css/style.css    All styling
static/js/app.js        Minimal JS helpers
tests.py                30 tests covering all critical paths
```

---

## Running Tests

```bash
pip install -r requirements.txt
python tests.py
```

---

## Honest Limitations

- No real-time data (no WebSockets, no live scores)
- Cricket NRR not calculated — requires ball-by-ball data we don't collect
- No user authentication — single-admin assumption
- Knockout result edits not supported after bracket progression
