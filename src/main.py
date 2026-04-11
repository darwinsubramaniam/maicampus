import threading

import flet as ft

from ai_providers import ProviderConfig
from bootstrap import create_bootstrap_view, is_bootstrapped
from campus_calendar import create_calendar_view, get_calendar_context
from campus_calendar.event_store import CalendarEventStore
from chat import create_chat_view
from memory import MemoryManager
from notifications import NotificationCenter
from settings import create_settings_view
from theme import apply_theme

# Import to trigger tool registration
import tools.calendar_tools as _calendar_tools


def main(page: ft.Page):
    page.title = "MAI Campus"
    apply_theme(page)

    current_config: dict = {"config": None}
    memory_state: dict = {"mgr": None}
    calendar_store = CalendarEventStore()

    def get_config() -> ProviderConfig | None:
        return current_config["config"]

    def get_memory_manager() -> MemoryManager | None:
        return memory_state["mgr"]

    def get_cal_context() -> str:
        return get_calendar_context(calendar_store)

    def on_config_save(config: ProviderConfig):
        current_config["config"] = config
        mgr = MemoryManager(config)
        memory_state["mgr"] = mgr
        threading.Thread(target=mgr.initialize, daemon=True).start()

    def show_bootstrap():
        current_config["config"] = None
        memory_state["mgr"] = None
        page.navigation_bar = None
        page.controls.clear()
        bootstrap_view = create_bootstrap_view(page, on_bootstrap_complete)
        page.add(bootstrap_view)

    def show_main_app():
        _calendar_tools.set_memory_getter(get_memory_manager)

        notif_center = NotificationCenter(page)

        def _on_tool_executed(name, result):
            if name == "create_calendar_event" and result.get("success"):
                notif_center.add(
                    f"Added to calendar: {result.get('title', 'Event')}",
                    icon=ft.Icons.CALENDAR_MONTH,
                    color=ft.Colors.TEAL,
                )

        chat_view = create_chat_view(page, get_config, get_memory_manager, get_calendar_context=get_cal_context, notifications=notif_center)
        calendar_view = create_calendar_view(
            page, get_memory_manager,
            get_config=get_config,
            get_calendar_context_fn=get_cal_context,
            on_tool_executed=_on_tool_executed,
        )
        settings_view = create_settings_view(page, on_ai_save=on_config_save, on_reset=show_bootstrap)

        body = ft.Container(content=chat_view, expand=True)

        def switch_tab(e):
            index = e.control.selected_index
            if index == 0:
                body.content = chat_view
            elif index == 1:
                body.content = calendar_view
            else:
                body.content = settings_view
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

    def on_bootstrap_complete(config: ProviderConfig):
        on_config_save(config)
        page.navigation_bar = None
        page.controls.clear()
        show_main_app()

    # Check bootstrap using file-based flag (avoids SharedPreferences timing issues)
    from pathlib import Path
    _bootstrap_flag = Path.home() / ".maicampus" / ".bootstrapped"
    if _bootstrap_flag.exists():
        show_main_app()
    else:
        bootstrap_view = create_bootstrap_view(page, on_bootstrap_complete)
        page.add(bootstrap_view)


ft.run(main)
