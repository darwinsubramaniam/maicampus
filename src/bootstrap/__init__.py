from __future__ import annotations

from typing import TYPE_CHECKING

from bootstrap.pipeline import build_pipeline
from bootstrap.wizard import create_wizard
from constants import BOOTSTRAP_FLAG

if TYPE_CHECKING:
    from collections.abc import Callable

    import flet as ft

    from ai_providers import ProviderConfig


def is_bootstrapped(page: ft.Page | None = None) -> bool:
    return BOOTSTRAP_FLAG.exists()


def _mark_bootstrapped():
    BOOTSTRAP_FLAG.parent.mkdir(parents=True, exist_ok=True)
    BOOTSTRAP_FLAG.touch()


def create_bootstrap_view(page: ft.Page, on_complete: Callable) -> ft.Container:
    """Create the onboarding wizard. on_complete(config) called when finished."""
    saved_config: dict = {"config": None}

    def on_config_ready(config: ProviderConfig):
        saved_config["config"] = config

    def get_config() -> ProviderConfig | None:
        return saved_config["config"]

    async def on_finish():
        _mark_bootstrapped()
        on_complete(saved_config["config"])

    step_defs = build_pipeline(page, on_config_ready, get_config)
    return create_wizard(page, step_defs, on_finish)
