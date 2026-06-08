# MAI Campus

An AI-powered student companion app built with Flet (Python). Helps students manage campus life — classes, assignments, deadlines, facility bookings, social clubs, and more.

## Prerequisites

- Python 3.14+ (see `pyproject.toml`)
- [uv](https://docs.astral.sh/uv/) package manager

## Getting Started

### 1. Install dependencies

```bash
uv sync
```

### 2. Run the app (with hot reload)

**Desktop** (native OS window):
```bash
uv run flet run --recursive src
```

**Web** (browser):
```bash
uv run flet run --web --recursive src
```

**iOS** (simulator or device):
```bash
uv run flet run --ios --recursive src
```

**Android** (emulator or device):
```bash
uv run flet run --android --recursive src
```

- `--recursive` (`-r`) watches `src/` and all subdirectories for changes and auto-reloads on save

### 3. Run the stack with Docker Compose (mock backend + web app)

The University Knowledge Base and Facility Booking features call an external mock backend, and the
whole app can also be served as a website. All of it runs via Docker Compose (three services:
`db`, `api`, `webapp`):

```bash
docker compose up --build
```

| Service | Host port | Notes |
|---|---|---|
| `webapp` | `http://localhost:8550` | The MAiCampus Flet app served as a website |
| `api` | `http://localhost:28000` | Mock backend (UKB + Facility Booking); OpenAPI docs at `/docs` |
| `db` | _(internal only)_ | Postgres 18 — no host port (shared-server friendly) |

- Mock backend lives in `mock_server/`, seeded (`mock_server/seed.py`) with a UTM/Malaysian dataset
  anchored to the FOL scenario (MECS0033 · Darwin `MEC255043` · Mon 09:00–11:00 · Room N28 · Dr Shafaatunnur).
- The **webapp** runs Python server-side, so it reaches the API over the compose network at
  `http://api:8000` (set via `MAICAMPUS_API_BASE`).
- A **locally-run** app (`uv run flet run`) uses `constants.API_BASE_URL` (default
  `http://localhost:28000`, override with `MAICAMPUS_API_BASE`) through `src/campus_api.py` (httpx);
  calls degrade gracefully when the backend is down.
- To run only the backend (no web app): `docker compose up --build db api`.

## Features

### AI Chat
- Streaming AI responses from OpenAI, Claude, or Gemini (configurable)
- "MAI is thinking..." loading indicator with spinner before response streams in
- Chat messages with user profile pic/name and "MAI" AI branding (school icon)
- Error messages displayed as distinct red bubbles
- Background streaming — user can navigate to Settings while AI responds
- Floating scroll-to-bottom button when scrolled up in chat

### Chat History
- Multiple chat sessions persisted via TinyDB (`~/.maicampus/chat_history.json`)
- Toggleable inline sidebar (hamburger menu) showing session list with relative timestamps
- Auto-title from first user message
- Session switching with full conversation restore
- Delete sessions
- Most recent session auto-loads on startup

### AI Memory (Mem0 + ChromaDB)
- Long-term knowledge extraction from conversations via Mem0
- Semantic search of past memories injected as context (RAG)
- Local ChromaDB vector storage at `~/.maicampus/chroma_db`
- Per-student memory scoping (user_id)

### Navigation
- Bottom NavigationBar with Chat and Settings tabs
- Both views stay in page tree (Stack) — streaming continues when on Settings tab
- Chat header with hamburger menu toggle for history sidebar

### Facility Booking (Flow 6)
- Dedicated **Booking** tab: search facilities by type → pick date/time → check availability
- Conflict detection against BOTH the facility (server) and the student's own calendar
- Conflicts show a red banner + suggested free slots (clickable chips auto-fill the time)
- On confirm: booking saved to the Facility API and mirrored onto the calendar + a notification
- Same `book_facility` tool powers chat, so MAI can book conversationally too
- Backed by the [mock campus backend](#mock-campus-backend-ukb--facility-booking)

### University Knowledge Base (UKB)
- Chatbot tools answer schedule/course/club/facility questions from the UKB service
  (e.g. "Do I have class on Monday?", "When does the library close?", "Which clubs focus on tech?")
- **Settings → Knowledge → "Sync from Knowledge Base"** imports the student's classes into the calendar
- Backed by the [mock campus backend](#mock-campus-backend-ukb--facility-booking)

### Onboarding (Bootstrap Wizard)
- Step-by-step first-run setup: Welcome → Profile → AI Provider → Done
- Plugin-based step system — add/remove/reorder steps in `bootstrap/pipeline.py`
- Reusable generic wizard engine (`bootstrap/wizard.py`)

### Settings
- **Profile**: name, email, profile picture with file picker (persisted via `shared_preferences`)
- **Appearance**: theme mode toggle (System / Light / Dark)
- **AI Provider**: provider selection, API key, model override (auto-loads on startup)
- **Reset App**: wipes all data (storage + ChromaDB), returns to bootstrap with "confirm" guard

### Theming
- Material 3 with indigo color scheme
- Light and dark themes with system default
- Theme-aware chat bubbles and UI components

## Architecture

### Streaming Flow
```
User sends message
  → show "MAI is thinking..." (ProgressRing)
  → background thread produces chunks via stream_response()
  → asyncio.Queue bridges thread → main event loop
  → each chunk updates body_text + page.update() from async context
  → on complete: save to TinyDB + extract memories via Mem0
```

### Navigation Model
```
main.py
  → ft.Stack([chat_view, settings_view])  # both always in tree
  → NavigationBar toggles visibility
  → chat streaming works even when settings_view is visible
```

## Mock Campus Backend (UKB + Facility Booking)

Two campus services — the **University Knowledge Base (UKB)** and the **Facility Booking API** —
are modelled as an **external mock HTTP backend** rather than local files, so the prototype
demonstrates a realistic *client → service → database* flow (assignment Flow 3/4 and Flow 6).

### Stack & how to run

`docker-compose.yml` (repo root) defines three services:

| Service | Build | Host port | Role |
|---|---|---|---|
| `db` | `postgres:18` | _internal only_ | Database (volume `pgdata`) |
| `api` | `mock_server/` (FastAPI) | `28000` → 8000 | UKB + Facility Booking API |
| `webapp` | `Dockerfile.web` (Flet) | `8550` | The app served as a website |

```bash
docker compose up --build          # web: http://localhost:8550  ·  API: http://localhost:28000 (docs at /docs)
docker compose up --build db api   # backend only (no web app)
docker compose down                # stop (keeps data in pgdata / appdata volumes)
docker compose down -v             # stop + wipe volumes (forces a fresh DB re-seed on next up)
```

The `api` startup `lifespan` waits for Postgres, runs `Base.metadata.create_all`, then calls `seed()`
(idempotent — no-op once the `students` table is populated), so `up` always boots a fully seeded API.
The `webapp` is the MAiCampus Flet app built with `Dockerfile.web`; Python runs server-side and reaches
the API over the compose network at `http://api:8000` (via `MAICAMPUS_API_BASE`). Postgres has **no host
port** so it won't clash with other stacks on a shared server.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/ukb/courses` (`?code=&day=&lecturer=`) | Course catalogue (filterable) |
| GET | `/ukb/courses/{code}` | One course + timetable (day, time, room, lecturer) |
| GET | `/ukb/students/{id}` | Student profile + enrolled course codes |
| GET | `/ukb/students/{id}/timetable` | Weekly class schedule (enrollments × timetables) |
| GET | `/ukb/clubs` (`?interest=`) | Club directory |
| GET | `/ukb/facilities` | Facility metadata (hours, capacity, rules) |
| GET | `/facility/facilities` (`?type=`) | Bookable facilities |
| GET | `/facility/availability` (`?facility_id=&date=`) | Hourly slots with `available` flags |
| POST | `/facility/bookings` | Create booking — **HTTP 409 on overlap** (conflict prevention) |
| GET | `/facility/bookings` (`?student_id=`) | A student's confirmed bookings |
| DELETE | `/facility/bookings/{id}` | Cancel a booking |

### Data model & seed

Postgres tables (SQLAlchemy ORM in `mock_server/models.py`): `lecturers`, `students`, `courses`,
`timetable_entries`, `enrollments`, `clubs`, `facilities`, `bookings`. The seed
(`mock_server/seed.py`) is a UTM / Malaysian dataset **anchored to the assignment's FOL proof** so the
resolution-refutation scenario is reproducible:

> **MECS0033** *Artificial Intelligence* · **Dr Shafaatunnur Hasan** · **Monday 09:00–11:00 · Room N28**,
> with student **Darwin Subramaniam (`MEC255043`)** enrolled.

It is broadened with ~8 lecturers, ~12 students (incl. the real Group 2 members), ~8 courses, ~8
facilities (PSZ discussion rooms, study pods, badminton/futsal courts), ~6 clubs, and a few
pre-existing bookings so availability/conflict works out of the box.

### How the app plugs in

```
Flet app                          Mock backend
--------                          ------------
src/campus_api.py  ──httpx──▶  GET/POST  http://localhost:8000  ──▶  Postgres
  ▲ friendly {"error": ...} on connection failure / non-2xx

src/tools/ukb_tools.py        → query_my_timetable, lookup_course, list_clubs,
                                get_facility_info, sync_my_classes
src/tools/facility_tools.py   → search_facilities, check_facility_availability, book_facility
src/facility_booking/         → Booking tab UI (calls the same tools, not the client directly)
src/settings/knowledge_settings.py → "Sync from Knowledge Base" button
```

- **Config:** `constants.API_BASE_URL` (default `http://localhost:28000` for a locally-run app; the
  Docker `webapp` overrides it to `http://api:8000` — both via the `MAICAMPUS_API_BASE` env var) and
  `constants.DEFAULT_STUDENT_ID` (`MEC255043`, the demo student).
- **Graceful degradation:** `src/campus_api.py` catches httpx errors and returns `{"error": ...}`, so
  tools and the Booking UI show a friendly "service unavailable" message when the backend is down —
  the app never crashes.

### Facility booking flow (Flow 6 — in `book_facility`)

```
book_facility(facility_id, date, start, end)
  1. GET /facility/availability        → is the server slot free?      ── no → conflict + suggested slots
  2. calendar_store.get_events_for_date → does it clash with the         ── yes → conflict + suggested slots
                                          student's own calendar?
  3. POST /facility/bookings           → confirm (409-safe)
  4. calendar_store.create_event(...)  → mirror booking onto the calendar (teal #00897B)
  → returns {"booked": True, ...}; main.py `_on_tool_executed` raises a notification
```

The chatbot and the Booking UI share this exact path, so *"book a study pod tomorrow 2–4pm"* in chat
and the Booking tab behave identically.

### UKB → calendar sync (Flow 5 / Flow 8)

`sync_timetable_from_ukb()` (in `ukb_tools.py`, exposed as the `sync_my_classes` tool and the
**Settings → Knowledge → "Sync from Knowledge Base"** button) pulls the student's UKB timetable and
creates recurring weekly `CLASS` events, deduped by `(title, weekday)` so re-running is safe.

### OpenAPI docs

FastAPI auto-generates **OpenAPI 3.1.0** from the Pydantic schemas in `mock_server/schemas.py`:
Swagger UI at `/docs`, ReDoc at `/redoc`, raw spec at `/openapi.json`.

## Project Structure

```
src/
  main.py                    # App entry — NavigationBar routing, Stack layout
  ai_providers.py            # Provider abstraction (OpenAI, Claude, Gemini) with streaming
  theme.py                   # Light/dark theme definitions
  constants.py               # Paths + API_BASE_URL / DEFAULT_STUDENT_ID for the mock backend
  campus_api.py              # httpx client for the mock backend (UKB + Facility Booking)

  facility_booking/
    __init__.py              # Booking tab (Flow 6: search → availability + calendar conflict → confirm)

  tools/
    __init__.py              # ToolDefinition registry (register / get_all / execute)
    converters.py            # Provider-agnostic → OpenAI/Claude/Gemini tool formats
    calendar_tools.py        # Calendar event tools
    planner_tools.py         # Task management + competency tools
    ukb_tools.py             # UKB lookups (timetable, course, clubs, facility info) + sync
    facility_tools.py        # Facility search / availability / book_facility (Flow 6 chain)

  bootstrap/
    __init__.py              # Bootstrap flow: is_bootstrapped, create_bootstrap_view
    wizard.py                # Generic step-by-step wizard engine
    pipeline.py              # Step ordering — add/remove/reorder here
    steps/
      welcome.py             # Welcome screen
      profile.py             # Name, email, photo setup
      ai_provider.py         # API key configuration
      done.py                # Confirmation screen

  chat/
    __init__.py              # Chat view — sidebar, messages, input, sessions, streaming
    message.py               # ChatMessage widget with avatars, loading state, error state
    input_bar.py             # Text input + send button
    session_store.py         # TinyDB wrapper for chat session persistence
    sidebar.py               # Toggleable session list sidebar

  memory/
    __init__.py              # Exports MemoryManager
    manager.py               # Mem0 + ChromaDB wrapper for semantic knowledge

  settings/
    __init__.py              # Settings page (NavigationRail sections)
    profile_settings.py      # Profile CRUD (shared_preferences + FilePicker)
    appearance_settings.py   # Theme mode toggle
    ai_settings.py           # AI provider config + persistence
    knowledge_settings.py    # "Sync from Knowledge Base" (UKB → calendar)
    planner_settings.py      # Manual Smart Planner scan trigger
    reset_settings.py        # App reset with confirmation

  assets/
    icon.png                 # App icon

mock_server/                 # Mock UTM backend (FastAPI + Postgres 18) — run via Docker Compose
  Dockerfile                 # python:3.14-slim image
  requirements.txt           # fastapi, uvicorn, sqlalchemy, psycopg (image-only deps)
  app.py                     # FastAPI app; lifespan = wait_for_db → create_all → seed
  db.py                      # SQLAlchemy engine/session from DATABASE_URL + wait_for_db
  models.py                  # ORM tables (lecturers, students, courses, timetable, …, bookings)
  schemas.py                 # Pydantic request/response schemas (drive the OpenAPI docs)
  seed.py                    # UTM/Malaysian seed anchored to the FOL scenario (idempotent)
  routers/ukb.py             # /ukb/* read endpoints
  routers/facility.py        # /facility/* read + booking (409 on conflict)
Dockerfile.web               # Image that serves the Flet app as a website (uv sync --group web)
docker-compose.yml           # `db` (postgres:18) + `api` (FastAPI) + `webapp` (Flet web) services
```

## Key Dependencies

- `flet` — cross-platform UI framework (Material 3)
- `anthropic`, `openai`, `google-genai` — AI provider SDKs
- `mem0ai` — conversation memory extraction
- `chromadb` — local vector database
- `tinydb` — JSON-backed document database for chat history
- `httpx` — HTTP client for the mock campus backend (`src/campus_api.py`)
- **Mock backend only** (in `mock_server/requirements.txt`, installed in the Docker image — NOT in the
  app's `pyproject.toml`): `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg`

## Data Storage

| Data | Location | Mechanism |
|------|----------|-----------|
| Profile, API keys, preferences | Platform key-value store | `page.shared_preferences` |
| Chat sessions | `~/.maicampus/chat_history.json` | TinyDB |
| Calendar events | `~/.maicampus/calendar_events.json` | TinyDB |
| AI memories | `~/.maicampus/chroma_db/` | ChromaDB |
| Courses, timetables, clubs, facilities, bookings | `http://localhost:8000` (`pgdata` volume) | **External** mock backend (Postgres 18) |

## Flet Notes

- `page.update()` from background threads may not flush UI — use `page.run_task()` for async updates
- `FilePicker` is a Service control — use `ft.FilePicker().pick_files()` inline (auto-registers)
- `shared_preferences` is deprecated in Flet 0.80+ — will need migration to `SharedPreferences()` class
- SQLite crashes on iOS (flet-dev/flet#5480) — TinyDB used instead for cross-platform compat

## Flet Reference

- Docs: https://flet.dev/docs
- Controls: https://flet.dev/docs/controls
- Services: https://flet.dev/docs/services/filepicker
- Theming: https://flet.dev/docs/cookbook/theming
- Client Storage: https://flet.dev/docs/cookbook/client-storage
- CLI: https://flet.dev/docs/cli/flet-run
