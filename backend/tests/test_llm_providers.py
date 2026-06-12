"""Unit tests for the provider-agnostic LLM layer.

These tests assert the *gating and resolution* logic — which provider is enabled,
how the API key resolves, and that missing packages / misconfiguration degrade to
``None`` (template fallback) — without making any network calls.
"""

from __future__ import annotations

import types

from app.config.settings import Settings
from app.schemas.decision import DecisionType
from app.services import llm_providers
from app.services.llm_providers import build_chat_model
from app.services.llm_service import LLMService


def make_settings(**overrides) -> Settings:
    """Build isolated Settings (ignoring any real .env) with explicit overrides."""
    return Settings(_env_file=None, **overrides)


# ── API key resolution ─────────────────────────────────────────────────────
def test_generic_key_takes_precedence() -> None:
    """LLM_API_KEY wins over a provider-specific key."""
    settings = make_settings(
        llm_provider="openai", llm_api_key="generic", openai_api_key="specific"
    )
    assert settings.effective_api_key == "generic"


def test_provider_specific_key_fallback() -> None:
    """With no generic key, the provider-specific key is used."""
    settings = make_settings(llm_provider="groq", groq_api_key="gsk-x")
    assert settings.effective_api_key == "gsk-x"


def test_legacy_anthropic_key_still_resolves() -> None:
    """The legacy ANTHROPIC_API_KEY path is unchanged for the default provider."""
    settings = make_settings(llm_provider="anthropic", anthropic_api_key="sk-legacy")
    assert settings.effective_api_key == "sk-legacy"
    assert settings.llm_enabled is True


# ── llm_enabled gating ──────────────────────────────────────────────────────
def test_disabled_without_key() -> None:
    """A key-based provider with no key is disabled (template fallback)."""
    settings = make_settings(
        llm_provider="anthropic", anthropic_api_key=None, llm_api_key=None
    )
    assert settings.llm_enabled is False
    assert build_chat_model(settings) is None


def test_unknown_provider_disabled() -> None:
    """An unrecognized provider is disabled and builds no client."""
    settings = make_settings(llm_provider="does_not_exist", llm_api_key="x")
    assert settings.llm_enabled is False
    assert build_chat_model(settings) is None


def test_ollama_enabled_without_key() -> None:
    """Ollama (local, keyless) is enabled without any API key."""
    settings = make_settings(llm_provider="ollama", llm_api_key=None)
    assert settings.llm_enabled is True


# ── build_chat_model behavior ───────────────────────────────────────────────
def test_anthropic_builds_with_key() -> None:
    """The installed Anthropic provider constructs a real client carrying the model."""
    settings = make_settings(
        llm_provider="anthropic", llm_api_key="sk-test", llm_model="claude-opus-4-8"
    )
    client = build_chat_model(settings)
    assert client is not None
    # Read back via `.model` (this langchain-anthropic version aliases the field).
    assert getattr(client, "model", None) == "claude-opus-4-8"


def test_uninstalled_provider_degrades_to_none() -> None:
    """Selecting a provider whose package is absent returns None (no crash)."""
    # langchain-openai is not installed in the base environment.
    settings = make_settings(llm_provider="openai", llm_api_key="sk-test")
    assert settings.llm_enabled is True
    assert build_chat_model(settings) is None


def test_openai_compatible_requires_base_url() -> None:
    """openai_compatible without a base URL builds nothing."""
    settings = make_settings(llm_provider="openai_compatible", llm_api_key="sk-test")
    assert build_chat_model(settings) is None


def test_renamed_class_degrades_to_none(monkeypatch) -> None:
    """An installed package missing the expected class degrades to None, not a crash."""
    # Module imports fine but lacks the chat class (simulates a future rename).
    empty_module = types.ModuleType("fake_provider")
    monkeypatch.setattr(llm_providers.importlib, "import_module", lambda _: empty_module)
    settings = make_settings(llm_provider="anthropic", llm_api_key="sk-test")
    assert build_chat_model(settings) is None


def test_import_time_error_degrades_to_none(monkeypatch) -> None:
    """A non-ImportError raised while importing a provider degrades to None."""

    def _boom(_: str):
        raise RuntimeError("provider blew up at import")

    monkeypatch.setattr(llm_providers.importlib, "import_module", _boom)
    settings = make_settings(llm_provider="anthropic", llm_api_key="sk-test")
    assert build_chat_model(settings) is None


# ── LLMService fallback ─────────────────────────────────────────────────────
def test_llm_service_templates_when_disabled() -> None:
    """With no client, phrasing uses the template and never leaks the rationale."""
    settings = make_settings(
        llm_provider="anthropic", anthropic_api_key=None, llm_api_key=None
    )
    service = LLMService(settings=settings)
    reply = service.phrase_decision(
        "Eleanor Whitfield",
        DecisionType.APPROVED,
        rationale="INTERNAL-RATIONALE-XYZ fraud score 0.04",
    )
    assert "Eleanor" in reply
    assert "approved" in reply.lower()
    # Internal reasoning must never reach the customer message.
    assert "INTERNAL-RATIONALE-XYZ" not in reply
    assert "fraud" not in reply.lower()
