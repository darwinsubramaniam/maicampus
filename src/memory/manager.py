import threading

from mem0 import Memory

from ai_providers import OPENAI_COMPATIBLE_BASE_URLS, Provider, ProviderConfig
from constants import CHROMA_DB_PATH

_CHROMA_PATH = str(CHROMA_DB_PATH)

# ChromaDB's SharedSystemClient is not safe to construct concurrently for the
# same persist path — racing client creations corrupt each other's half-built
# state ("RustBindingsAPI has no attribute 'bindings'"). Several MemoryManager
# instances may initialize at once (onboarding warm-up + main app + hot reload),
# so serialize all Memory.from_config() calls process-wide.
_MEMORY_INIT_LOCK = threading.Lock()

# Embedder config per provider. DeepSeek has no embeddings API, so it falls back
# to a local HuggingFace embedder (same as Claude).
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
    Provider.DEEPSEEK: {
        "provider": "huggingface",
        "config": {"model": "all-MiniLM-L6-v2"},
    },
}

# LLM provider names in Mem0. DeepSeek is OpenAI-compatible, so it uses the
# "openai" provider pointed at the DeepSeek base URL.
_LLM_PROVIDER = {
    Provider.OPENAI: "openai",
    Provider.CLAUDE: "anthropic",
    Provider.GEMINI: "gemini",
    Provider.DEEPSEEK: "openai",
}


def uses_local_embedder(provider: Provider) -> bool:
    """True if the provider relies on a local (HuggingFace) embedding model that
    must be downloaded on first run, rather than a hosted embeddings API.

    Providers without their own embeddings endpoint (Claude, DeepSeek) fall back
    to the local model, so first-run setup needs to download it.
    """
    return _EMBEDDER_CONFIG.get(provider, {}).get("provider") == "huggingface"


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

        # Each embedder produces vectors of a different dimension (OpenAI 1536,
        # Gemini 768, local MiniLM 384). Chroma collections are fixed-dimension,
        # so scope the collection per embedder to avoid dimension-mismatch errors
        # when switching providers.
        embedder_tag = f"{embedder['provider']}_{embedder['config']['model']}"
        collection_name = "maicampus_memories_" + "".join(
            c if c.isalnum() else "_" for c in embedder_tag
        )

        llm_config = {
            "api_key": self._config.api_key,
            "model": self._config.effective_model,
            "temperature": 0.1,
        }
        # OpenAI-compatible providers (e.g. DeepSeek) need a custom base URL.
        base_url = OPENAI_COMPATIBLE_BASE_URLS.get(self._config.provider)
        if base_url:
            llm_config["openai_base_url"] = base_url

        return {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": collection_name,
                    "path": _CHROMA_PATH,
                },
            },
            "llm": {
                "provider": _LLM_PROVIDER[self._config.provider],
                "config": llm_config,
            },
            "embedder": embedder,
        }

    def _ensure_initialized(self):
        if self._memory is None:
            config = self._build_mem0_config()
            with _MEMORY_INIT_LOCK:
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
            if not self._memory:
                return
            self._memory.add(messages, user_id=user_id)

    def search_relevant(self, query: str, user_id: str = "default_student", top_k: int = 5) -> list[str]:
        """Semantic search for relevant memories."""
        with self._lock:
            self._ensure_initialized()
            if not self._memory:
                return []
            results = self._memory.search(query, filters={"user_id": user_id}, limit=top_k)
        return [r["memory"] for r in results.get("results", [])]

    def get_all(self, user_id: str = "default_student") -> list[dict]:
        """Retrieve all memories for a student."""
        with self._lock:
            self._ensure_initialized()
            if not self._memory:
                return []
            return self._memory.get_all(filters={"user_id": user_id})  # type: ignore[return-value]
