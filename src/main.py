from __future__ import annotations

import flet as ft

from ai_providers import server_config_from_env
from auth import (
    allowed_domains_label,
    build_google_provider,
    email_allowed,
    google_oauth_configured,
    resolve_user_context,
)
from campus_calendar import create_calendar_view, get_calendar_context
from campus_calendar.event_store import CalendarEventStore
from chat import create_chat_view
from chat.session_store import SessionStore
from constants import DEFAULT_STUDENT_ID
from facility_booking import create_facility_view
from memory import MemoryManager
from notifications import NotificationCenter
from observability import get_logger
from planner import SmartPlannerTask
from services import UserContext
from settings import create_settings_view
from theme import apply_theme
from tools import calendar_tools as _calendar_tools  # noqa: F401  # side-effect: registers tools
from tools import facility_tools as _facility_tools  # noqa: F401  # side-effect: registers tools
from tools import planner_tools as _planner_tools  # noqa: F401  # side-effect: registers tools
from tools import ukb_tools as _ukb_tools  # noqa: F401  # side-effect: registers tools

# Local-dev identity used only when Google SSO is not configured, so `uv run flet run` works
# offline. Production sets MAICAMPUS_GOOGLE_CLIENT_ID/SECRET and every user logs in for real.
_DEV_USER_ID = "dev-local"

log = get_logger("app")


