import threading
from pathlib import Path

from mem0 import Memory

from ai_providers import Provider, ProviderConfig

_CHROMA_PATH = str(Path.home() / ".maicampus" / "chroma_db")

# Embedder config per provider
_EMBEDDER_CONFIG = {
    Provider.OPENAI: {
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"},
    },
    Provider.GEMINI: {
        "provider": "gemini",
        "config": {"model": "models/text-embedding-004"},
    },
    Provider.CLAUDE: {
        "provider": "huggingface",
        "config": {"model": "all-MiniLM-L6-v2"},
    },
}

# LLM provider names in Mem0
_LLM_PROVIDER = {
    Provider.OPENAI: "openai",
    Provider.CLAUDE: "anthropic",
    Provider.GEMINI: "gemini",
}


class MemoryManager:
    def __init__(self, config: ProviderConfig):
        self._config = config
        self._memory: Memory | None = None
        self._lock = threading.Lock()

    def _build_mem0_config(self) -> dict:
        embedder = _EMBEDDER_CONFIG[self._config.provider].copy()
        # Pass API key to embedder if not huggingface
        if embedder["provider"] != "huggingface":
            embedder["config"] = {**embedder["config"], "api_key": self._config.api_key}

        return {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "maicampus_memories",
                    "path": _CHROMA_PATH,
                },
            },
            "llm": {
                "provider": _LLM_PROVIDER[self._config.provider],
                "config": {
                    "api_key": self._config.api_key,
                    "model": self._config.effective_model,
                    "temperature": 0.1,
                },
            },
            "embedder": embedder,
        }

    def _ensure_initialized(self):
        if self._memory is None:
            config = self._build_mem0_config()
            self._memory = Memory.from_config(config)

    def initialize(self):
        """Eagerly initialize (call from background thread)."""
        with self._lock:
            self._ensure_initialized()

    def add_turn(self, user_text: str, assistant_text: str, user_id: str = "default_student"):
        """Store a conversation turn. Mem0 extracts facts via LLM."""
        messages = [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ]
        with self._lock:
            self._ensure_initialized()
            self._memory.add(messages, user_id=user_id)

    def search_relevant(self, query: str, user_id: str = "default_student", top_k: int = 5) -> list[str]:
        """Semantic search for relevant memories."""
        with self._lock:
            self._ensure_initialized()
            results = self._memory.search(query, user_id=user_id, limit=top_k)
        return [r["memory"] for r in results.get("results", [])]

    def get_all(self, user_id: str = "default_student") -> list[dict]:
        """Retrieve all memories for a student."""
        with self._lock:
            self._ensure_initialized()
            return self._memory.get_all(user_id=user_id)
