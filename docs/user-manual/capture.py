"""Automated screenshot capture for the MAI Campus user manual.

Launches the Flet web app in *demo mode* (auto sign-in as the seed student — no Google
SSO), drives it with Playwright through a fixed-size browser, waits for the canvas to
settle, draws annotation overlays, and writes PNGs into ``images/``.

The app renders through Flutter web (a ``<canvas>``), so there are no HTML elements to
select: navigation is coordinate-driven and "is it done rendering yet?" is answered by
watching the screenshot stop changing (``wait_stable``).

Usage::

    uv run python docs/user-manual/capture.py baseline   # raw first-paint, for coord discovery
    uv run python docs/user-manual/capture.py chat        # annotated Chat-screen captures
"""

from __future__ import annotations

import io
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import Page, sync_playwright

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC = REPO / "src"
ENV_FILE = REPO / ".env"
IMAGES = HERE / "images"

PORT = 8561
API_BASE = "http://localhost:28000"
# Isolated, throwaway per-user store so captures are deterministic and the developer's real
# ~/.maicampus data is never touched. Wiped before every run.
CAPTURE_DATA = Path(tempfile.gettempdir()) / "maicampus-manual-capture"
CAPTURE_DB = CAPTURE_DATA / "surreal.db"

# Desktop-ish frame; deviceScaleFactor 2 => crisp 2x pixels for print.
VIEWPORT = {"width": 1280, "height": 832}
SCALE = 2

# Only these env vars are forwarded to the app. Google creds are deliberately withheld so
# google_oauth_configured() is False and the app auto-signs-in as the demo student.
_AI_KEYS = ("MAICAMPUS_AI_PROVIDER", "MAICAMPUS_AI_API_KEY", "MAICAMPUS_AI_MODEL")


# --------------------------------------------------------------------------- app process
def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def _app_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("MAICAMPUS_GOOGLE_")}
    parsed = _parse_env_file(ENV_FILE)
    for key in _AI_KEYS:
        if parsed.get(key):
            env[key] = parsed[key]
    env.pop("MAICAMPUS_GOOGLE_CLIENT_ID", None)
    env.pop("MAICAMPUS_GOOGLE_CLIENT_SECRET", None)
    # Route per-user data to the isolated capture store (embedded surrealkv, no auth) and talk
    # to the campus API for live timetable/booking data.
    env["MAICAMPUS_SURREAL_URL"] = f"surrealkv://{CAPTURE_DB}"
    env["MAICAMPUS_API_BASE"] = API_BASE
    return env


def reset_capture_data() -> None:
    if CAPTURE_DATA.exists():
        shutil.rmtree(CAPTURE_DATA, ignore_errors=True)
    CAPTURE_DATA.mkdir(parents=True, exist_ok=True)


