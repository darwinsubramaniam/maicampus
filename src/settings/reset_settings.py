import shutil

import flet as ft

from constants import APP_DIR


def create_reset_settings(page: ft.Page, on_reset: callable) -> ft.Container:
    confirm_field = ft.TextField(
        label='Type "confirm" to reset',
        width=300,
    )

    status_text = ft.Text("", color=ft.Colors.RED)

    async def do_reset(e):
        if confirm_field.value.strip().lower() != "confirm":
            status_text.value = 'Please type "confirm" to proceed.'
            status_text.color = ft.Colors.RED
            page.update()
            return

        # Clear all client storage
        from prefs import get_prefs
        await get_prefs().clear()

        # Delete all local data (ChromaDB + chat history)
        if APP_DIR.exists():
            shutil.rmtree(APP_DIR, ignore_errors=True)

        status_text.value = "App reset complete."
        status_text.color = ft.Colors.GREEN
        page.update()

        on_reset()

    return ft.Container(
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=40, color=ft.Colors.ERROR),
                ft.Container(height=10),
                ft.Text(
                    "This will permanently delete all your data:",
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.ERROR,
                ),
                ft.Container(height=8),
                ft.Column(
                    controls=[
                        ft.Text("  - Your profile (name, email, photo)", color=ft.Colors.ON_SURFACE),
                        ft.Text("  - AI provider settings and API keys", color=ft.Colors.ON_SURFACE),
                        ft.Text("  - All AI memories and conversation knowledge", color=ft.Colors.ON_SURFACE),
                        ft.Text("  - Appearance preferences", color=ft.Colors.ON_SURFACE),
                    ],
                    spacing=4,
                ),
                ft.Container(height=16),
                ft.Text(
                    'Type "confirm" below to reset the app.',
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Container(height=8),
                confirm_field,
                ft.Container(height=16),
                ft.FilledButton(
                    "Reset App",
                    icon=ft.Icons.DELETE_FOREVER,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.ERROR, color=ft.Colors.ON_ERROR),
                    on_click=do_reset,
                ),
                ft.Container(height=10),
                status_text,
            ],
        ),
        padding=20,
    )
