"""Count tokens and cost across every LLM call made while answering one query."""

from typing import Any

from adaptive_rag.llm.base import LLM, LLMResponse, Message, ReasoningEffort


class MeteredLLM(LLM):
    """Wraps an LLM and adds up usage, so a query can report its total cost."""

    def __init__(self, inner: LLM) -> None:
        self._inner = inner
        self.model_name = inner.model_name
        self.calls = 0
        self.cached_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.reasoning_tokens = 0
        self.cost_inr = 0.0

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 1024,
        reasoning_effort: ReasoningEffort = "low",
    ) -> LLMResponse:
        return self._count(
            self._inner.complete(messages, max_tokens=max_tokens, reasoning_effort=reasoning_effort)
        )

    def complete_json(
        self,
        messages: list[Message],
        schema: dict[str, Any],
        *,
        name: str = "response",
        max_tokens: int = 1024,
        reasoning_effort: ReasoningEffort = "low",
    ) -> LLMResponse:
        return self._count(
            self._inner.complete_json(
                messages,
                schema,
                name=name,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
            )
        )

    def _count(self, response: LLMResponse) -> LLMResponse:
        self.calls += 1
        self.cached_calls += response.cached
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self.reasoning_tokens += response.reasoning_tokens
        self.cost_inr += response.cost_inr
        return response