def seed_demo_profile() -> None:
    """Give the demo user a realistic name/email so the Profile screen isn't empty."""
    env = _app_env()
    env["PYTHONPATH"] = str(SRC)
    try:
        subprocess.run(
            ["uv", "run", "python", str(HERE / "seed_demo_profile.py")],
            cwd=str(REPO), env=env, check=True, capture_output=True, timeout=90, text=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[seed] demo profile seed skipped ({exc})", flush=True)


def ensure_campus_api() -> bool:
    """Best-effort: bring up the campus backend so MAI can answer with real seeded data.

    Non-fatal — if Docker isn't available the app degrades gracefully and chat still works.
    """
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d", "surreal", "api"],
            cwd=str(REPO), check=True, capture_output=True, timeout=180,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[api] could not start campus backend ({exc}); continuing without it", flush=True)
        return False
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{API_BASE}/openapi.json", timeout=3) as resp:
                if resp.status == 200:
                    print("[api] campus backend ready", flush=True)
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(2)
    print("[api] campus backend not responding; continuing without it", flush=True)
    return False


def _free_port(port: int) -> None:
    """Kill anything still LISTENing on the port (e.g. a stale flet server from a prior run).

    `flet run` spawns a child web-server that outlives a plain terminate(); if it keeps the
    port, a new launch can't bind and Playwright would silently attach to the old process
    (with the wrong, non-isolated data). This guarantees we always talk to our own server.
    """
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:  # noqa: BLE001
        return
    pids = [p for p in out.stdout.split() if p.strip()]
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except (ProcessLookupError, ValueError):
            pass
    if pids:
        time.sleep(1)


def _wait_http(url: str, timeout: float = 120) -> None:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - polling, any error means "not yet"
            last = exc
        time.sleep(1)
    raise RuntimeError(f"app never became ready at {url}: {last}")


@contextmanager
def running_app(
    port: int = PORT,
    *,
    fresh: bool = True,
    with_api: bool = True,
    seed: bool = True,
    env_extra: dict[str, str] | None = None,
):
    url = f"http://127.0.0.1:{port}"
    if fresh:
        reset_capture_data()
        if seed:
            seed_demo_profile()
    if with_api:
        ensure_campus_api()
    _free_port(port)  # clear any stale server before we bind
    env = _app_env()
    if env_extra:
        env.update(env_extra)
    print(f"[app] launching flet web on {url} (demo mode, isolated store)…", flush=True)
    proc = subprocess.Popen(
        ["uv", "run", "flet", "run", "--web", "--port", str(port), str(SRC)],
        cwd=str(REPO),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # own process group so we can reap the whole tree
    )
    try:
        _wait_http(url)
        print("[app] HTTP ready; letting Flutter first-paint settle…", flush=True)
        time.sleep(3)
        yield url
    finally:
        print("[app] shutting down…", flush=True)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        _free_port(port)  # ensure the child web-server is gone too


# --------------------------------------------------------------------------- browser utils
def _png_bytes(page: Page) -> bytes:
    return page.screenshot(type="png")


def wait_stable(
    page: Page, *, settle: float = 1.2, every: float = 0.4, timeout: float = 30, tol: float = 0.004
) -> None:
    """Block until the screenshot stops changing meaningfully.

    The Flutter text caret blinks forever, so exact equality never holds. Instead we treat
    the frame as stable when the changed bounding-box covers less than ``tol`` of the image
    (caret-sized) for ``settle`` seconds — large changes (streaming text) reset the timer.
    """
    deadline = time.time() + timeout
    prev: Image.Image | None = None
    stable_since: float | None = None
    while time.time() < deadline:
        cur = Image.open(io.BytesIO(_png_bytes(page))).convert("RGB")
        if prev is not None:
            bbox = ImageChops.difference(prev, cur).getbbox()
            if bbox is None:
                changed = 0.0
            else:
                changed = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / (cur.width * cur.height)
            if changed < tol:
                stable_since = stable_since or time.time()
                if time.time() - stable_since >= settle:
                    return
            else:
                stable_since = None
        prev = cur
        time.sleep(every)
    print("[warn] wait_stable timed out — capturing current frame", flush=True)


def open_app(pw, url: str):
    browser = pw.chromium.launch(
        headless=True,
        args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swangle"],
    )
    ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=SCALE)
    page = ctx.new_page()
    page.goto(url, wait_until="load")
    wait_stable(page, timeout=40)
    return browser, page


