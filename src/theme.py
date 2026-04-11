import flet as ft

_SEED = ft.Colors.TEAL

LIGHT_THEME = ft.Theme(
    color_scheme_seed=_SEED,
    color_scheme=ft.ColorScheme(
        primary=ft.Colors.TEAL_700,
        on_primary=ft.Colors.WHITE,
        primary_container="#D0F1EC",
        on_primary_container="#0D3D35",
        secondary=ft.Colors.BLUE_GREY_600,
        on_secondary=ft.Colors.WHITE,
        surface="#FAFCFB",
        on_surface="#1A1C1B",
        surface_container="#F1F5F4",
        surface_container_highest="#E8EDEC",
        on_surface_variant="#3F4947",
    ),
    text_theme=ft.TextTheme(
        body_medium=ft.TextStyle(size=14),
    ),
)

DARK_THEME = ft.Theme(
    color_scheme_seed=_SEED,
    color_scheme=ft.ColorScheme(
        primary=ft.Colors.TEAL_200,
        on_primary="#003730",
        primary_container="#1A3B36",
        on_primary_container="#B2DFDB",
        secondary=ft.Colors.BLUE_GREY_300,
        on_secondary=ft.Colors.BLACK,
        surface="#0F1514",
        on_surface="#E0E3E1",
        surface_container="#1A2120",
        surface_container_highest="#252D2C",
        on_surface_variant="#BFC9C6",
    ),
    text_theme=ft.TextTheme(
        body_medium=ft.TextStyle(size=14),
    ),
)


def apply_theme(page: ft.Page):
    page.theme = LIGHT_THEME
    page.dark_theme = DARK_THEME
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.padding = 0
