"""Shared test helpers."""

from collections.abc import Callable
from typing import Any

import pytest

from adaptive_rag.llm.base import LLM, LLMResponse, Message, ReasoningEffort
from adaptive_rag.store import db


class FakeLLM(LLM):
    """An LLM that returns scripted replies and records every prompt."""

    model_name = "fake-model"

    def __init__(
        self,
        reply: str | Callable[[list[Message]], str] = "ok",
        data: dict[str, Any] | Callable[[list[Message]], dict[str, Any]] | None = None,
    ) -> None:
        self.reply = reply
        self.data = data
        self.calls: list[list[Message]] = []

    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 1024,
        reasoning_effort: ReasoningEffort = "low",
    ) -> LLMResponse:
        self.calls.append(messages)
        text = self.reply(messages) if callable(self.reply) else self.reply
        return self._response(text)

    def complete_json(
        self,
        messages: list[Message],
        schema: dict[str, Any],
        *,
        name: str = "response",
        max_tokens: int = 1024,
        reasoning_effort: ReasoningEffort = "low",
    ) -> LLMResponse:
        self.calls.append(messages)
        data = self.data(messages) if callable(self.data) else (self.data or {})
        response = self._response("{}")
        response.data = data
        return response

    def _response(self, text: str) -> LLMResponse:
        return LLMResponse(
            text=text,
            model=self.model_name,
            input_tokens=100,
            output_tokens=20,
            reasoning_tokens=10,
            cost_inr=0.01,
        )


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def memory_db():
    """Point the app at a fresh in-memory database for one test."""
    db.configure("sqlite:///:memory:")
    yield
    db.configure("sqlite:///:memory:")  # never leave a test's data behind
