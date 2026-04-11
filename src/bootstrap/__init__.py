import flet as ft

from ai_providers import ProviderConfig
from bootstrap.pipeline import build_pipeline
from bootstrap.wizard import create_wizard
from constants import BOOTSTRAP_FLAG


def is_bootstrapped(page: ft.Page = None) -> bool:
    return BOOTSTRAP_FLAG.exists()


def _mark_bootstrapped():
    BOOTSTRAP_FLAG.parent.mkdir(parents=True, exist_ok=True)
    BOOTSTRAP_FLAG.touch()


def create_bootstrap_view(page: ft.Page, on_complete: callable) -> ft.Container:
    """Create the onboarding wizard. on_complete(config) called when finished."""
    saved_config: dict = {"config": None}

    def on_config_ready(config: ProviderConfig):
        saved_config["config"] = config

    async def on_finish():
        _mark_bootstrapped()
        on_complete(saved_config["config"])

    step_defs = build_pipeline(on_config_ready)
    return create_wizard(page, step_defs, on_finish)
