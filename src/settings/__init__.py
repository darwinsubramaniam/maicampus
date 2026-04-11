import flet as ft

from settings.ai_settings import create_ai_settings
from settings.appearance_settings import create_appearance_settings
from settings.profile_settings import create_profile_settings
from settings.reset_settings import create_reset_settings


def create_settings_view(page: ft.Page, on_ai_save: callable, on_reset: callable) -> ft.Row:
    profile_section = create_profile_settings(page)
    appearance_section = create_appearance_settings(page)
    ai_section = create_ai_settings(page, on_ai_save)
    reset_section = create_reset_settings(page, on_reset)

    sections = [
        {"label": "Profile", "icon": ft.Icons.PERSON_OUTLINED, "selected_icon": ft.Icons.PERSON, "content": profile_section},
        {"label": "Appearance", "icon": ft.Icons.PALETTE_OUTLINED, "selected_icon": ft.Icons.PALETTE, "content": appearance_section},
        {"label": "AI Provider", "icon": ft.Icons.SMART_TOY_OUTLINED, "selected_icon": ft.Icons.SMART_TOY, "content": ai_section},
        {"label": "Reset", "icon": ft.Icons.DELETE_OUTLINE, "selected_icon": ft.Icons.DELETE_FOREVER, "content": reset_section},
    ]

    content_area = ft.Container(
        content=sections[0]["content"],
        expand=True,
        padding=ft.Padding(left=24, right=24, top=16, bottom=16),
    )

    section_title = ft.Text(
        sections[0]["label"],
        size=22,
        weight=ft.FontWeight.W_600,
        color=ft.Colors.ON_SURFACE,
    )

    content_panel = ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(
                content=ft.Column(
                    controls=[section_title, content_area],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(left=24, right=24, top=20, bottom=16),
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
