# MAI Campus

An AI-powered student companion app built with Flet (Python). Helps students manage campus life —
classes, assignments, deadlines, facility bookings, social clubs, and more.

It runs as a **multi-tenant web server**: students sign in with **Google SSO** (restricted to UTM
accounts), and every user's data — chat history, calendar, AI memory, bookings — is fully isolated
in **SurrealDB**. A single server-side AI key (DeepSeek by default) powers chat for everyone, capped
by per-user daily limits.

## Prerequisites

- Python 3.14+ (see `pyproject.toml`)
- [uv](https://docs.astral.sh/uv/) package manager
- Docker + Docker Compose (for the full stack / SurrealDB / campus backend)

## Getting Started

### 1. Install dependencies

```bash
uv sync
```

### 2. Run the full stack with Docker Compose (recommended)

The stack is **SurrealDB + FastAPI campus backend + the Flet web app**. Copy the env template and
fill in your keys, then bring it up:

```bash
cp .env.sample .env        # then edit .env (see "Configuration" below)
docker compose up --build  # web: http://localhost:8550 · API: http://localhost:28000 (docs at /docs)
```

| Service | Host port | Notes |
|---|---|---|
| `webapp` | `http://localhost:8550` | The MAiCampus Flet app served as a website |
| `api` | `http://localhost:28000` | Campus backend (UKB + Facility Booking); OpenAPI docs at `/docs` |
| `surreal` | _(internal only)_ | SurrealDB — single datastore (per-user **and** campus data) |

- Both `api` and `webapp` connect to the **same** SurrealDB instance (namespace `maicampus`,
  database `app`) — campus reference data in its own tables, per-user data owner-scoped.
- The `api` `lifespan` waits for SurrealDB, defines the campus schema, then seeds (idempotent — a
  no-op once a student exists), anchored to the FOL scenario
  (MECS0033 · Darwin `MEC255043` · Mon 09:00–11:00 · Room N28 · Dr Shafaatunnur).
- Backend only (no web app): `docker compose up --build surreal api`.
- `docker compose down` keeps data in the `surrealdata` volume; `down -v` wipes it (forces re-seed).

### 3. Run locally for UI iteration (`flet run`)

```bash
uv run flet run --web --recursive src     # or: --recursive src (desktop), --ios, --android
```

- With **no Google credentials** set, the app auto-signs-in as a **local demo user**
  (`student_id = MEC255043`) so you can iterate on the UI offline — no login, no Docker.
- Per-user data uses an **embedded, file-backed SurrealDB** at `~/.maicampus/surreal.db` (the
  `surrealkv://` engine bundled with the Python SDK), so it persists across restarts.
- UKB / Facility features still call the campus API (`http://localhost:28000`); run
  `docker compose up surreal api` alongside, or they degrade gracefully to a "service unavailable"
  message.
- `--recursive` (`-r`) watches `src/` and auto-reloads on save.

## Configuration (env vars)

All config is via environment variables. Docker Compose auto-loads `.env`; `.env` is gitignored,
`.env.sample` is the committed template.

| Variable | Purpose | Default |
|---|---|---|
| `MAICAMPUS_GOOGLE_CLIENT_ID` / `_SECRET` | Google OAuth web client | _(unset → local demo user)_ |
| `MAICAMPUS_GOOGLE_REDIRECT_URL` | Must match an Authorized redirect URI in Google Console **and** where the app is browsed | `http://localhost:8550/oauth_callback` |
| `MAICAMPUS_ALLOWED_EMAIL_DOMAINS` | Comma-separated allowed sign-in domains (subdomains included). `*`/empty = any account | `utm.my` |
| `MAICAMPUS_AI_PROVIDER` | Chat provider (`deepseek`/`openai`/`claude`/`gemini`) | `deepseek` |
| `MAICAMPUS_AI_API_KEY` | Server-side chat key (shared by all users) | _(empty)_ |
| `MAICAMPUS_AI_MODEL` | Optional chat model override | provider default (`deepseek-chat`) |
| `MAICAMPUS_EMBED_API_KEY` | OpenAI key for **memory embeddings** (DeepSeek has none) | _(empty → memory off)_ |
| `MAICAMPUS_EMBED_MODEL` / `_DIM` | Embedding model + vector dimension | `text-embedding-3-small` / `1536` |
| `MAICAMPUS_DAILY_LIMIT` | Per-user chat messages per day | `50` |
| `MAICAMPUS_SURREAL_URL` / `_USER` / `_PASS` / `_NS` / `_DB` | SurrealDB connection (unset URL → embedded local file) | `ws://surreal:8000/rpc` … `maicampus`/`app` |
| `MAICAMPUS_API_BASE` | Campus API base URL | `http://localhost:28000` (Docker webapp → `http://api:8000`) |
| `MAICAMPUS_CF_TUNNEL_TOKEN` | Cloudflare named-tunnel token (optional) | _(empty)_ |

## Features

### Authentication & multi-tenancy
- **Google SSO** via Flet's native `GoogleOAuthProvider`; the whole app is gated behind login.
- **UTM-only** sign-in enforced server-side (`MAICAMPUS_ALLOWED_EMAIL_DOMAINS`, default `utm.my` —
  covers `@utm.my`, `@graduate.utm.my`, …). Non-UTM accounts get an "UTM account required" screen.
- Account chooser is forced (`prompt=select_account`) so users can switch accounts; when restricted
  to one domain, Google's `hd` hint pre-filters the chooser.
- **Per-user isolation:** every per-user record carries an `owner = user:<google-sub>` link, and
  every query filters by it — one user can never see another's chats, calendar, memory, or bookings.

### AI Chat
- Streaming responses from a **single server-side key** (DeepSeek by default; OpenAI/Claude/Gemini
  supported). No per-user API keys.
- "MAI is thinking…" spinner; user/MAI avatars; red error bubbles; background streaming.
- Floating scroll-to-bottom button; floating chat bubble on the Calendar/Booking tabs.

### Chat History
- Per-user chat sessions in SurrealDB (`chat_session`), owner-scoped.
- Toggleable sidebar with relative timestamps, auto-title, session switching, delete, auto-load most
  recent on startup.

### AI Memory (SurrealDB vectors)
- Long-term memory stored as `memory` records with a 1536-dim embedding and an HNSW vector index.
- Embeddings via the **OpenAI embeddings API** (`text-embedding-3-small`) — no local model / torch.
- Semantic recall (cosine similarity) injected as RAG context, scoped to the owner.
- **Best-effort / fail-soft:** a missing/failed embedding never breaks chat or booking.

### Daily usage limits
- Per-user, per-day counters in `usage_daily` (id `[user_id, date]`); checked before each AI call.
- Over the limit → a friendly "daily limit reached" message instead of streaming. Date-keyed records
  self-reset at midnight (no cron).

### Navigation
- Bottom `NavigationBar`: **Chat · Calendar · Booking · Settings** (compact height for web).
- Views swap in a single `Container`; chat streaming continues across tabs. Calendar and Booking
  expose a `refresh()` (re-queries on show) so a change made in one tab (or in chat) is reflected
  when you switch to the other — no stale data.

### Facility Booking (Flow 6)
- **Booking** tab: search facilities → pick date/time → check availability → book, plus a **My
  Bookings** panel to **reschedule** or **cancel** existing bookings — driven by the same
  `reschedule_booking` / `cancel_booking` tools chat uses, so the Facility API and the calendar
  mirror stay in sync.
- Conflict detection against BOTH the facility (server) and the user's own calendar; conflicts show a
  red banner + clickable suggested free-slot chips.
- On confirm: booking saved to the Facility API and mirrored onto the user's calendar + a
  notification. The same `book_facility` tool powers chat, so MAI can book conversationally too.

### Calendar editing & booking linkage
- Regular calendar events are edited/deleted in place. Events that **mirror a facility booking**
  (tagged with `booking_id` / `facility_id`; `booking_id_of()` is the single detector) can't be
  edited in place — that wouldn't reach the Facility API — so they show a **"Manage in Booking"**
  action that deep-links to the Booking tab focused on that booking.

### University Knowledge Base (UKB)
- Chatbot tools answer schedule/course/club/facility questions from the UKB service.
- **Settings → Knowledge → "Sync from Knowledge Base"** imports the signed-in student's classes into
  their calendar (recurring weekly events, deduped by `(title, weekday)`).

### Settings
- **Profile**: read-only, sourced from the `user` record (Google name, email, photo, linked matric).
- **Appearance**: theme mode (System / Light / Dark).
- **Knowledge**: "Sync from Knowledge Base" + API health checks.
- **Planner**: manual Smart Planner scan.
- **Logout**: sign out of the Google session (no destructive data wipe in multi-user mode).
- _(The per-user "AI Provider" key UI is removed — the key is server-managed.)_

### Theming
- Material 3 (teal), light/dark with system default, theme-aware components.

## Architecture

### Identity & per-user resolution
```
Google login → on_login → email allowlist check (UTM) → resolve_user_context()
  → upsert user:<sub> {name,email,picture,student_id}  → UserContext(user_id, student_id)
  → stored in main()'s per-connection closures (main(page) runs once per client)
```
Tools are module-level singletons shared across users, so the current `UserContext` is carried in a
**ContextVar** that `tools.execute()` sets around each handler (works across the background threads
the views spawn). Store factories in `services.py` resolve the owner from it and **fail closed** when
no context is set — never leaking another user's data. `campus_api` reads the linked `student_id`
from the same context.

### Streaming flow
```
User sends message
  → daily-limit check (usage_daily)         → over limit → friendly message, stop
  → "MAI is thinking…" (ProgressRing)
  → background thread produces chunks via stream_response() (server-side key)
  → asyncio.Queue bridges thread → event loop; each chunk updates the bubble
  → tool calls run via tools.execute(name, args, user_ctx)  (owner-scoped)
  → on complete: save session to SurrealDB + store memory (embed via OpenAI, best-effort)
```

### Data layer (one SurrealDB, three models)
- **Records** — `user`, `chat_session`, `calendar_event`, `usage_daily` (per-user, `owner`-scoped);
  campus `lecturer`, `student`, `course`, `club`, `facility`, `booking`.
- **Graph** — `student ->enrolled-> course` edges; `course.lecturer` record link; timetables embedded
  on `course`.
- **Vector** — `memory.embedding` with an `HNSW … DIST COSINE` index for semantic recall.

`src/db/surreal.py` is the blocking client (the SDK is async-first, but all stores are called from
sync code): `ws://` to the server in Docker, or an embedded `surrealkv://` file for local dev.

## Campus Backend (UKB + Facility Booking)

Two campus services — the **University Knowledge Base (UKB)** and the **Facility Booking API** — are
modelled as an **external FastAPI backend on SurrealDB**, so the prototype demonstrates a realistic
*client → service → database* flow (assignment Flow 3/4 and Flow 6). It is a separate Docker service
with its own deps (`mock_server/requirements.txt`).

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/ukb/courses` (`?code=&day=&lecturer=`) | Course catalogue (filterable) |
| GET | `/ukb/courses/{code}` | One course + timetable (day, time, room, lecturer) |
| GET | `/ukb/students/{id}` | Student profile + enrolled course codes (via graph) |
| GET | `/ukb/students/{id}/timetable` | Weekly schedule (enrolled edges × embedded timetables) |
| GET | `/ukb/clubs` (`?interest=`) | Club directory |
| GET | `/ukb/facilities` | Facility metadata (hours, capacity, rules) |
| GET | `/facility/facilities` (`?type=`) | Bookable facilities |
| GET | `/facility/availability` (`?facility_id=&date=`) | Hourly slots with `available` flags |
| POST | `/facility/bookings` | Create booking — **HTTP 409 on overlap** (conflict prevention) |
| GET | `/facility/bookings` (`?student_id=`) | A student's confirmed bookings |
| DELETE | `/facility/bookings/{id}` | Cancel a booking |

The API surface and response schemas are unchanged from the previous Postgres version, so
`src/campus_api.py` and the OpenAPI docs are identical; only the storage moved to SurrealDB.

### How the app plugs in

```
Flet app                                  Campus backend (FastAPI)        SurrealDB
--------                                  ------------------------        ---------
src/campus_api.py ──httpx──▶ /ukb/* /facility/* (student_id from ctx) ──▶ records + enrolled graph
  ▲ friendly {"error": ...} on connection failure / non-2xx

src/db/surreal.py ─────────────────────────────────────────────────────▶ per-user records + vectors
```

- **Graceful degradation:** `src/campus_api.py` catches httpx errors and returns `{"error": ...}`, so
  tools and the Booking UI show a friendly "service unavailable" message when the backend is down.
- The booking flow (Flow 6) is one chain in `book_facility`: server availability → calendar clash →
  `POST /facility/bookings` (409-safe) → mirror onto the calendar (teal `#00897B`) → notification.

### OpenAPI docs
FastAPI auto-generates **OpenAPI 3.1.0** from `mock_server/schemas.py`: Swagger UI at `/docs`, ReDoc
at `/redoc`, raw spec at `/openapi.json`.

## Deployment (Cloudflare Tunnel)

`docker-compose.yml` includes an optional `cloudflared` service (opt-in `tunnel` profile) to expose
the webapp at a public domain without inbound ports:

```bash
# 1. Create a named tunnel in the Cloudflare Zero Trust dashboard; put its token in MAICAMPUS_CF_TUNNEL_TOKEN.
# 2. In the dashboard, route the public hostname → http://webapp:8550 (cloudflared shares the compose network).
# 3. Set MAICAMPUS_GOOGLE_REDIRECT_URL=https://<your-domain>/oauth_callback and register it in Google Console.
docker compose --profile tunnel up -d --build
```

WebSockets (which Flet's UI needs) pass through automatically; don't put Cloudflare caching in front.

## Project Structure

```
src/
  main.py                    # Entry — auth gate, per-user wiring, NavigationBar, server AI config
  ai_providers.py            # Provider streaming + server_config_from_env() (DeepSeek default)
  services.py                # UserContext + ContextVar; per-user store/memory factories (fail-closed)
  theme.py                   # Light/dark themes; page padding/spacing
  constants.py               # APP_DIR + DEFAULT_STUDENT_ID (demo fallback)
  campus_api.py              # httpx client for the campus backend (student_id from context)

  auth/
    provider.py              # GoogleOAuthProvider + UTM email allowlist + account-chooser params
    session.py               # resolve_user_context: upsert user, link student, build UserContext

  db/
    surreal.py               # SurrealDB blocking client, schema (HNSW vector index), normalize

  usage/
    limiter.py               # Per-user daily limits (usage_daily) — check_and_increment / record_tokens

  memory/
    manager.py               # Per-user MemoryManager on SurrealDB vectors (best-effort)
    embedder.py              # OpenAI embeddings (text-embedding-3-small)

  facility_booking/__init__.py  # Booking tab (Flow 6), per-user, passes UserContext to tools
  campus_calendar/
    __init__.py              # Calendar view (injected per-user store)
    event_store.py           # CalendarEventStore on SurrealDB (owner-scoped)

  chat/
    __init__.py              # Chat view — sidebar, sessions, identity from Google
    chat_core.py             # ChatEngine — streaming, tools (UserContext), daily-limit enforcement
    session_store.py         # SessionStore on SurrealDB (owner-scoped)
    floating_chat.py, message.py, input_bar.py, sidebar.py

  tools/
    __init__.py              # Registry + execute(name, args, context) — sets the request ContextVar
    calendar_tools.py, facility_tools.py, ukb_tools.py, planner_tools.py, converters.py

  settings/
    __init__.py              # Settings (NavigationRail): Profile, Appearance, Knowledge, Planner, Logout
    profile_settings.py      # Read-only profile from the user record
    appearance_settings.py, knowledge_settings.py, planner_settings.py
    logout_settings.py       # Sign out (was reset_settings.py)

  bootstrap/                 # Legacy first-run wizard — superseded by the login gate (unused)

mock_server/                 # Campus backend (FastAPI + SurrealDB) — separate Docker service
  app.py                     # lifespan = wait_for_db → define_schema → seed
  db.py                      # SurrealDB blocking client + campus schema + query helper
  schemas.py                 # Pydantic schemas (drive the OpenAPI docs)
  seed.py                    # UTM/Malaysian seed (records + enrolled edges), FOL-anchored, idempotent
  routers/ukb.py, routers/facility.py   # /ukb/* and /facility/* (409 on conflict)
  requirements.txt           # fastapi, uvicorn, surrealdb (image-only deps)

Dockerfile.web               # Serves the Flet app as a website (uv sync --group web)
docker-compose.yml           # surreal + api + webapp (+ optional cloudflared tunnel profile)
.env.sample                  # Env template (.env is gitignored)
```

## Key Dependencies

- `flet` — cross-platform UI framework (Material 3), incl. native Google OAuth
- `surrealdb` — single datastore (records + graph + vector) for per-user and campus data
- `openai` — chat (OpenAI-compatible, incl. DeepSeek) **and** memory embeddings
- `anthropic`, `google-genai` — alternative chat providers
- `httpx` — HTTP client for the campus backend (`src/campus_api.py`)
- **Campus backend only** (in `mock_server/requirements.txt`, Docker image — not in app `pyproject.toml`):
  `fastapi`, `uvicorn`, `surrealdb`

## Data Storage

| Data | Location | Mechanism |
|------|----------|-----------|
| Users (name, email, photo, matric) | SurrealDB `user` | owner = Google `sub` |
| Chat sessions | SurrealDB `chat_session` | owner-scoped records |
| Calendar events | SurrealDB `calendar_event` | owner-scoped records |
| AI memory | SurrealDB `memory` | owner-scoped + HNSW vector index |
| Daily usage | SurrealDB `usage_daily` | id `[user_id, date]` |
| Courses, timetables, clubs, facilities, bookings, enrollments | SurrealDB (campus tables + `enrolled` edges) | seeded by the `api` service |
| Local-dev per-user data | `~/.maicampus/surreal.db` | embedded `surrealkv://` |

## Flet Notes

- `main(page)` runs **once per connected client**, so its closures are naturally per-user.
- Google OAuth: `page.login(provider)`, `page.on_login`, `page.auth.user` (a `User` dict; `.id` =
  Google `sub`, plus `email`/`name`/`picture`).
- `page.update()` from background threads may not flush UI — use `page.run_task()` for async updates.
- The SurrealDB SDK is async-first; this app uses its **blocking** client to keep sync store APIs.

## Flet Reference

- Docs: https://flet.dev/docs · Controls: https://flet.dev/docs/controls
- Authentication: https://flet.dev/docs/cookbook/authentication
- Theming: https://flet.dev/docs/cookbook/theming · CLI: https://flet.dev/docs/cli/flet-run
