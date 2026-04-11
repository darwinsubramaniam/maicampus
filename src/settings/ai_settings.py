import flet as ft

from ai_providers import DEFAULT_MODELS, Provider, ProviderConfig

_KEY_PREFIX = "maicampus.ai."


async def load_config(page: ft.Page = None) -> ProviderConfig | None:
    """Load saved AI config from client storage."""
    from prefs import get_prefs
    prefs = get_prefs()
    provider_name = await prefs.get(f"{_KEY_PREFIX}provider")
    api_key = await prefs.get(f"{_KEY_PREFIX}api_key")
    if not provider_name or not api_key:
        return None
    model = await prefs.get(f"{_KEY_PREFIX}model")
    return ProviderConfig(
        provider=Provider[provider_name],
        api_key=api_key,
        model=model or None,
    )


async def save_config(page: ft.Page = None, config: ProviderConfig = None):
    """Persist AI config to client storage."""
    from prefs import get_prefs
    prefs = get_prefs()
    await prefs.set(f"{_KEY_PREFIX}provider", config.provider.name)
    await prefs.set(f"{_KEY_PREFIX}api_key", config.api_key)
    if config.model:
        await prefs.set(f"{_KEY_PREFIX}model", config.model)
    else:
        await prefs.remove(f"{_KEY_PREFIX}model")


def create_ai_settings(page: ft.Page, on_save: callable) -> ft.Container:
    provider_dropdown = ft.Dropdown(
        label="AI Provider",
        options=[ft.DropdownOption(key=p.name, text=p.value) for p in Provider],
        value=Provider.OPENAI.name,
        width=300,
        on_select=lambda e: _update_model_hint(),
    )

    api_key_field = ft.TextField(
        label="API Key",
        password=True,
        can_reveal_password=True,
        width=400,
    )

    model_field = ft.TextField(
        label="Model (leave blank for default)",
        hint_text=DEFAULT_MODELS[Provider.OPENAI],
        width=400,
    )

    status_text = ft.Text("", color=ft.Colors.GREEN)

    def _update_model_hint():
        provider = Provider[provider_dropdown.value]
        model_field.hint_text = DEFAULT_MODELS[provider]
        page.update()

    async def save_click(e):
        if not api_key_field.value.strip():
            status_text.value = "API key is required."
            status_text.color = ft.Colors.RED
            page.update()
            return

        provider = Provider[provider_dropdown.value]
        config = ProviderConfig(
            provider=provider,
            api_key=api_key_field.value.strip(),
            model=model_field.value.strip() or None,
        )
        await save_config(page, config)
        on_save(config)
        status_text.value = f"Saved — using {provider.value} ({config.effective_model})"
        status_text.color = ft.Colors.GREEN
        page.update()

    async def _populate_from_storage():
        config = await load_config()
        if config:
            provider_dropdown.value = config.provider.name
            api_key_field.value = config.api_key
            model_field.value = config.model or ""
            model_field.hint_text = DEFAULT_MODELS[config.provider]
            on_save(config)
            status_text.value = f"Loaded — {config.provider.value} ({config.effective_model})"
            status_text.color = ft.Colors.GREEN
            page.update()

    page.run_task(_populate_from_storage)

    return ft.Container(
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                provider_dropdown,
                ft.Container(height=10),
                api_key_field,
                ft.Container(height=10),
                model_field,
                ft.Container(height=20),
                ft.FilledButton("Save", icon=ft.Icons.SAVE, on_click=save_click),
                ft.Container(height=10),
                status_text,
            ],
        ),
        padding=20,
    )
