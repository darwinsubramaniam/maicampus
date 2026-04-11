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

## Project Structure

```
src/
  main.py                    # App entry — NavigationBar routing, Stack layout
  ai_providers.py            # Provider abstraction (OpenAI, Claude, Gemini) with streaming
  theme.py                   # Light/dark theme definitions

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
    __init__.py              # Settings page with ExpansionTile sections
    profile_settings.py      # Profile CRUD (shared_preferences + FilePicker)
    appearance_settings.py   # Theme mode toggle
    ai_settings.py           # AI provider config + persistence
    reset_settings.py        # App reset with confirmation

  assets/
    icon.png                 # App icon
```

## Key Dependencies

- `flet` — cross-platform UI framework (Material 3)
- `anthropic`, `openai`, `google-genai` — AI provider SDKs
- `mem0ai` — conversation memory extraction
- `chromadb` — local vector database
- `tinydb` — JSON-backed document database for chat history

## Data Storage

| Data | Location | Mechanism |
|------|----------|-----------|
| Profile, API keys, preferences | Platform key-value store | `page.shared_preferences` |
| Chat sessions | `~/.maicampus/chat_history.json` | TinyDB |
| AI memories | `~/.maicampus/chroma_db/` | ChromaDB |

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
