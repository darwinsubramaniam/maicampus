from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from collections.abc import Callable

from settings.ai_settings import create_ai_settings
from settings.appearance_settings import create_appearance_settings
from settings.knowledge_settings import create_knowledge_settings
from settings.planner_settings import create_planner_settings
from settings.profile_settings import create_profile_settings
from settings.reset_settings import create_reset_settings
from ui import FONT_DISPLAY, section_card


def create_settings_view(
    page: ft.Page, on_ai_save: Callable, on_reset: Callable, on_scan: Callable | None = None
) -> ft.Row:
    profile_section = create_profile_settings(page)
    appearance_section = create_appearance_settings(page)
    ai_section = create_ai_settings(page, on_ai_save)
    knowledge_section = create_knowledge_settings(page)
    planner_section = create_planner_settings(page, on_scan=on_scan)
    reset_section = create_reset_settings(page, on_reset)

    sections = [
        {
            "label": "Profile",
            "icon": ft.Icons.PERSON_OUTLINED,
            "selected_icon": ft.Icons.PERSON,
            "content": profile_section,
        },
        {
            "label": "Appearance",
            "icon": ft.Icons.PALETTE_OUTLINED,
            "selected_icon": ft.Icons.PALETTE,
            "content": appearance_section,
        },
        {
            "label": "AI Provider",
            "icon": ft.Icons.SMART_TOY_OUTLINED,
            "selected_icon": ft.Icons.SMART_TOY,
            "content": ai_section,
        },
        {
            "label": "Knowledge",
            "icon": ft.Icons.SCHOOL_OUTLINED,
            "selected_icon": ft.Icons.SCHOOL,
            "content": knowledge_section,
        },
        {
            "label": "Planner",
            "icon": ft.Icons.AUTO_AWESOME_OUTLINED,
            "selected_icon": ft.Icons.AUTO_AWESOME,
            "content": planner_section,
        },
        {
            "label": "Reset",
            "icon": ft.Icons.DELETE_OUTLINE,
            "selected_icon": ft.Icons.DELETE_FOREVER,
            "content": reset_section,
        },
    ]

    content_area = ft.Container(
        content=sections[0]["content"],
        padding=0,
    )

    section_title = ft.Text(
        sections[0]["label"],
        size=24,
        weight=ft.FontWeight.W_700,
        font_family=FONT_DISPLAY,
        color=ft.Colors.ON_SURFACE,
    )

    content_panel = ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(
                content=ft.Column(
                    controls=[section_title, ft.Container(height=4), section_card(content_area, padding=8)],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                padding=ft.Padding(left=24, right=24, top=28, bottom=24),
                alignment=ft.Alignment.TOP_CENTER,
                expand=True,
            ),
        ],
    )

    def on_nav_change(e):
        idx = e.control.selected_index
        section = sections[idx]
        section_title.value = section["label"]
        content_area.content = section["content"]
        page.update()

    rail = ft.NavigationRail(
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icon(s["icon"], color=ft.Colors.ON_SURFACE_VARIANT),
                selected_icon=ft.Icon(s["selected_icon"], color=ft.Colors.TEAL),
                label=s["label"],
            )
            for s in sections
        ],
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        on_change=on_nav_change,
        indicator_color=ft.Colors.PRIMARY_CONTAINER,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        min_width=80,
        group_alignment=-1,
        selected_label_text_style=ft.TextStyle(size=11, color=ft.Colors.PRIMARY, weight=ft.FontWeight.W_600),
        unselected_label_text_style=ft.TextStyle(size=11, color=ft.Colors.ON_SURFACE_VARIANT),
    )

    return ft.Row(
        expand=True,
        spacing=0,
        controls=[
            rail,
            ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
            content_panel,
        ],
    )
