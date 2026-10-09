"""The LLM interface the rest of the app depends on.

Code elsewhere only uses `LLM` and `LLMResponse`, never a provider SDK, so
swapping Sarvam for another provider means writing one new class.
"""

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel

Message = dict[str, str]  # {"role": "system" | "user" | "assistant", "content": "..."}
ReasoningEffort = Literal["low", "medium", "high"]


class LLMError(Exception):
    """The LLM call failed or returned something unusable."""


class LLMResponse(BaseModel):
    """What came back from one LLM call, with its token usage and cost."""

    text: str
    data: dict[str, Any] | None = None  # parsed JSON, for structured calls
    model: str
    input_tokens: int
    output_tokens: int  # includes reasoning tokens
    reasoning_tokens: int = 0
    cost_inr: float = 0.0


class LLM(ABC):
    """A chat model that answers in plain text or in JSON matching a schema."""

    @abstractmethod
    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 1024,
        reasoning_effort: ReasoningEffort = "low",
    ) -> LLMResponse:
        """Return a plain-text answer."""

    @abstractmethod
    def complete_json(
        self,
        messages: list[Message],
        schema: dict[str, Any],
        *,
        name: str = "response",
        max_tokens: int = 1024,
        reasoning_effort: ReasoningEffort = "low",
    ) -> LLMResponse:
        """Return an answer whose `data` matches the JSON schema."""
