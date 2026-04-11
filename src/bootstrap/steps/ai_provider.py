import flet as ft

from ai_providers import DEFAULT_MODELS, Provider, ProviderConfig
from settings.ai_settings import save_config


def step(on_config_ready: callable) -> dict:
    provider_dropdown = ft.Dropdown(
        label="AI Provider",
        options=[ft.DropdownOption(key=p.name, text=p.value) for p in Provider],
        value=Provider.OPENAI.name,
        width=350,
    )

    api_key_field = ft.TextField(
        label="API Key",
        password=True,
        can_reveal_password=True,
        width=400,
    )

    model_field = ft.TextField(
        label="Model (optional — leave blank for default)",
        hint_text=DEFAULT_MODELS[Provider.OPENAI],
        width=400,
    )

    error_text = ft.Text("", color=ft.Colors.RED, visible=False)

    def _on_provider_change(e):
        provider = Provider[provider_dropdown.value]
        model_field.hint_text = DEFAULT_MODELS[provider]

    provider_dropdown.on_select = _on_provider_change

    content = ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            provider_dropdown,
            ft.Container(height=10),
            api_key_field,
            ft.Container(height=10),
            model_field,
            ft.Container(height=8),
            error_text,
        ],
    )

    async def validate(page: ft.Page) -> bool:
        if not api_key_field.value.strip():
            error_text.value = "Please enter your API key."
            error_text.visible = True
            page.update()
            return False
        error_text.visible = False

        provider = Provider[provider_dropdown.value]
        config = ProviderConfig(
            provider=provider,
            api_key=api_key_field.value.strip(),
            model=model_field.value.strip() or None,
        )
        await save_config(page, config)
        on_config_ready(config)
        page.update()
        return True

    return {
        "title": "AI Provider",
        "subtitle": "Configure your AI assistant",
        "content": content,
        "next_label": "Next",
        "validate": validate,
    }
