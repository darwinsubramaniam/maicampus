import flet as ft


def create_appearance_settings(page: ft.Page) -> ft.Container:
    theme_modes = {
        "System": ft.ThemeMode.SYSTEM,
        "Light": ft.ThemeMode.LIGHT,
        "Dark": ft.ThemeMode.DARK,
    }

    # Determine current selection
    current = next(
        (name for name, mode in theme_modes.items() if mode == page.theme_mode),
        "System",
    )

    theme_dropdown = ft.Dropdown(
        label="Theme Mode",
        options=[ft.DropdownOption(key=name, text=name) for name in theme_modes],
        value=current,
        width=300,
    )

    def on_theme_select(e):
        page.theme_mode = theme_modes[theme_dropdown.value or "System"]
        page.update()

    theme_dropdown.on_select = on_theme_select

    return ft.Container(
        content=ft.Column(
            controls=[theme_dropdown],
        ),
        padding=20,
    )
