import flet as ft

from ui import FONT_BODY, FONT_DISPLAY, register_fonts

_SEED = ft.Colors.TEAL


def _text_theme(on_surface: str, on_surface_variant: str) -> ft.TextTheme:
    """Display font for headings (tight tracking), body font for everything else.

    Colors are pinned per-mode so default-colored ``Text`` / ``TextField`` values
    always have proper contrast (Flutter's implicit default rendered too light).
    """
    def disp(size, weight, ls):
        return ft.TextStyle(
            font_family=FONT_DISPLAY, size=size, weight=weight, letter_spacing=ls, color=on_surface
        )

    def body(size, weight=None, h=1.45):
        return ft.TextStyle(font_family=FONT_BODY, size=size, weight=weight, height=h, color=on_surface)
    return ft.TextTheme(
        display_large=disp(52, ft.FontWeight.W_700, -1.5),
        display_medium=disp(40, ft.FontWeight.W_700, -1.0),
        display_small=disp(32, ft.FontWeight.W_700, -0.5),
        headline_large=disp(28, ft.FontWeight.W_700, -0.5),
        headline_medium=disp(24, ft.FontWeight.W_700, -0.3),
        headline_small=disp(20, ft.FontWeight.W_600, -0.2),
        title_large=disp(20, ft.FontWeight.W_600, -0.2),
        title_medium=ft.TextStyle(font_family=FONT_DISPLAY, size=16, weight=ft.FontWeight.W_600, color=on_surface),
        body_large=body(15),
        body_medium=body(14),
        body_small=ft.TextStyle(font_family=FONT_BODY, size=12, height=1.4, color=on_surface_variant),
        label_large=body(14, ft.FontWeight.W_500),
    )


LIGHT_THEME = ft.Theme(
    color_scheme_seed=_SEED,
    font_family=FONT_BODY,
    color_scheme=ft.ColorScheme(
        primary=ft.Colors.TEAL_700,
        on_primary=ft.Colors.WHITE,
        primary_container="#D0F1EC",
        on_primary_container="#0D3D35",
        secondary=ft.Colors.BLUE_GREY_600,
        on_secondary=ft.Colors.WHITE,
        surface="#FAFCFB",
        on_surface="#1A1C1B",
        surface_container_lowest="#FFFFFF",
        surface_container="#F1F5F4",
        surface_container_highest="#E8EDEC",
        on_surface_variant="#3F4947",
        outline_variant="#C5CFCC",
    ),
    text_theme=_text_theme("#1A1C1B", "#3F4947"),
)

DARK_THEME = ft.Theme(
    color_scheme_seed=_SEED,
    font_family=FONT_BODY,
    color_scheme=ft.ColorScheme(
        primary=ft.Colors.TEAL_200,
        on_primary="#003730",
        primary_container="#1A3B36",
        on_primary_container="#B2DFDB",
        secondary=ft.Colors.BLUE_GREY_300,
        on_secondary=ft.Colors.BLACK,
        surface="#0F1514",
        on_surface="#E0E3E1",
        surface_container_lowest="#0A0F0E",
        surface_container="#1A2120",
        surface_container_highest="#252D2C",
        on_surface_variant="#BFC9C6",
        outline_variant="#3A4442",
    ),
    text_theme=_text_theme("#E0E3E1", "#BFC9C6"),
)


def apply_theme(page: ft.Page):
    register_fonts(page)
    page.theme = LIGHT_THEME
    page.dark_theme = DARK_THEME
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.padding = 0
    page.spacing = 0
