"""Regression tests for settings parsing (env sources)."""

from __future__ import annotations

from app.config.settings import Settings


def test_cors_origins_csv_from_env(monkeypatch) -> None:
    """A comma-separated CORS_ORIGINS env var parses into a list (not JSON-decoded).

    Regression: pydantic-settings JSON-decodes list fields from env by default,
    which broke ``CORS_ORIGINS=a,b``; ``NoDecode`` + the CSV validator fix it.
    """
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_cors_origins_default() -> None:
    """The default CORS origin is used when nothing is configured."""
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://localhost:5173"]
