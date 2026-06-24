"""SurrealDB data layer for MAI Campus (multi-user server)."""

from db.surreal import EMBED_DIM, get_db, user_ref

__all__ = ["EMBED_DIM", "get_db", "user_ref"]
