import flet as ft


def step() -> dict:
    content = ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[
            ft.Icon(ft.Icons.CHECK_CIRCLE, size=80, color=ft.Colors.GREEN),
            ft.Container(height=10),
            ft.Text(
                "You're all set!",
                size=28,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER,
                color=ft.Colors.ON_SURFACE,
            ),
            ft.Container(height=10),
            ft.Text(
                "Your AI companion is configured. You can change settings anytime.",
                size=14,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
        ],
    )

    return {
        "title": "All Done",
        "subtitle": "",
        "content": content,
        "next_label": "Start Chatting",
    }
