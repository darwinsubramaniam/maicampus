from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import flet as ft

import services

if TYPE_CHECKING:
    from ai_providers import ProviderConfig
from bootstrap import create_bootstrap_view
from campus_calendar import create_calendar_view, get_calendar_context
from chat import create_chat_view
from constants import BOOTSTRAP_FLAG
from facility_booking import create_facility_view
from memory import MemoryManager
from notifications import NotificationCenter
from planner import SmartPlannerTask
from settings import create_settings_view
from theme import apply_theme
from tools import calendar_tools as _calendar_tools  # noqa: F401  # side-effect: registers tools
from tools import facility_tools as _facility_tools  # noqa: F401  # side-effect: registers tools
from tools import planner_tools as _planner_tools  # noqa: F401  # side-effect: registers tools
from tools import ukb_tools as _ukb_tools  # noqa: F401  # side-effect: registers tools


def main(page: ft.Page):
    page.title = "MAI Campus"
    apply_theme(page)

    current_config: dict = {"config": None}
    memory_state: dict = {"mgr": None}
    planner_state: dict = {"task": None}

    def get_config() -> ProviderConfig | None:
        return current_config["config"]

    def get_memory_manager() -> MemoryManager | None:
        return memory_state["mgr"]

    def get_cal_context() -> str:
        return get_calendar_context(services.calendar_store)

    def on_config_save(config: ProviderConfig):
        current_config["config"] = config
        mgr = MemoryManager(config)
        memory_state["mgr"] = mgr
        services.set_memory_getter(get_memory_manager)
        threading.Thread(target=mgr.initialize, daemon=True).start()

    def show_bootstrap():
        current_config["config"] = None
        memory_state["mgr"] = None
        if planner_state["task"]:
            planner_state["task"].stop()
            planner_state["task"] = None
        services.reset()
        page.navigation_bar = None
        page.controls.clear()
        bootstrap_view = create_bootstrap_view(page, on_bootstrap_complete)
        page.add(bootstrap_view)

    def show_main_app():
        services.set_memory_getter(get_memory_manager)

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

        chat_view = create_chat_view(
            page,
            get_config,
            get_memory_manager,
            get_calendar_context=get_cal_context,
            notifications=notif_center,
        )
        calendar_view = create_calendar_view(
            page,
            get_memory_manager,
            get_config=get_config,
            get_calendar_context_fn=get_cal_context,
            on_tool_executed=_on_tool_executed,
        )
        facility_view = create_facility_view(
            page,
            get_memory_manager,
            get_config=get_config,
            get_calendar_context_fn=get_cal_context,
            on_tool_executed=_on_tool_executed,
        )
        # Create planner early so we can pass scan to settings
        planner = SmartPlannerTask(
            store=services.calendar_store,
            get_memory_manager=get_memory_manager,
            notification_center=notif_center,
            page=page,
            open_chat_fn=lambda *a, **kw: None,  # wired after chat_view exists
        )

        settings_view = create_settings_view(
            page, on_ai_save=on_config_save, on_reset=show_bootstrap, on_scan=planner._scan
        )

        body = ft.Container(content=chat_view, expand=True)

        def switch_tab(e):
            index = e.control.selected_index
            if index == 0:
                body.content = chat_view
            elif index == 1:
                body.content = calendar_view
            elif index == 2:
                body.content = facility_view
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

    def on_bootstrap_complete(config: ProviderConfig):
        on_config_save(config)
        page.navigation_bar = None
        page.controls.clear()
        show_main_app()

    if BOOTSTRAP_FLAG.exists():
        show_main_app()
    else:
        bootstrap_view = create_bootstrap_view(page, on_bootstrap_complete)
        page.add(bootstrap_view)


ft.run(main)