def main(page: ft.Page):
    page.title = "MAI Campus"
    apply_theme(page)

    # One shared, server-funded AI config (DeepSeek by default). Never per-user.
    server_config = server_config_from_env()

    # Per-connection (per-user) state. main() runs once per connected client.
    auth: dict = {"ctx": None, "name": "You", "pic": ""}
    planner_state: dict = {"task": None}

    def get_config():
        return server_config

    def get_user_context() -> UserContext | None:
        return auth["ctx"]

    def get_memory_manager() -> MemoryManager | None:
        ctx = auth["ctx"]
        return MemoryManager(ctx.user_id) if ctx else None

    def get_calendar_store() -> CalendarEventStore:
        return CalendarEventStore(auth["ctx"].user_id)

    def get_session_store() -> SessionStore:
        return SessionStore(auth["ctx"].user_id)

    def get_cal_context() -> str:
        ctx = auth["ctx"]
        return get_calendar_context(CalendarEventStore(ctx.user_id)) if ctx else ""

    # --- Login screen -------------------------------------------------------
    def show_login():
        page.navigation_bar = None
        page.controls.clear()

        async def _do_login(e):
            await page.login(build_google_provider())

        login_card = ft.Container(
            alignment=ft.Alignment.CENTER,
            expand=True,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
                spacing=0,
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=40, color=ft.Colors.PRIMARY),
                        width=84,
                        height=84,
                        border_radius=28,
                        alignment=ft.Alignment.CENTER,
                        bgcolor=ft.Colors.PRIMARY_CONTAINER,
                    ),
                    ft.Container(height=20),
                    ft.Text("MAI Campus", size=30, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    ft.Text(
                        "Your AI student companion. Sign in with your UTM account to continue.",
                        size=14,
                        text_align=ft.TextAlign.CENTER,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Container(height=28),
                    ft.FilledButton(
                        content=ft.Row(
                            [
                                ft.Image(src="google_g.svg", width=20, height=20),
                                ft.Text(
                                    "Sign in with UTM Student Google Account",
                                    weight=ft.FontWeight.W_600,
                                ),
                            ],
                            tight=True,
                            spacing=12,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        on_click=_do_login,
                        # Google-style button: white surface, subtle border, brand logo.
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.WHITE,
                            color="#3C4043",
                            padding=ft.Padding(22, 18, 24, 18),
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
                        ),
                    ),
                ],
            ),
        )
        page.add(login_card)

    def on_login(e):
        log.info("on_login fired (error=%r)", getattr(e, "error", None))
        if getattr(e, "error", None):
            log.warning("OAuth flow returned an error → back to login: %s", e.error)
            show_login()
            return
        user = getattr(page.auth, "user", None)
        if user is None:
            log.warning("on_login: page.auth.user is None (no identity) → back to login")
            show_login()
            return
        email = str(user.get("email") or "")
        log.info("OAuth user authenticated: email=%r name=%r", email, str(user.get("name") or ""))
        # Server-side gate: only allow UTM accounts (Google's `hd` hint is not a security control).
        if not email_allowed(email):
            log.warning("Access denied for %r (allowed: %s)", email, allowed_domains_label())
            page.logout()
            show_access_denied(email)
            return
        try:
            auth["ctx"] = resolve_user_context(user)
            auth["name"] = str(user.get("name") or "You")
            auth["pic"] = str(user.get("picture") or "")
            log.info(
                "Session established: user_id=%s student_id=%s",
                auth["ctx"].user_id,
                auth["ctx"].student_id,
            )
            show_main_app()
            log.info("Main app rendered for %r", email)
        except Exception:
            # Don't strand the user on a blank screen — log the full trace and return to login.
            log.exception("Failed to establish session after login for %r", email)
            show_login()

    def show_access_denied(email: str):
        page.navigation_bar = None
        page.controls.clear()

        def _retry(e):
            show_login()

        page.add(
            ft.Container(
                alignment=ft.Alignment.CENTER,
                expand=True,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.BLOCK, size=48, color=ft.Colors.ERROR),
                        ft.Container(height=16),
                        ft.Text("UTM account required", size=24, weight=ft.FontWeight.W_700,
                                color=ft.Colors.ON_SURFACE),
                        ft.Container(height=8),
                        ft.Text(
                            f"{email or 'That account'} isn't a UTM account. "
                            f"Please sign in with your university account ({allowed_domains_label()}).",
                            size=14, text_align=ft.TextAlign.CENTER, color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Container(height=24),
                        ft.FilledButton("Try another account", icon=ft.Icons.SWITCH_ACCOUNT, on_click=_retry),
                    ],
                ),
            )
        )

    def do_sign_out():
        if planner_state["task"]:
            planner_state["task"].stop()
            planner_state["task"] = None
        auth["ctx"] = None
        page.logout()
        show_login()

    # --- Main application ---------------------------------------------------
    def show_main_app():
        notif_center = NotificationCenter(page)

        def _on_tool_executed(name, result):
            if name == "create_calendar_event" and result.get("success"):
                notif_center.add(
                    f"Added to calendar: {result.get('title', 'Event')}",
                    icon=ft.Icons.CALENDAR_MONTH,
                    color=ft.Colors.TEAL,
                )
            elif name == "book_facility" and result.get("booked"):
                notif_center.add(
                    f"Booked {result.get('facility', 'facility')} · {result.get('date', '')} {result.get('time', '')}",
                    icon=ft.Icons.EVENT_AVAILABLE,
                    color=ft.Colors.TEAL,
                )
            elif name == "cancel_booking" and result.get("cancelled"):
                notif_center.add(
                    f"Cancelled booking #{result.get('booking_id')}",
                    icon=ft.Icons.EVENT_BUSY,
                    color=ft.Colors.ORANGE,
                )
            elif name == "reschedule_booking" and result.get("rescheduled"):
                notif_center.add(
                    f"Rescheduled {result.get('facility', 'booking')} · {result.get('date', '')} {result.get('time', '')}",
                    icon=ft.Icons.EVENT_REPEAT,
                    color=ft.Colors.TEAL,
                )

            # A booking created/changed from the Book button or the floating chat changes
            # "My Bookings" — re-query the Booking panel so it doesn't keep showing the
            # stale (often empty) list it loaded before the booking existed.
            if name in ("book_facility", "cancel_booking", "reschedule_booking"):
                refresh = getattr(facility_view, "refresh", None)
                if refresh:
                    refresh()

        # Calendar → Booking deep link: a booking's calendar mirror can't be edited in place, so
        # its "Manage in Booking" action jumps to the Booking tab focused on that booking.
        def navigate_to_booking(booking_id=None, facility_id=None):
            if page.navigation_bar:
                page.navigation_bar.selected_index = 2
            body.content = facility_view
            focus = getattr(facility_view, "focus_booking", None)
            if focus:
                focus(booking_id)
            page.update()

        chat_view = create_chat_view(
            page,
            get_config,
            get_memory_manager,
            get_session_store,
            get_calendar_context=get_cal_context,
            get_user_context=get_user_context,
            notifications=notif_center,
            user_name=auth["name"],
            user_pic=auth["pic"],
        )
        calendar_view = create_calendar_view(
            page,
            get_memory_manager,
            get_calendar_store,
            get_config=get_config,
            get_calendar_context_fn=get_cal_context,
            on_tool_executed=_on_tool_executed,
            get_session_store=get_session_store,
            get_user_context=get_user_context,
            on_navigate_to_booking=navigate_to_booking,
            user_name=auth["name"],
            user_pic=auth["pic"],
        )
        facility_view = create_facility_view(
            page,
            get_memory_manager,
            get_config=get_config,
            get_calendar_context_fn=get_cal_context,
            on_tool_executed=_on_tool_executed,
            get_session_store=get_session_store,
            get_user_context=get_user_context,
            user_name=auth["name"],
            user_pic=auth["pic"],
        )
        # Create planner early so we can pass scan to settings
        planner = SmartPlannerTask(
            store=get_calendar_store(),
            get_memory_manager=get_memory_manager,
            notification_center=notif_center,
            page=page,
            open_chat_fn=lambda *a, **kw: None,  # wired after chat_view exists
        )

        settings_view = create_settings_view(
            page, on_logout=do_sign_out, on_scan=planner._scan, get_user_context=get_user_context
        )

        body = ft.Container(content=chat_view, expand=True)

        def _refresh_view(view):
            # Re-query on show so each tab reflects changes made in another (e.g. a booking
            # cancelled in the Booking tab is gone from the Calendar; chat bookings show up).
            refresh = getattr(view, "refresh", None)
            if refresh:
                refresh()

        def switch_tab(e):
            index = e.control.selected_index
            if index == 0:
                body.content = chat_view
            elif index == 1:
                body.content = calendar_view
                _refresh_view(calendar_view)
            elif index == 2:
                body.content = facility_view
                _refresh_view(facility_view)
            else:
                body.content = settings_view
            page.update()

        # Chat deep-link from planner notifications
        def open_chat_with_prompt(
            mai_message: str,
            title: str = "Task",
            event_id: str | None = None,
            due_date: str | None = None,
        ):
            """Open chat with a progress check-in initiated by MAI."""
            if page.navigation_bar:
                page.navigation_bar.selected_index = 0
            body.content = chat_view
            chat_view.start_checkin(title, mai_message, event_id=event_id, due_date=due_date)  # type: ignore[attr-defined]
            page.update()

        page.navigation_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(
                    icon=ft.Icons.CHAT_BUBBLE_OUTLINE,
                    selected_icon=ft.Icons.CHAT_BUBBLE,
                    label="Chat",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.CALENDAR_MONTH_OUTLINED,
                    selected_icon=ft.Icons.CALENDAR_MONTH,
                    label="Calendar",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.MEETING_ROOM_OUTLINED,
                    selected_icon=ft.Icons.MEETING_ROOM,
                    label="Booking",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label="Settings",
                ),
            ],
            on_change=switch_tab,
            indicator_color=ft.Colors.PRIMARY_CONTAINER,
            # Pin a compact height + always-show labels so the bar fits the web viewport
            # (the default M3 height overflows slightly and clips the labels).
            height=68,
            label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        )

        page.controls.clear()
        page.add(body)

        # Wire planner chat callback and start
        planner._open_chat_fn = open_chat_with_prompt
        planner.start()
        planner_state["task"] = planner

        # Check for app updates
        import webbrowser

        from updater import check_for_update

        def _on_update(version, download_url, notes, update_type):
            def _open_download(e):
                webbrowser.open(download_url)

            if update_type == "major":
                notif_center.add(
                    f"Major update {version} available. This may include breaking changes"
                    " — please review release notes before updating.",
                    icon=ft.Icons.WARNING_AMBER,
                    color=ft.Colors.ORANGE,
                    on_click=_open_download,
                )
            elif update_type == "minor":
                notif_center.add(
                    f"Update {version} available with new features. Tap to download.",
                    icon=ft.Icons.SYSTEM_UPDATE,
                    color=ft.Colors.TEAL,
                    on_click=_open_download,
                )
            else:
                notif_center.add(
                    f"Patch {version} available. Tap to download.",
                    icon=ft.Icons.SYSTEM_UPDATE,
                    color=ft.Colors.TEAL,
                    on_click=_open_download,
                )

        check_for_update(_on_update)

    # --- Entry: gate the whole app behind authentication --------------------
    if google_oauth_configured():
        log.info("New session: Google SSO active (allowed domains: %s)", allowed_domains_label())
        page.on_login = on_login
        show_login()
    else:
        # No Google SSO configured (local dev) — auto-sign-in as the demo student.
        log.warning("New session: Google SSO NOT configured — auto-login as dev user")
        auth["ctx"] = UserContext(user_id=_DEV_USER_ID, student_id=DEFAULT_STUDENT_ID)
        show_main_app()


ft.run(main)
