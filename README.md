# MAiCampus

An AI-powered student companion for campus life. Built with [Flet](https://flet.dev) (Python) — runs on Desktop, Web, iOS, and Android.

## Vision

MAiCampus is designed to be the one app every student needs on campus. It combines an intelligent AI assistant with practical tools for managing academic work, campus facilities, and social life — all in one place.

### Feature Roadmap

| Priority | Feature | Status | Description |
|----------|---------|--------|-------------|
| 1 | **Class & Assignment Tracker** | In Progress | Track class schedules, assignment due dates, project deadlines, and exam prep time |
| 2 | **Facility Booking** | Planned | Book library rooms, study rooms, and sport facilities |
| 3 | **University Club App** | Planned | Browse clubs, enroll, admin management, elections, upcoming events |
| 4 | **Research Resources** | Planned | Gather research data, books, and past year papers |
| 5 | **AI Chatbot (MAI)** | Done | Intelligent assistant with tool calling (OpenAI, Claude, Gemini) |
| 6 | **Directions & Contacts** | Planned | Navigate to campus locations and contact professors |

---

## Pages

### Onboarding (First Launch)

When you open MAiCampus for the first time, a step-by-step wizard guides you through setup:

1. **Welcome** — Introduction to MAiCampus and what it can do
2. **Profile Setup** — Enter your name, email, and optionally upload a profile picture
3. **AI Provider** — Choose your AI provider (OpenAI, Claude, or Gemini) and enter your API key
4. **All Done** — Confirmation and jump into the app

The wizard is plugin-based — new onboarding steps can be added without changing existing code.


---

### Chat

The main conversation interface with MAI, your AI campus companion.

**What you can do:**
- **Ask MAI anything** about campus life — class schedules, study tips, club recommendations
- **Add events via conversation** — tell MAI "Add my Math 101 class on Monday 9am" and it uses native tool calling to create the calendar event
- **Check your schedule** — ask "What do I have this week?" and MAI queries your calendar
- **Get task priorities** — ask "What should I focus on?" and MAI ranks your assignments by urgency, estimated effort, and your past performance patterns
- **View chat history** — toggle the sidebar (hamburger menu) to see past conversations, switch between them, or start a new chat
- **Notification bell** — see alerts from the smart planner about upcoming deadlines
- **Scroll-to-bottom button** — quickly jump to the latest messages when scrolled up

MAI streams responses in real-time with a "thinking" indicator. You can navigate to other pages while MAI is responding — the response continues in the background.

![Chat with Check-In](docs/screenshots/ChatBot%20-%20With%20Check-In%20Capability.png)

---

### Calendar

A full calendar view for managing your academic and campus schedule.

**What you can do:**
- **Browse by month** — navigate between months with arrow buttons, jump to today
- **See events at a glance** — colored dots on each day indicate events (blue = class, orange = assignment, red = exam, green = club, purple = custom)
- **View day details** — click any day to see all events listed chronologically with colored type badges
- **Add events manually** — click the + button to open the event form with title, type, date/time, recurrence, description, and color
- **Edit and delete events** — manage events directly from the day detail panel
- **Recurring events** — set weekly recurrence (e.g. "every Monday and Wednesday")
- **Floating chat bubble** — chat with MAI directly from the calendar page without switching tabs. The floating chat has its own session history.

Events added via the calendar or via chat are stored in the same database and visible in both places.

![Calendar & Planning](docs/screenshots/Planning%20Study%20and%20Life.png)

---

### Settings

Configure your MAiCampus experience. Uses a NavigationRail layout with sections:

#### Profile
- Update your **name**, **email**, and **profile picture**
- Profile picture appears on your chat messages
- Changes persist across app restarts

#### Appearance
- Switch between **System**, **Light**, and **Dark** theme modes
- Uses a teal Material 3 color scheme

#### AI Provider
- Select your AI provider: **OpenAI**, **Claude (Anthropic)**, or **Google Gemini**
- Enter your **API key** (stored securely in platform key-value storage)
- Optionally override the default **model** (e.g. `gpt-4o`, `claude-sonnet-4-20250514`, `gemini-2.5-flash`)
- Settings auto-load on app startup

#### Smart Planner
- View what the **background scanner** does (checks deadlines, marks overdue tasks, generates alerts)
- **Run Scan Now** button — manually trigger the planner scan for testing or immediate alerts
- The planner normally runs automatically every 5 hours while the app is open

#### Reset App
- **Wipe all data** — clears profile, API keys, chat history, calendar events, AI memories, and preferences
- Requires typing "confirm" to prevent accidental resets
- Returns to the onboarding wizard after reset

![Settings](docs/screenshots/Setting%20Page.png)

---

## Smart Planner (Background)

The smart planner runs automatically and proactively helps you stay on track:

- **Scans every 5 hours** (and once on app startup) for upcoming assignments and exams
- **Overdue detection** — marks tasks as overdue and sends urgent notifications
- **Check-in prompts** — for tasks due within 3 days with unknown status, creates a notification asking "How's it going?"
- **Upcoming reminders** — gentle reminders for tasks due within 7 days
- **Clickable notifications** — tap a planner notification to open a dedicated **check-in chat session** where MAI asks about your progress
- **Check-in sessions** are visually distinct: orange banner at top, "[Check-in]" label in history, MAI initiates the conversation
- **Competency learning** — after you complete a task and report hours spent, MAI compares estimated vs actual time and stores the pattern in memory. Over time, MAI learns: "This student underestimates Physics tasks by 2x" and adjusts future priority scoring.

---

## AI Tool Calling

MAI uses **native tool calling** (not prompt-based parsing) for reliable calendar and task management:

| Tool | What it does |
|------|-------------|
| `create_calendar_event` | Add a new event to the calendar |
| `get_upcoming_events` | Query upcoming events for the next N days |
| `get_events_for_date` | Get all events for a specific date |
| `update_task_status` | Mark a task as pending, in progress, or completed |
| `log_task_completion` | Record actual hours spent and trigger competency learning |
| `get_priority_tasks` | Get a smart-ranked task list based on deadline, effort, and history |
| `get_student_competency` | Query the student's performance patterns for a subject |

Tool definitions are provider-agnostic and automatically converted to the correct format for OpenAI, Claude, or Gemini.

---

## Getting Started

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager

### Install & Run

```bash
# Clone the repo
git clone https://github.com/darwinsubramaniam/maicampus.git
cd maicampus

# Install dependencies
uv sync

# Run the app (desktop with hot reload)
uv run flet run --recursive src
```

### Other Platforms

```bash
# Web
uv run flet run --web --recursive src

# iOS
uv run flet run --ios --recursive src

# Android
uv run flet run --android --recursive src
```

## Architecture

```
src/
  main.py                    # App entry — navigation, view routing
  ai_providers.py            # Multi-provider AI streaming (OpenAI, Claude, Gemini)
  constants.py               # Shared constants and utility functions
  services.py                # Shared service instances (stores, memory getter)
  theme.py                   # Material 3 teal theme (light/dark)
  notifications.py           # In-app notification center
  prefs.py                   # SharedPreferences helper

  chat/                      # AI Chat Module
    chat_core.py             # ChatEngine — streaming, tool calling, system prompts
    message.py               # Chat bubble widget with avatars
    input_bar.py             # Message input + send button
    session_store.py         # TinyDB chat session persistence
    sidebar.py               # Toggleable chat history sidebar
    floating_chat.py         # Floating chat bubble for non-chat pages

  campus_calendar/           # Calendar Module
    event_model.py           # EventType/EventStatus enums, recurrence helpers
    event_store.py           # TinyDB calendar event persistence
    month_grid.py            # Custom month grid view
    day_detail.py            # Day event list panel
    event_form.py            # Add/edit event dialog
    calendar_memory.py       # AI memory integration for events

  tools/                     # AI Tool Calling System
    converters.py            # Provider-agnostic to OpenAI/Claude/Gemini format
    calendar_tools.py        # Calendar event tools
    planner_tools.py         # Task management and competency tools

  planner/                   # Smart Planner
    background.py            # Background scanner (5-hour interval + on startup)

  memory/                    # AI Memory (Mem0 + ChromaDB)
    manager.py               # Semantic knowledge extraction and retrieval

  settings/                  # Settings Module (NavigationRail)
    profile_settings.py      # Name, email, profile picture
    appearance_settings.py   # Theme mode toggle
    ai_settings.py           # Provider, API key, model
    planner_settings.py      # Manual scan trigger
    reset_settings.py        # App reset with confirmation

  bootstrap/                 # First-Run Onboarding
    wizard.py                # Generic step-by-step wizard engine
    pipeline.py              # Step ordering (plugin-based)
    steps/                   # Individual onboarding steps
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| UI Framework | [Flet](https://flet.dev) (Material 3, cross-platform) |
| AI Providers | OpenAI, Anthropic Claude, Google Gemini |
| AI Memory | [Mem0](https://mem0.ai) + [ChromaDB](https://www.trychroma.com/) |
| Database | [TinyDB](https://tinydb.readthedocs.io/) (JSON-backed, cross-platform) |
| Language | Python 3.14+ |
| Package Manager | [uv](https://docs.astral.sh/uv/) |

## Data Storage

All data is stored locally on the user's device:

| Data | Location | Engine |
|------|----------|--------|
| Chat sessions | `~/.maicampus/chat_history.json` | TinyDB |
| Calendar events | `~/.maicampus/calendar_events.json` | TinyDB |
| AI memories | `~/.maicampus/chroma_db/` | ChromaDB |
| Profile & settings | Platform key-value store | Flet SharedPreferences |
| Profile cache | `~/.maicampus/profile.json` | JSON file |

## Building

```bash
# Android
flet build apk -v

# iOS
flet build ipa -v

# macOS
flet build macos -v

# Windows / Linux / Web
flet build windows -v
flet build linux -v
flet build web -v
```

See the [Flet Packaging Guides](https://flet.dev/docs/publish/) for signing and distribution details.

## License

[MIT](LICENSE)
