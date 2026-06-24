# MAI Campus User Manual (automated)

A student-facing PDF user manual whose screenshots are captured automatically by driving the
real app with Playwright, then composited into a PDF from Markdown via WeasyPrint.

```
manual.md              source content (Markdown; references images/*.png)
style.css              print stylesheet (cover, page numbers, figures, callouts)
capture.py             Playwright: launches the app, drives each screen, writes annotated PNGs
seed_demo_profile.py   gives the demo user a name/email so the Profile screen isn't empty
build_pdf.py           Markdown -> HTML -> WeasyPrint -> MAiCampus-User-Manual.pdf
build.py               one-shot: run every capture flow, then render the PDF
images/                generated PNGs (annotated <name>.png + clean <name>-raw.png)
MAiCampus-User-Manual.pdf   the output
```

The capture flows, in document order: `login`, `chat` (welcome, a real Q&A, history),
`calendar` (month, add-event), `booking` (search, conflict, confirmed, calendar mirror),
`settings` (profile, appearance, knowledge, planner, logout). The booking flow is the most
involved: it syncs the timetable, hits a real calendar clash at 14:00, then books a free slot.

## How it works

- **Auth-free capture.** The app is launched with the AI key from `.env` but *without* Google
  credentials, so `google_oauth_configured()` is false and it auto-signs-in as the demo
  student (`MEC255043`). No login to script.
- **Deterministic & non-destructive.** Per-user data is routed to an isolated, throwaway
  `surrealkv://` store under the system temp dir (wiped before each run), so captures are
  reproducible and your real `~/.maicampus` data is never touched. The campus API
  (`docker compose up -d surreal api`) is started best-effort so MAI answers with the real
  FOL-seeded timetable/booking data.
- **Canvas-aware.** The app renders through Flutter web (a `<canvas>`), so there are no HTML
  elements to select. Navigation is coordinate-driven (fractions of a fixed viewport) and
  "done rendering?" is decided by watching the screenshot stop changing (`wait_stable`).
- **Annotations** are HTML overlays drawn on top of the canvas (numbered teal dots plus an
  optional legend), then captured. No external image editor is needed.

## Prerequisites (one-time)

```bash
uv sync --group docs                 # playwright, markdown, weasyprint, …
uv run playwright install chromium   # headless browser
# WeasyPrint system libs (macOS): brew install pango gdk-pixbuf libffi
# Docker running, for the campus API (optional but recommended for real data)
```

## Regenerate

```bash
uv run python docs/user-manual/build.py             # capture everything + build the PDF
# or step by step:
uv run python docs/user-manual/capture.py booking   # re-shoot one flow (login/chat/calendar/booking/settings)
uv run python docs/user-manual/build_pdf.py         # just rebuild the PDF from existing images
```

## Notes

- Chat answers come from a live LLM, so the exact wording/format of a reply varies between
  runs (e.g. bullet list vs. table). Re-run a flow if you want a cleaner-looking answer.
- To add a screen: add a flow function in `capture.py`, register it in `build.py`'s `FLOWS`,
  add the figure + steps to `manual.md`.
