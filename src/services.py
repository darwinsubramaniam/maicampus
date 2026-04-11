"""Shared service instances — single source of truth for stores and getters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from campus_calendar.event_store import CalendarEventStore

if TYPE_CHECKING:
    from collections.abc import Callable

    from memory import MemoryManager

# Shared instances
calendar_store = CalendarEventStore()

# Memory manager getter (set during app init)
_memory_getter: Callable[[], MemoryManager | None] = lambda: None


def set_memory_getter(fn: Callable[[], MemoryManager | None]):
    global _memory_getter
    _memory_getter = fn


def get_memory_manager() -> MemoryManager | None:
    return _memory_getter()


def reset():
    """Reinitialize stores after app reset."""
    global calendar_store, _memory_getter
    calendar_store = CalendarEventStore()
    _memory_getter = lambda: None
