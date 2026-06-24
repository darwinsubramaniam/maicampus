"""Lightweight server-side tracing for the web app.

Configures a ``maicampus`` logger that streams to stdout, so `docker compose logs webapp`
(or the console under `uv run`) shows a structured trace of the auth flow, tool calls, and
errors — instead of the app being a black box.

Level is controlled by ``MAICAMPUS_LOG_LEVEL`` (default ``INFO``; set ``DEBUG`` for verbose
tracing). Use ``get_logger("auth")`` / ``get_logger("tools")`` etc. for a namespaced child.
"""

from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False


def setup_logging() -> None:
    """Attach a stdout handler to the ``maicampus`` logger once (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.environ.get("MAICAMPUS_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    )
    root = logging.getLogger("maicampus")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced ``maicampus.<name>`` logger, configuring logging on first use."""
    setup_logging()
    return logging.getLogger(f"maicampus.{name}")
