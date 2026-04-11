from datetime import datetime

import flet as ft


class NotificationCenter:
    """In-app notification center shown as a dropdown from the bell icon."""

    def __init__(self, page: ft.Page):
        self._page = page
        self._items: list[dict] = []  # {"message": str, "time": datetime, "icon": str, "color": str}
        self._badge_count = 0

        self._list = ft.ListView(spacing=4, padding=8, width=320, height=300)
        self._empty = ft.Container(
            content=ft.Text("No notifications", size=13, color=ft.Colors.ON_SURFACE_VARIANT, italic=True),
            alignment=ft.Alignment.CENTER,
            height=80,
        )

        self._badge = ft.Container(
            content=ft.Text("0", size=9, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
            width=16,
            height=16,
            border_radius=8,
            bgcolor=ft.Colors.ERROR,
            alignment=ft.Alignment.CENTER,
            visible=False,
            offset=ft.Offset(0.4, -0.4),
        )

        self._panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Text("Notifications", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                                ft.Container(expand=True),
                                ft.TextButton("Clear", on_click=self._clear_all),
                            ],
                        ),
                        padding=ft.Padding(left=12, right=4, top=8, bottom=4),
                    ),
                    ft.Divider(height=1),
                    self._list,
                ],
                tight=True,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border_radius=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=12,
                color=ft.Colors.with_opacity(0.15, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            visible=False,
            width=340,
        )

        self._bell = ft.Stack(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.NOTIFICATIONS_OUTLINED,
                    tooltip="Notifications",
                    on_click=self._toggle_panel,
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                self._badge,
            ],
            width=40,
            height=40,
        )

    @property
    def bell_button(self) -> ft.Stack:
        return self._bell

    @property
    def panel(self) -> ft.Container:
        return self._panel

    def add(self, message: str, icon: str = ft.Icons.INFO_OUTLINE, color: str = ft.Colors.TEAL):
        """Add a notification."""
        self._items.insert(0, {
            "message": message,
            "time": datetime.now(),
            "icon": icon,
            "color": color,
        })
        self._badge_count += 1
        self._badge.content.value = str(self._badge_count)
        self._badge.visible = True
        self._refresh_list()
        self._page.update()

    def _refresh_list(self):
        self._list.controls.clear()
        if not self._items:
            self._list.controls.append(self._empty)
            return
        for item in self._items:
            time_str = item["time"].strftime("%I:%M %p").lstrip("0")
            tile = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(item["icon"], size=18, color=item["color"]),
                        ft.Column(
                            controls=[
                                ft.Text(item["message"], size=12, color=ft.Colors.ON_SURFACE, max_lines=2),
                                ft.Text(time_str, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                padding=ft.Padding(left=10, right=10, top=8, bottom=8),
                border_radius=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            )
            self._list.controls.append(tile)

    def _toggle_panel(self, e):
        self._panel.visible = not self._panel.visible
        if self._panel.visible:
            self._badge_count = 0
            self._badge.visible = False
            self._refresh_list()
        self._page.update()

    def _clear_all(self, e):
        self._items.clear()
        self._badge_count = 0
        self._badge.visible = False
        self._refresh_list()
        self._page.update()
