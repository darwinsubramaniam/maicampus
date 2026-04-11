from typing import cast

import flet as ft


def _icon_avatar(icon: ft.IconData, bgcolor: str) -> ft.CircleAvatar:
    return ft.CircleAvatar(
        content=ft.Icon(icon, color=ft.Colors.WHITE, size=16),
        bgcolor=bgcolor,
        radius=16,
    )


def _user_avatar(pic_path: str | None = None) -> ft.CircleAvatar:
    if pic_path:
        return ft.CircleAvatar(foreground_image_src=pic_path, radius=16)
    return _icon_avatar(ft.Icons.PERSON, ft.Colors.TEAL_700)


def _ai_avatar() -> ft.CircleAvatar:
    return _icon_avatar(ft.Icons.SCHOOL, ft.Colors.TEAL)


class ChatMessage(ft.Row):
    def __init__(
        self,
        author: str,
        body: str,
        is_user: bool = False,
        is_error: bool = False,
        user_pic: str | None = None,
        is_loading: bool = False,
    ):
        text_color = (
            ft.Colors.ON_ERROR_CONTAINER
            if is_error
            else ft.Colors.ON_PRIMARY_CONTAINER
            if is_user
            else ft.Colors.ON_SURFACE
        )

        self.body_text = ft.Text(
            body,
            selectable=True,
            size=14,
            color=text_color,
        )

        self._loading_row = ft.Row(
            controls=[
                ft.ProgressRing(width=12, height=12, stroke_width=2, color=ft.Colors.TEAL),
                ft.Text(
                    "MAI is thinking...",
                    size=12,
                    italic=True,
                    color=ft.Colors.GREY_500,
                ),
            ],
            spacing=8,
            visible=is_loading,
        )

        author_color = (
            ft.Colors.ON_ERROR_CONTAINER
            if is_error
            else ft.Colors.ON_PRIMARY_CONTAINER
            if is_user
            else ft.Colors.TEAL_700
        )

        self._bubble = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Error" if is_error else author,
                        weight=ft.FontWeight.W_600,
                        size=11,
                        color=author_color,
                    ),
                    self._loading_row,
                    self.body_text,
                ],
                tight=True,
                spacing=4,
            ),
            bgcolor=(
                ft.Colors.ERROR_CONTAINER
                if is_error
                else ft.Colors.PRIMARY_CONTAINER
                if is_user
                else ft.Colors.SURFACE_CONTAINER_HIGHEST
            ),
            border_radius=ft.BorderRadius(
                top_left=16 if is_user else 4,
                top_right=4 if is_user else 16,
                bottom_left=16,
                bottom_right=16,
            ),
            padding=ft.Padding(left=14, right=14, top=10, bottom=10),
            expand=True,
        )

        if is_loading:
            self.body_text.visible = False

        if is_error:
            _avatar = _icon_avatar(ft.Icons.ERROR_OUTLINE, ft.Colors.ERROR)
        elif is_user:
            _avatar = _user_avatar(user_pic)
        else:
            _avatar = _ai_avatar()

        controls = [self._bubble, _avatar] if is_user else [_avatar, self._bubble]

        super().__init__(
            alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=controls,
            spacing=8,
        )

    def start_streaming(self):
        self._loading_row.visible = False
        self.body_text.visible = True
        self.body_text.value = ""

    def set_error(self, message: str):
        self._loading_row.visible = False
        self.body_text.visible = True
        self.body_text.value = message
        self.body_text.color = ft.Colors.ON_ERROR_CONTAINER
        self._bubble.bgcolor = ft.Colors.ERROR_CONTAINER
        cast("ft.Column", self._bubble.content).controls[0] = ft.Text(
            "Error",
            weight=ft.FontWeight.W_600,
            size=11,
            color=ft.Colors.ON_ERROR_CONTAINER,
        )
        self.controls[0] = _icon_avatar(ft.Icons.ERROR_OUTLINE, ft.Colors.ERROR)
