import flet as ft


def step() -> dict:
    content = ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[
            ft.Icon(ft.Icons.SCHOOL, size=80, color=ft.Colors.PRIMARY),
            ft.Container(height=10),
            ft.Text(
                "Welcome to MAI Campus",
                size=28,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER,
                color=ft.Colors.ON_SURFACE,
            ),
            ft.Container(height=10),
            ft.Text(
                "Your AI companion for campus life — classes, assignments,\n"
                "deadlines, facilities, clubs, and more.\n\n"
                "Let's get you set up in a few quick steps.",
                size=16,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
        ],
    )

    return {
        "title": "Welcome",
        "subtitle": "Get started with MAI Campus",
        "content": content,
        "next_label": "Get Started",
    }
