"""Per-user long-term memory, backed by SurrealDB's vector (HNSW) index.

Replaces the previous Mem0 + ChromaDB stack. Each memory is one ``memory`` record owned by a
``user:<id>`` link, with a 384-dim embedding produced locally (all-MiniLM-L6-v2). Recall is a
cosine-similarity search scoped to the owner, so one user's memories can never surface in
another user's context.

A ``MemoryManager`` is constructed with the owning ``user_id``. The ``user_id`` parameters on
``add_turn`` / ``search_relevant`` / ``get_all`` are kept for signature compatibility but
default to the manager's own user — which is what fixes the old "everything lands under
``default_student``" cross-contamination bug: scoping now lives in construction, not call args.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from db import get_db, user_ref
from memory import embedder

if TYPE_CHECKING:
    from surrealdb import RecordID

_TABLE = "memory"
# Cosine similarity below this is treated as "not relevant" and dropped from recall, so an
# empty/foreign query doesn't pull in unrelated memories.
_MIN_SCORE = 0.25


def uses_local_embedder(provider: object = None) -> bool:
    """Kept for compatibility: embeddings now use a hosted API, nothing to download locally."""
    return False


def warmup() -> None:
    """No-op — embeddings use a hosted API, so there's no local model to preload."""
    return None


class MemoryManager:
    def __init__(self, user_id: str):
        self._uid = user_id
        self._db = get_db()

    def _owner(self, user_id: str | None = None) -> RecordID:
        return user_ref(user_id or self._uid)

    def initialize(self):
        """Eagerly load the embedding model (call from a background thread)."""
        warmup()

    def add_turn(self, user_text: str, assistant_text: str, user_id: str | None = None):
        """Remember the salient thing the student said this turn. Best-effort: a failed
        embedding (e.g. missing key, network blip) is skipped, never propagated."""
        text = (user_text or "").strip()
        if not text:
            return
        try:
            vector = embedder.embed(text)
        except Exception:
            return
        record = {
            "owner": self._owner(user_id),
            "text": text,
            "kind": "chat",
            "embedding": vector,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._db.query(f"CREATE {_TABLE} CONTENT $data", {"data": record})

    def search_relevant(self, query: str, user_id: str | None = None, top_k: int = 5) -> list[str]:
        """Semantic search for the most relevant memories for this user. Returns [] if the
        embedding/query fails, so recall is never a hard dependency of chat."""
        q = (query or "").strip()
        if not q:
            return []
        try:
            qvec = embedder.embed(q)
            rows = self._db.query(
                f"SELECT text, vector::similarity::cosine(embedding, $q) AS score "
                f"FROM {_TABLE} WHERE owner = $owner ORDER BY score DESC LIMIT $k",
                {"q": qvec, "owner": self._owner(user_id), "k": top_k},
            )
        except Exception:
            return []
        return [r["text"] for r in rows if r.get("score", 0) >= _MIN_SCORE]

    def get_all(self, user_id: str | None = None) -> list[dict]:
        """Retrieve all memories for this user, newest first."""
        return self._db.query(
            f"SELECT text, kind, created_at FROM {_TABLE} WHERE owner = $owner ORDER BY created_at DESC",
            {"owner": self._owner(user_id)},
        )
