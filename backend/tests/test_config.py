"""Tests for app settings."""

import pytest
from pydantic import ValidationError

from adaptive_rag.config import Settings


def test_defaults_load():
    """Settings load with sensible defaults."""
    s = Settings()
    assert s.embedding_model == "BAAI/bge-small-en-v1.5"
    assert s.top_k == 5


def test_env_var_overrides_default(monkeypatch):
    """An environment variable replaces the default value."""
    monkeypatch.setenv("TOP_K", "8")
    assert Settings().top_k == 8


def test_wrong_type_is_rejected(monkeypatch):
    """A non-number for TOP_K fails immediately."""
    monkeypatch.setenv("TOP_K", "abc")
    with pytest.raises(ValidationError):
        Settings()


def test_api_key_is_hidden_when_printed(monkeypatch):
    """The secret never shows up in printed output."""
    monkeypatch.setenv("SARVAM_API_KEY", "real-secret-123")
    s = Settings()
    assert "real-secret-123" not in str(s.sarvam_api_key)
    assert s.sarvam_api_key.get_secret_value() == "real-secret-123"