# annotation overlay -------------------------------------------------------------------
def annotate(
    page: Page,
    markers: list[dict],
    *,
    title: str | None = None,
    legend: bool = False,
    legend_pos: str = "cr",
) -> None:
    """Draw numbered callouts over the canvas.

    Each marker: {"n": 1, "x": 0.5, "y": 0.9, "label": "..."} where x/y are 0..1 of viewport.
    Markers always render as numbered teal dots. When ``legend`` is True an in-image legend
    box lists the labels (use only where there is empty space — ``legend_pos`` is "cr"
    center-right or "br" bottom-right above the nav bar). Otherwise the explanations live in
    the manual text beside the figure, which keeps busy screens uncluttered.
    """
    page.evaluate(
        """([markers, title, legend, pos]) => {
          const old = document.getElementById('mm-overlay'); if (old) old.remove();
          const o = document.createElement('div'); o.id = 'mm-overlay';
          Object.assign(o.style, {position:'fixed',inset:'0',zIndex:'2147483647',pointerEvents:'none',
            fontFamily:'-apple-system,Segoe UI,Roboto,sans-serif'});
          for (const m of markers) {
            const d = document.createElement('div');
            Object.assign(d.style, {position:'absolute',left:(m.x*100)+'%',top:(m.y*100)+'%',
              transform:'translate(-50%,-50%)',width:'25px',height:'25px',borderRadius:'50%',
              background:'#00897B',color:'#fff',display:'flex',alignItems:'center',
              justifyContent:'center',fontWeight:'700',fontSize:'14px',
              boxShadow:'0 0 0 3px #fff, 0 2px 6px rgba(0,0,0,.4)'});
            d.textContent = m.n; o.appendChild(d);
          }
          if (legend && markers.some(m => m.label)) {
            const lg = document.createElement('div');
            const place = pos === 'br'
              ? {right:'16px', bottom:'72px'}
              : pos === 'tr'
              ? {right:'16px', top:'13%'}
              : {right:'16px', top:'50%', transform:'translateY(-50%)'};
            Object.assign(lg.style, {position:'absolute',maxWidth:'42%',
              background:'rgba(255,255,255,.97)',border:'1px solid #cfd8dc',borderRadius:'10px',
              padding:'12px 14px',boxShadow:'0 4px 14px rgba(0,0,0,.18)',fontSize:'14px',color:'#263238'},
              place);
            if (title) { const h=document.createElement('div'); h.textContent=title;
              Object.assign(h.style,{fontWeight:'700',marginBottom:'6px',color:'#00695C'}); lg.appendChild(h); }
            for (const m of markers.filter(x=>x.label)) {
              const r=document.createElement('div');
              Object.assign(r.style,{display:'flex',gap:'8px',alignItems:'flex-start',margin:'4px 0'});
              const b=document.createElement('span'); b.textContent=m.n;
              Object.assign(b.style,{flex:'0 0 20px',height:'20px',borderRadius:'50%',background:'#00897B',
                color:'#fff',fontWeight:'700',fontSize:'12px',display:'inline-flex',
                alignItems:'center',justifyContent:'center'});
              const t=document.createElement('span'); t.textContent=m.label;
              r.appendChild(b); r.appendChild(t); lg.appendChild(r);
            }
            o.appendChild(lg);
          }
          document.body.appendChild(o);
        }""",
        [markers, title, legend, legend_pos],
    )


def clear_overlay(page: Page) -> None:
    page.evaluate("() => { const o=document.getElementById('mm-overlay'); if(o) o.remove(); }")


def shoot(page: Page, name: str) -> Path:
    IMAGES.mkdir(parents=True, exist_ok=True)
    out = IMAGES / f"{name}.png"
    page.screenshot(path=str(out), type="png")
    print(f"[shot] {out.relative_to(REPO)}", flush=True)
    return out


def click_frac(page: Page, x: float, y: float) -> None:
    page.mouse.click(VIEWPORT["width"] * x, VIEWPORT["height"] * y)


# bottom NavigationBar tab x-fractions; settings NavigationRail item y-fractions
NAV = {"chat": 0.13, "calendar": 0.37, "booking": 0.61, "settings": 0.875}
NAV_Y = 0.955
RAIL = {"profile": 0.04, "appearance": 0.13, "knowledge": 0.20, "planner": 0.28, "logout": 0.35}
RAIL_X = 0.03


def goto_tab(page: Page, which: str, *, settle: float = 1.2, timeout: float = 25) -> None:
    click_frac(page, NAV[which], NAV_Y)
    wait_stable(page, settle=settle, timeout=timeout)


def open_section(page: Page, name: str, *, settle: float = 1.0, timeout: float = 15) -> None:
    click_frac(page, RAIL_X, RAIL[name])
    wait_stable(page, settle=settle, timeout=timeout)


# --------------------------------------------------------------------------- flows
def baseline() -> None:
    with running_app() as url, sync_playwright() as pw:
        browser, page = open_app(pw, url)
        try:
            shoot(page, "_baseline_initial")
        finally:
            browser.close()


