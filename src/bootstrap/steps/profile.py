import flet as ft

from constants import make_avatar
from settings.profile_settings import save_profile


def step() -> dict:
    name_field = ft.TextField(label="Name *", width=400)
    email_field = ft.TextField(label="Email *", width=400)

    pic_container = ft.Container(content=make_avatar())
    pic_path_state = {"path": ""}

    error_text = ft.Text("", color=ft.Colors.RED, visible=False)

    async def pick_photo(e):
        files = await ft.FilePicker().pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["png", "jpg", "jpeg", "webp"],
            dialog_title="Choose profile picture",
        )
        if files:
            pic_path_state["path"] = files[0].path
            pic_container.content = make_avatar(files[0].path)
            e.page.update()

    content = ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            pic_container,
            ft.Container(height=8),
            ft.TextButton("Add photo (optional)", icon=ft.Icons.CAMERA_ALT, on_click=pick_photo),
            ft.Container(height=16),
            name_field,
            ft.Container(height=10),
            email_field,
            ft.Container(height=8),
            error_text,
        ],
    )

    async def validate(page: ft.Page) -> bool:
        if not name_field.value.strip():
            error_text.value = "Please enter your name."
            error_text.visible = True
            page.update()
            return False
        if not email_field.value.strip():
            error_text.value = "Please enter your email."
            error_text.visible = True
            page.update()
            return False
        error_text.visible = False

        await save_profile(page, name_field.value.strip(), email_field.value.strip(), pic_path_state["path"])
        page.update()
        return True

    return {
        "title": "Your Profile",
        "subtitle": "Tell us a bit about yourself",
        "content": content,
        "next_label": "Next",
        "validate": validate,
    }
