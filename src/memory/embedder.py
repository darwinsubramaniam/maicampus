"""Text embeddings via an OpenAI-compatible embeddings API (no local model, no torch/CUDA).

AI memory is stored as vectors in SurrealDB. DeepSeek (the default chat provider) has no
embeddings endpoint, so embeddings use a dedicated OpenAI embeddings model
(``text-embedding-3-small``, 1536-dim by default). This keeps the server image small — no
``sentence-transformers``/``torch`` — and works on CPU-only Macs and servers.

Config (env):
* ``MAICAMPUS_EMBED_API_KEY`` — OpenAI key for embeddings (falls back to ``MAICAMPUS_AI_API_KEY``
  when the chat provider is also OpenAI).
* ``MAICAMPUS_EMBED_MODEL`` — default ``text-embedding-3-small``.
* ``MAICAMPUS_EMBED_BASE_URL`` — optional, for an OpenAI-compatible host.
* ``MAICAMPUS_EMBED_DIM`` — vector dimension (default 1536); must match the SurrealDB HNSW index.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

from db import EMBED_DIM
from observability import get_logger

if TYPE_CHECKING:
    from openai import OpenAI

_log = get_logger("memory.embed")
_MODEL = os.environ.get("MAICAMPUS_EMBED_MODEL", "text-embedding-3-small")
_BASE_URL = os.environ.get("MAICAMPUS_EMBED_BASE_URL") or None
_API_KEY = os.environ.get("MAICAMPUS_EMBED_API_KEY") or os.environ.get("MAICAMPUS_AI_API_KEY", "")
# `dimensions` is only honoured by text-embedding-3-* models.
_SUPPORTS_DIMENSIONS = _MODEL.startswith("text-embedding-3")

_client: OpenAI | None = None
_lock = threading.Lock()


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                from openai import OpenAI

                _client = OpenAI(api_key=_API_KEY, base_url=_BASE_URL)
    return _client


def embed(text: str) -> list[float]:
    """Embed a single string into an ``EMBED_DIM``-length vector via the embeddings API."""
    if not _API_KEY:
        _log.warning("embeddings disabled: no MAICAMPUS_EMBED_API_KEY / MAICAMPUS_AI_API_KEY set")
        raise RuntimeError("No embeddings API key configured")
    kwargs: dict = {"model": _MODEL, "input": text}
    if _SUPPORTS_DIMENSIONS:
        kwargs["dimensions"] = EMBED_DIM
    try:
        resp = _get_client().embeddings.create(**kwargs)
    except Exception:
        _log.exception("embeddings API call failed (model=%s)", _MODEL)
        raise
    vec = resp.data[0].embedding
    if len(vec) != EMBED_DIM:  # guard against a model/index dimension mismatch
        raise ValueError(f"embedding dim {len(vec)} != index dim {EMBED_DIM}")
    return list(vec)
