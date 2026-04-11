"""Shared SharedPreferences instance — recreated per page session."""

import flet as ft


def get_prefs() -> ft.SharedPreferences:
    """Create a fresh SharedPreferences instance each time.

    SharedPreferences auto-registers with the current page context,
    so creating a new one per call ensures it's always valid.
    """
    return ft.SharedPreferences()
