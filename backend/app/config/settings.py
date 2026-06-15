"""Typed application settings.

Settings are loaded once and cached via :func:`get_settings`, which is used as a
FastAPI dependency. Centralizing configuration here keeps environment access out
of business logic and makes the app trivially testable (override the cache).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repository roots resolved relative to this file so the app is CWD-independent.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _BACKEND_ROOT / "data"


class Settings(BaseSettings):
    """Strongly-typed runtime configuration sourced from the environment / ``.env``.

    Every field has a production-safe default so the application boots with zero
    configuration, which is essential for a reproducible demo.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── App ────────────────────────────────────────────────────────────────
    app_name: str = "RefundFlow AI"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"

    # ── LLM (optional phrasing layer) ──────────────────────────────────────
    # Provider-agnostic: pick any LangChain-supported chat provider. The active
    # provider's integration package must be installed (see requirements.txt);
    # otherwise the layer degrades to the deterministic template responder.
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-4-8"
    llm_temperature: float = 0.2
    # Generic key/base-url applied to whichever provider is selected.
    llm_api_key: str | None = Field(default=None)
    llm_base_url: str | None = Field(default=None)
    # Optional provider-specific keys (used as a fallback when ``llm_api_key``
    # is unset). ``anthropic_api_key`` is kept for backward compatibility.
    anthropic_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    groq_api_key: str | None = Field(default=None)
    google_api_key: str | None = Field(default=None)
    mistral_api_key: str | None = Field(default=None)

    # ── Persistence ────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./refundflow.db"

    # ── Policy knobs (mirrored in data/refund_policy.md) ───────────────────
    refund_window_days: int = 30
    max_refunds_per_6_months: int = 3
    fraud_score_threshold: float = 0.7
    fraud_escalation_band: float = 0.15

    # ── Demo pacing ────────────────────────────────────────────────────────
    # A small per-node delay so the SSE stream is visibly animated in the UI
    # (the deterministic graph would otherwise finish in a few milliseconds).
    # Set to 0 to disable for production/throughput.
    node_delay_seconds: float = 0.35

    # ── LiveKit voice agent (optional) ────────────────────────────────────
    livekit_url: str | None = Field(default=None)
    livekit_api_key: str | None = Field(default=None)
    livekit_api_secret: str | None = Field(default=None)

    # ── Logging ────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_json: bool = True

    # ── CORS ───────────────────────────────────────────────────────────────
    # ``NoDecode`` stops pydantic-settings from JSON-decoding the env value, so
    # the validator below can accept a plain comma-separated string.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Allow ``CORS_ORIGINS`` to be supplied as a comma-separated string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def data_dir(self) -> Path:
        """Absolute path to the bundled mock-data directory."""
        return _DATA_DIR

    # Providers that authenticate with an API key (everything except local Ollama).
    _KEY_BASED_PROVIDERS: ClassVar[frozenset[str]] = frozenset(
        {"anthropic", "openai", "openai_compatible", "groq", "google_genai", "mistral"}
    )

    @property
    def effective_api_key(self) -> str | None:
        """Resolve the API key for the active provider.

        Resolution order: the generic ``LLM_API_KEY`` first, then the
        provider-specific key (e.g. ``OPENAI_API_KEY``). Returns ``None`` for
        Ollama (a local server needs no key) or when nothing is configured.
        """
        if self.llm_api_key:
            return self.llm_api_key
        provider_key = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "openai_compatible": self.openai_api_key,
            "groq": self.groq_api_key,
            "google_genai": self.google_api_key,
            "mistral": self.mistral_api_key,
        }
        return provider_key.get(self.llm_provider.strip().lower())

    @property
    def llm_enabled(self) -> bool:
        """Whether the optional LLM phrasing layer is active for this provider.

        Key-based providers are enabled once a key resolves; Ollama is always
        enabled (local, keyless); unknown providers are disabled. When ``False``
        the application uses the deterministic templated responder.
        """
        provider = self.llm_provider.strip().lower()
        if provider == "ollama":
            return True
        if provider not in self._KEY_BASED_PROVIDERS:
            return False
        return bool(self.effective_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached :class:`Settings` instance.

    Cached so configuration is parsed exactly once. Tests clear the cache via
    ``get_settings.cache_clear()`` to inject overrides.
    """
    return Settings()