def chat() -> None:
    # Coordinates (fractions of the viewport) read off the baseline capture.
    INPUT_X, INPUT_Y = 0.5, 0.86  # message field
    with running_app() as url, sync_playwright() as pw:
        browser, page = open_app(pw, url)
        try:
            # 1) genuine first-open / empty state (welcome panel + suggestion chips)
            shoot(page, "chat-01-welcome-raw")
            annotate(
                page,
                [
                    {"n": 1, "x": 0.045, "y": 0.02, "label": "Past chats (history sidebar)"},
                    {"n": 2, "x": 0.5, "y": 0.30, "label": "MAI introduces itself"},
                    {"n": 3, "x": 0.5, "y": 0.52, "label": "Tap a suggestion to get started"},
                    {"n": 4, "x": INPUT_X, "y": INPUT_Y, "label": "…or type your own question, then Enter"},
                    {"n": 5, "x": 0.37, "y": 0.955, "label": "Switch tabs (Chat · Calendar · Booking · Settings)"},
                ],
                title="The Chat screen",
                legend=True,
                legend_pos="tr",
            )
            shoot(page, "chat-01-welcome")
            clear_overlay(page)

            # 2) send a message and wait for the streamed reply (MAI reads the seeded timetable)
            click_frac(page, INPUT_X, INPUT_Y)
            page.keyboard.type("What does my class timetable look like this week?", delay=18)
            page.keyboard.press("Enter")
            time.sleep(1.5)
            wait_stable(page, settle=2.5, timeout=75)
            shoot(page, "chat-02-conversation-raw")
            annotate(
                page,
                [
                    {"n": 1, "x": 0.84, "y": 0.105, "label": "Your question appears on the right"},
                    {"n": 2, "x": 0.052, "y": 0.215, "label": "MAI answers — it can read your timetable"},
                ],
                title="Asking MAI a question",
            )
            shoot(page, "chat-02-conversation")
            clear_overlay(page)

            # 3) history sidebar (a titled session now exists from the message above)
            click_frac(page, 0.025, 0.033)  # open the menu
            wait_stable(page, settle=1.0, timeout=15)
            shoot(page, "chat-03-history-raw")
            annotate(
                page,
                [
                    {"n": 1, "x": 0.075, "y": 0.075, "label": "Start a fresh conversation"},
                    {"n": 2, "x": 0.10, "y": 0.16, "label": "Your past chats, tap one to reopen it"},
                ],
                title="Chat history",
            )
            shoot(page, "chat-03-history")
            clear_overlay(page)
        finally:
            browser.close()


def _send(page: Page, text: str, *, reply_timeout: float) -> None:
    click_frac(page, 0.5, 0.86)  # message field
    page.keyboard.type(text, delay=12)
    page.keyboard.press("Enter")
    time.sleep(1.5)
    wait_stable(page, settle=2.5, timeout=reply_timeout)


def ask_once(prompt: str, name: str, *, confirm: str | None = None, reply_timeout: float = 80) -> None:
    """Launch a fresh chat, send a plain-language prompt (and an optional 'yes' to a follow-up
    question), then capture MAI's reply. MAI confirms before write actions, so the ``confirm``
    turn is what makes the booking/reminder actually go through."""
    with running_app() as url, sync_playwright() as pw:
        browser, page = open_app(pw, url)
        try:
            _send(page, prompt, reply_timeout=reply_timeout)
            if confirm:
                _send(page, confirm, reply_timeout=reply_timeout)
            shoot(page, name)
        finally:
            browser.close()


def chat_examples() -> None:
    """A few example conversations showing MAI acting on plain-language requests."""
    reset_student_bookings()
    # MAI always confirms a calendar write first, so a clear "yes" on the follow-up completes it.
    ask_once(
        "Add a one-time reminder to play football this Friday from 6pm to 7pm", "chat-ex-reminder",
        confirm="Yes, that's all correct, please add it",
    )
    # "go ahead" makes MAI book in one turn (no confirmation round-trip).
    ask_once("Book Badminton Court 1 tomorrow from 5pm to 6pm, go ahead", "chat-ex-booking", reply_timeout=95)
    ask_once("When does the library close?", "chat-ex-library")


def sync_timetable(page: Page) -> None:
    """Settings -> Knowledge -> Sync from Knowledge Base, so the calendar has the seeded classes."""
    goto_tab(page, "settings")
    open_section(page, "knowledge")
    click_frac(page, 0.53, 0.39)  # Sync from Knowledge Base
    wait_stable(page, settle=2.0, timeout=45)
    time.sleep(2)


def login() -> None:
    # Dummy Google creds force the login screen to render (we never click through OAuth).
    extra = {
        "MAICAMPUS_GOOGLE_CLIENT_ID": "demo-client.apps.googleusercontent.com",
        "MAICAMPUS_GOOGLE_CLIENT_SECRET": "demo-secret",
    }
    with running_app(seed=False, with_api=False, env_extra=extra) as url, sync_playwright() as pw:
        browser, page = open_app(pw, url)
        try:
            shoot(page, "login-raw")
            annotate(
                page,
                [
                    {"n": 1, "x": 0.5, "y": 0.41, "label": "MAI Campus, your student companion"},
                    {"n": 2, "x": 0.5, "y": 0.63, "label": "Sign in with your UTM Google account"},
                ],
                title="Signing in",
                legend=True,
                legend_pos="br",
            )
            shoot(page, "login")
        finally:
            browser.close()


