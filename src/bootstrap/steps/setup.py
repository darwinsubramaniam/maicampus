from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import flet as ft

from memory.manager import MemoryManager, uses_local_embedder

if TYPE_CHECKING:
    from collections.abc import Callable

    from ai_providers import ProviderConfig


def step(page: ft.Page, get_config: Callable[[], ProviderConfig | None]) -> dict:
    """First-run setup step.

    When the chosen AI provider relies on the local embedding model (Claude,
    DeepSeek), this downloads/initializes it with a live status indicator so the
    user knows what's happening. For providers with a hosted embeddings API
    (OpenAI, Gemini) nothing needs downloading and the step is a no-op.
    """
    spinner = ft.ProgressRing(width=48, height=48, visible=False)
    done_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=56, color=ft.Colors.GREEN, visible=False)
    status_text = ft.Text(
        "",
        size=15,
        text_align=ft.TextAlign.CENTER,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )
    detail_text = ft.Text(
        "",
        size=12,
        text_align=ft.TextAlign.CENTER,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )

    state = {"started": False}

    content = ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=16,
        controls=[
            ft.Stack(
                alignment=ft.Alignment.CENTER,
                controls=[spinner, done_icon],
                width=56,
                height=56,
            ),
            status_text,
            detail_text,
        ],
    )

    async def _set(status: str, detail: str = "", busy: bool = False, ok: bool = False):
        status_text.value = status
        detail_text.value = detail
        spinner.visible = busy
        done_icon.visible = ok
        page.update()

    def _finish_ready(message: str):
        page.run_task(_set, message, "", busy=False, ok=True)

    def _warm_up(config: ProviderConfig):
        try:
            MemoryManager(config).initialize()
            _finish_ready("AI memory is ready.")
        except Exception:
            # Non-fatal: the app retries memory init on startup. Don't block onboarding.
            page.run_task(
                _set,
                "Almost there — AI memory will finish setting up in the background.",
                "",
                busy=False,
                ok=True,
            )

    def on_enter():
        if state["started"]:
            return
        state["started"] = True

        config = get_config()
        if not config or not uses_local_embedder(config.provider):
            page.run_task(_set, "Nothing to download — you're ready to go.", "", busy=False, ok=True)
            return

        page.run_task(
            _set,
            "Setting up AI memory…",
            "Downloading the on-device memory model (one-time, ~90 MB). This can take a minute.",
            busy=True,
            ok=False,
        )
        threading.Thread(target=_warm_up, args=(config,), daemon=True).start()

    return {
        "title": "Finishing setup",
        "subtitle": "Getting your AI companion ready",
        "content": content,
        "next_label": "Next",
        "on_enter": on_enter,
    }
