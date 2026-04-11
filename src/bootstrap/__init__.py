import flet as ft

from ai_providers import ProviderConfig
from bootstrap.pipeline import build_pipeline
from bootstrap.wizard import create_wizard

_KEY_BOOTSTRAPPED = "maicampus.bootstrapped"


async def is_bootstrapped(page: ft.Page) -> bool:
    return await page.shared_preferences.get(_KEY_BOOTSTRAPPED) is True


async def _mark_bootstrapped(page: ft.Page):
    await page.shared_preferences.set(_KEY_BOOTSTRAPPED, True)


def create_bootstrap_view(page: ft.Page, on_complete: callable) -> ft.Container:
    """Create the onboarding wizard. on_complete(config) called when finished."""
    saved_config: dict = {"config": None}

    def on_config_ready(config: ProviderConfig):
        saved_config["config"] = config

    async def on_finish():
        await _mark_bootstrapped(page)
        on_complete(saved_config["config"])

    step_defs = build_pipeline(on_config_ready)
    return create_wizard(page, step_defs, on_finish)