# Per-page annotation markers for the Settings sub-pages (single-action screens).
_SETTINGS_MARKERS = {
    "profile": [
        {"n": 1, "x": 0.5, "y": 0.19, "label": "Your name and photo from Google"},
        {"n": 2, "x": 0.62, "y": 0.535, "label": "Your linked matric number"},
    ],
    "appearance": [
        {"n": 1, "x": 0.42, "y": 0.105, "label": "Switch theme: System, Light or Dark"},
    ],
    "knowledge": [
        {"n": 1, "x": 0.53, "y": 0.345, "label": "Import your classes into the calendar"},
        {"n": 2, "x": 0.53, "y": 0.785, "label": "Check the campus services are reachable"},
    ],
    "planner": [
        {"n": 1, "x": 0.53, "y": 0.51, "label": "Run a planner scan now"},
    ],
    "logout": [
        {"n": 1, "x": 0.53, "y": 0.345, "label": "Sign out on this device"},
    ],
}
_SETTINGS_TITLES = {
    "profile": "Profile", "appearance": "Appearance", "knowledge": "Knowledge",
    "planner": "Planner", "logout": "Logout",
}


def settings() -> None:
    with running_app() as url, sync_playwright() as pw:
        browser, page = open_app(pw, url)
        try:
            goto_tab(page, "settings")
            order = ["profile", "appearance", "knowledge", "planner", "logout"]
            for name in order:
                if name != "profile":
                    open_section(page, name)
                shoot(page, f"settings-{name}-raw")
                annotate(
                    page, _SETTINGS_MARKERS[name], title=_SETTINGS_TITLES[name],
                    legend=True, legend_pos="cr",
                )
                shoot(page, f"settings-{name}")
                clear_overlay(page)
        finally:
            browser.close()


def calendar() -> None:
    with running_app() as url, sync_playwright() as pw:
        browser, page = open_app(pw, url)
        try:
            sync_timetable(page)
            goto_tab(page, "calendar")
            shoot(page, "calendar-01-month-raw")
            annotate(
                page,
                [
                    {"n": 1, "x": 0.13, "y": 0.10, "label": "Move between months; Today jumps back"},
                    {"n": 2, "x": 0.108, "y": 0.396, "label": "Tap any day to see what's on"},
                    {"n": 3, "x": 0.62, "y": 0.16, "label": "The day's classes and events"},
                    {"n": 4, "x": 0.975, "y": 0.03, "label": "Add your own event"},
                ],
                title="Your calendar",
                legend=True,
                legend_pos="br",
            )
            shoot(page, "calendar-01-month")
            clear_overlay(page)
            # add-event dialog, with a sample title filled in
            click_frac(page, 0.975, 0.03)
            wait_stable(page, settle=1.2, timeout=15)
            click_frac(page, 0.46, 0.142)  # Title field
            page.keyboard.type("Group project meeting", delay=18)
            wait_stable(page, settle=0.8, timeout=10)
            shoot(page, "calendar-02-add-raw")
            annotate(
                page,
                [
                    {"n": 1, "x": 0.535, "y": 0.142, "label": "Name your event"},
                    {"n": 2, "x": 0.48, "y": 0.316, "label": "Choose the date"},
                    {"n": 3, "x": 0.45, "y": 0.396, "label": "Set the start and end time"},
                    {"n": 4, "x": 0.365, "y": 0.484, "label": "Tick to repeat it every week"},
                    {"n": 5, "x": 0.625, "y": 0.923, "label": "Save it to your calendar"},
                ],
                title="Adding an event",
                legend=True,
                legend_pos="cr",
            )
            shoot(page, "calendar-02-add")
            clear_overlay(page)
        finally:
            browser.close()


