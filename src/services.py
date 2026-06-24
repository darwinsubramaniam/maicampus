"""Per-user service resolution for MAI Campus (multi-user server).

The app is multi-tenant: every connected client runs its own ``main(page)`` with its own
authenticated user, but the chatbot *tools* are module-level singletons shared across all
users. To keep tools (and ``campus_api``) scoped to the right person without rewriting every
handler signature, the current user is carried in a ``ContextVar`` that ``tools.execute()``
sets around each handler call — in whatever thread the handler runs.

* UI components (built inside ``main(page)`` where the user is known) get per-user store
  instances directly via the ``get_*`` factories with an explicit ``user_id``.
* Tool handlers call the same factories with no argument; those resolve the user from the
  ContextVar. If no context is set, resolution raises — fail closed, never leak another
  user's data.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass

from campus_calendar.event_store import CalendarEventStore
from chat.session_store import SessionStore
from memory import MemoryManager


@dataclass(frozen=True)
class UserContext:
    """The authenticated identity for one request/operation."""

    user_id: str  # stable Google subject id — owner of all per-user data
    student_id: str  # linked campus matric (e.g. MEC255043) for UKB/booking calls


_request_ctx: contextvars.ContextVar[UserContext | None] = contextvars.ContextVar(
    "maicampus_request_ctx", default=None
)


def set_request_context(ctx: UserContext):
    """Bind the current user for the duration of a tool/handler call. Returns a reset token."""
    return _request_ctx.set(ctx)


def reset_request_context(token) -> None:
    _request_ctx.reset(token)


def current_context() -> UserContext:
    ctx = _request_ctx.get()
    if ctx is None:
        raise RuntimeError("No authenticated user in context for this operation.")
    return ctx


def current_user_id() -> str:
    return current_context().user_id


def current_student_id() -> str:
    return current_context().student_id


def get_calendar_store(user_id: str | None = None) -> CalendarEventStore:
    return CalendarEventStore(user_id or current_user_id())


def get_session_store(user_id: str | None = None) -> SessionStore:
    return SessionStore(user_id or current_user_id())


def get_memory_manager(user_id: str | None = None) -> MemoryManager:
    return MemoryManager(user_id or current_user_id())
