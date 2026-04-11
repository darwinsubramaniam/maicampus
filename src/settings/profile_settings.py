import json

import flet as ft

from constants import PROFILE_CACHE_PATH, make_avatar

_KEY_PREFIX = "maicampus.profile."


async def load_profile(page: ft.Page | None = None) -> dict:
    """Load saved profile from client storage."""
    from prefs import get_prefs

    prefs = get_prefs()
    name = await prefs.get(f"{_KEY_PREFIX}name") or ""
    email = await prefs.get(f"{_KEY_PREFIX}email") or ""
    pic_path = await prefs.get(f"{_KEY_PREFIX}pic_path") or ""
    return {"name": name, "email": email, "pic_path": pic_path}


async def save_profile(page: ft.Page | None = None, name: str = "", email: str = "", pic_path: str = ""):
    """Persist profile to client storage."""
    from prefs import get_prefs

    prefs = get_prefs()
    await prefs.set(f"{_KEY_PREFIX}name", name)
    await prefs.set(f"{_KEY_PREFIX}email", email)
    await prefs.set(f"{_KEY_PREFIX}pic_path", pic_path)
    # File cache for sync loading
    PROFILE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_CACHE_PATH.write_text(json.dumps({"name": name, "email": email, "pic_path": pic_path}))


def create_profile_settings(page: ft.Page) -> ft.Container:
    name_field = ft.TextField(label="Name", width=400)
    email_field = ft.TextField(label="Email", width=400)

    pic_container = ft.Container(content=make_avatar())
    pic_path_state = {"path": ""}

    status_text = ft.Text("", color=ft.Colors.GREEN)

    async def pick_photo(e):
        files = await ft.FilePicker().pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["png", "jpg", "jpeg", "webp"],
            dialog_title="Choose profile picture",
        )
        if files and files[0].path:
            pic_path_state["path"] = files[0].path
            pic_container.content = make_avatar(files[0].path)
            page.update()

    async def do_save(e):
        if not name_field.value.strip():
            status_text.value = "Name is required."
            status_text.color = ft.Colors.RED
            page.update()
            return
        if not email_field.value.strip():
            status_text.value = "Email is required."
            status_text.color = ft.Colors.RED
            page.update()
            return

        await save_profile(page, name_field.value.strip(), email_field.value.strip(), pic_path_state["path"])
        status_text.value = "Profile saved."
        status_text.color = ft.Colors.GREEN
        page.update()

    async def _populate():
        profile = await load_profile()
        name_field.value = profile["name"]
        email_field.value = profile["email"]
        if profile["pic_path"]:
            pic_path_state["path"] = profile["pic_path"]
            pic_container.content = make_avatar(profile["pic_path"])
        page.update()

    page.run_task(_populate)

    return ft.Container(
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                pic_container,
                ft.Container(height=8),
                ft.TextButton("Change photo", icon=ft.Icons.CAMERA_ALT, on_click=pick_photo),
                ft.Container(height=10),
                name_field,
                ft.Container(height=10),
                email_field,
                ft.Container(height=20),
                ft.FilledButton("Save", icon=ft.Icons.SAVE, on_click=do_save),
                ft.Container(height=10),
                status_text,
            ],
        ),
        padding=20,
    )
