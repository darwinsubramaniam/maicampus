import flet as ft

_KEY_PREFIX = "maicampus.profile."


async def load_profile(page: ft.Page) -> dict:
    """Load saved profile from client storage."""
    name = await page.shared_preferences.get(f"{_KEY_PREFIX}name") or ""
    email = await page.shared_preferences.get(f"{_KEY_PREFIX}email") or ""
    pic_path = await page.shared_preferences.get(f"{_KEY_PREFIX}pic_path") or ""
    return {"name": name, "email": email, "pic_path": pic_path}


async def save_profile(page: ft.Page, name: str, email: str, pic_path: str = ""):
    """Persist profile to client storage."""
    await page.shared_preferences.set(f"{_KEY_PREFIX}name", name)
    await page.shared_preferences.set(f"{_KEY_PREFIX}email", email)
    await page.shared_preferences.set(f"{_KEY_PREFIX}pic_path", pic_path)


def _make_avatar(pic_path: str = "") -> ft.CircleAvatar:
    if pic_path:
        return ft.CircleAvatar(foreground_image_src=pic_path, radius=40)
    return ft.CircleAvatar(
        content=ft.Icon(ft.Icons.PERSON, size=32),
        radius=40,
        bgcolor=ft.Colors.PRIMARY_CONTAINER,
    )


def create_profile_settings(page: ft.Page) -> ft.Container:
    name_field = ft.TextField(label="Name", width=400)
    email_field = ft.TextField(label="Email", width=400)

    pic_container = ft.Container(content=_make_avatar())
    pic_path_state = {"path": ""}

    status_text = ft.Text("", color=ft.Colors.GREEN)

    async def pick_photo(e):
        files = await ft.FilePicker().pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["png", "jpg", "jpeg", "webp"],
            dialog_title="Choose profile picture",
        )
        if files:
            pic_path_state["path"] = files[0].path
            pic_container.content = _make_avatar(files[0].path)
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
        profile = await load_profile(page)
        name_field.value = profile["name"]
        email_field.value = profile["email"]
        if profile["pic_path"]:
            pic_path_state["path"] = profile["pic_path"]
            pic_container.content = _make_avatar(profile["pic_path"])
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
