"""Provider-agnostic chat-model factory.

Builds a LangChain chat model for the configured provider (Anthropic, OpenAI,
Google Gemini, Groq, Mistral, Ollama, or any OpenAI-API-compatible endpoint).
Each provider's integration package is imported **lazily** so only the active
provider's package needs to be installed; a missing package or construction
error degrades gracefully to ``None`` (the caller then uses the deterministic
template responder).

We deliberately use a small explicit registry rather than
``langchain.chat_models.init_chat_model``: the umbrella ``langchain`` package is
not a dependency of this project, and a registry gives precise control over the
(version-verified) constructor kwargs for each provider.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.observability.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from langchain_core.language_models.chat_models import BaseChatModel

    from app.config.settings import Settings

_logger = get_logger(__name__)


@dataclass(frozen=True)
class ProviderSpec:
    """Describes how to import and construct one provider's chat model.

    Attributes:
        key: Provider identifier used in ``LLM_PROVIDER``.
        pip_package: The package an operator must install to use this provider.
        import_path: Dotted module path holding the chat class.
        class_name: Chat model class name within ``import_path``.
        supports_api_key: Whether to pass ``api_key=`` (Ollama does not).
        supports_base_url: Whether to pass ``base_url=`` (Gemini does not).
        requires_base_url: Whether a base URL is mandatory (OpenAI-compatible).
    """

    key: str
    pip_package: str
    import_path: str
    class_name: str
    supports_api_key: bool = True
    supports_base_url: bool = True
    requires_base_url: bool = False


# Constructor kwargs (model=/api_key=/base_url=) verified against the installed
# LangChain integration packages. ``openai_compatible`` reuses ChatOpenAI with a
# mandatory custom base_url (Together / OpenRouter / vLLM / local servers).
PROVIDERS: dict[str, ProviderSpec] = {
    "anthropic": ProviderSpec(
        "anthropic", "langchain-anthropic", "langchain_anthropic", "ChatAnthropic"
    ),
    "openai": ProviderSpec(
        "openai", "langchain-openai", "langchain_openai", "ChatOpenAI"
    ),
    "google_genai": ProviderSpec(
        "google_genai",
        "langchain-google-genai",
        "langchain_google_genai",
        "ChatGoogleGenerativeAI",
        supports_base_url=False,  # Gemini API has no base_url kwarg
    ),
    "groq": ProviderSpec("groq", "langchain-groq", "langchain_groq", "ChatGroq"),
    "mistral": ProviderSpec(
        "mistral", "langchain-mistralai", "langchain_mistralai", "ChatMistralAI"
    ),
    "ollama": ProviderSpec(
        "ollama",
        "langchain-ollama",
        "langchain_ollama",
        "ChatOllama",
        supports_api_key=False,  # local server, keyless
    ),
    "openai_compatible": ProviderSpec(
        "openai_compatible",
        "langchain-openai",
        "langchain_openai",
        "ChatOpenAI",
        requires_base_url=True,
    ),
}


def build_chat_model(settings: "Settings") -> "BaseChatModel | None":
    """Construct the chat model for the configured provider, or ``None``.

    Returns ``None`` (so the caller falls back to templated phrasing) when:
    the provider is unknown, the layer is disabled (no key for a key-based
    provider), a required base URL is missing, the provider's package is not
    installed, or construction otherwise fails. All non-fatal — the application
    keeps working without any LLM.

    Args:
        settings: The active application settings.

    Returns:
        A LangChain ``BaseChatModel`` instance, or ``None``.
    """
    provider = settings.llm_provider.strip().lower()
    spec = PROVIDERS.get(provider)
    if spec is None:
        _logger.warning("llm_unknown_provider", provider=provider)
        return None
    if not settings.llm_enabled:
        return None  # offline-by-default gate (no key resolved)
    if spec.requires_base_url and not settings.llm_base_url:
        _logger.warning("llm_missing_base_url", provider=provider)
        return None

    try:
        module = importlib.import_module(spec.import_path)
        chat_cls = getattr(module, spec.class_name)
    except ImportError as exc:
        _logger.warning(
            "llm_provider_not_installed",
            provider=provider,
            package=spec.pip_package,
            error=str(exc),
        )
        return None
    except Exception as exc:  # pragma: no cover - API drift / import-time failures
        # The package is installed but importing/resolving the class failed
        # (e.g. the class was renamed in a newer version → AttributeError, or the
        # package raised at import). Degrade to None per the documented contract.
        _logger.warning(
            "llm_provider_import_failed",
            provider=provider,
            package=spec.pip_package,
            error=str(exc),
        )
        return None

    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
    }
    if spec.supports_api_key and settings.effective_api_key:
        kwargs["api_key"] = settings.effective_api_key
    if spec.supports_base_url and settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url

    try:
        return chat_cls(**kwargs)
    except Exception as exc:  # pragma: no cover - provider/credential edge cases
        _logger.warning("llm_init_failed", provider=provider, error=str(exc))
        return None
