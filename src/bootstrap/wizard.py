from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from collections.abc import Callable


def create_wizard(page: ft.Page, step_defs: list[dict], on_finish: Callable) -> ft.Container:
    """
    Generic step-by-step wizard.

    step_defs: list of dicts with keys:
        - title: str
        - subtitle: str
        - content: ft.Control
        - next_label: str
        - validate: optional async callable(page) -> bool (return False to block advancing)
        - on_enter: optional callable() invoked when step becomes active

    on_finish: async callable invoked when the last step's next button is clicked.
    """
    current_step = {"index": 0}

    step_title = ft.Text("", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
    step_subtitle = ft.Text("", size=14, color=ft.Colors.ON_SURFACE_VARIANT)
    step_body = ft.Container(expand=True)
    step_indicator = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)

    back_btn = ft.OutlinedButton("Back", icon=ft.Icons.ARROW_BACK, visible=False)
    next_btn = ft.FilledButton("Next", icon_color=ft.Colors.WHITE)

    def _render_step():
        step = step_defs[current_step["index"]]
        step_title.value = step["title"]
        step_subtitle.value = step["subtitle"]
        step_body.content = step["content"]
        step_indicator.value = f"Step {current_step['index'] + 1} of {len(step_defs)}"
        back_btn.visible = current_step["index"] > 0
        next_btn.text = step["next_label"]  # type: ignore[assignment]
        on_enter = step.get("on_enter")
        if on_enter:
            on_enter()
        page.update()

    def _go_back(e):
        if current_step["index"] > 0:
            current_step["index"] -= 1
            _render_step()

    async def _go_next(e):
        idx = current_step["index"]
        step = step_defs[idx]

        # Run validation if defined
        validate = step.get("validate")
        if validate and not await validate(page):
            return

        # Last step — finish
        if idx == len(step_defs) - 1:
            await on_finish()
            return

        current_step["index"] += 1
        _render_step()

    back_btn.on_click = _go_back
    next_btn.on_click = _go_next

    _render_step()

    return ft.Container(
        expand=True,
        padding=40,
        content=ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                step_indicator,
                ft.Container(height=10),
                step_title,
                step_subtitle,
                ft.Container(height=30),
                ft.Container(content=step_body, expand=True, alignment=ft.Alignment.CENTER),
                ft.Container(height=20),
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[back_btn, next_btn],
                    spacing=16,
                ),
            ],
        ),
    )