def reset_student_bookings(student_id: str = "MEC255043") -> None:
    """Clear the student's existing facility bookings so the flow is reproducible.

    The campus API's booking data lives in the Docker volume and isn't reset between runs;
    without this, old bookings accumulate and the free-slot suggestions drift.
    """
    import json

    try:
        with urllib.request.urlopen(f"{API_BASE}/facility/bookings?student_id={student_id}", timeout=5) as r:
            bookings = json.load(r)
    except Exception as exc:  # noqa: BLE001
        print(f"[booking] could not list bookings ({exc})", flush=True)
        return
    cleared = 0
    for b in bookings:
        bid = b.get("booking_id") or b.get("id")
        try:
            urllib.request.urlopen(
                urllib.request.Request(f"{API_BASE}/facility/bookings/{bid}", method="DELETE"), timeout=5
            )
            cleared += 1
        except Exception:  # noqa: BLE001
            pass
    if cleared:
        print(f"[booking] cleared {cleared} existing booking(s)", flush=True)


def booking() -> None:
    """Flow 6: search a facility, hit a calendar conflict, then book a free slot."""
    reset_student_bookings()
    with running_app() as url, sync_playwright() as pw:
        browser, page = open_app(pw, url)
        try:
            sync_timetable(page)  # gives the calendar the Wed class for conflict detection
            goto_tab(page, "booking")
            click_frac(page, 0.16, 0.46)  # select Study Pod N28-1
            wait_stable(page, settle=1.0, timeout=15)
            click_frac(page, 0.373, 0.327)  # Check availability
            wait_stable(page, settle=1.5, timeout=20)
            shoot(page, "booking-01-search-raw")
            annotate(
                page,
                [
                    {"n": 1, "x": 0.16, "y": 0.30, "label": "Browse facilities and pick one"},
                    {"n": 2, "x": 0.51, "y": 0.266, "label": "Set the date and time you want"},
                    {"n": 3, "x": 0.373, "y": 0.327, "label": "See which hours are free"},
                    {"n": 4, "x": 0.45, "y": 0.454, "label": "Tap a free slot to fill it in"},
                ],
                title="Booking a facility",
            )
            shoot(page, "booking-01-search")
            clear_overlay(page)

            # try to book 14:00-16:00, which overlaps the Wed MECS0022 class -> red conflict
            click_frac(page, 0.507, 0.327)  # Book facility
            wait_stable(page, settle=1.5, timeout=25)
            shoot(page, "booking-02-conflict-raw")
            annotate(
                page,
                [
                    {"n": 1, "x": 0.55, "y": 0.50, "label": "MAI caught a clash with your class"},
                    {"n": 2, "x": 0.40, "y": 0.44, "label": "Free slots to choose instead"},
                ],
                title="Clash detected",
            )
            shoot(page, "booking-02-conflict")
            clear_overlay(page)

            # take a suggested free slot (the app fills the time fields), then book successfully
            click_frac(page, 0.40, 0.44)  # "08:00-09:00" chip
            wait_stable(page, settle=0.8, timeout=10)
            click_frac(page, 0.507, 0.327)  # Book facility
            wait_stable(page, settle=1.5, timeout=25)
            click_frac(page, 0.95, 0.605)  # refresh My Bookings (it sits below the success note now)
            wait_stable(page, settle=1.2, timeout=20)
            shoot(page, "booking-03-confirmed-raw")
            annotate(
                page,
                [
                    {"n": 1, "x": 0.55, "y": 0.50, "label": "Booked, and added to your calendar"},
                    {"n": 2, "x": 0.55, "y": 0.66, "label": "Manage it later: reschedule or cancel"},
                ],
                title="Booked",
            )
            shoot(page, "booking-03-confirmed")
            clear_overlay(page)

            # the booking is mirrored onto the calendar (today, 08:00-09:00)
            goto_tab(page, "calendar")
            shoot(page, "calendar-03-booking-linked-raw")
            annotate(
                page,
                [
                    {"n": 1, "x": 0.58, "y": 0.185, "label": "Your booking shows on the calendar too"},
                    {"n": 2, "x": 0.965, "y": 0.185, "label": "Manage in Booking (it can't be edited here)"},
                    {"n": 3, "x": 0.95, "y": 0.278, "label": "Normal events have edit and delete"},
                ],
                title="Bookings on your calendar",
                legend=True,
                legend_pos="br",
            )
            shoot(page, "calendar-03-booking-linked")
            clear_overlay(page)
        finally:
            browser.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "login"
    {
        "baseline": baseline,
        "login": login,
        "chat": chat,
        "chat_examples": chat_examples,
        "calendar": calendar,
        "booking": booking,
        "settings": settings,
    }[cmd]()
