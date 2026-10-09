"""Sarvam 105B through its OpenAI-compatible chat completions API."""

import json
from typing import Any

import httpx
import openai
from openai import OpenAI

from adaptive_rag.config import settings
from adaptive_rag.llm.base import LLM, LLMError, LLMResponse, Message, ReasoningEffort


class SarvamLLM(LLM):
    """Calls Sarvam with retries and timeouts, and reports tokens and cost."""

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        """`http_client` lets tests swap in a fake server."""
        if not settings.sarvam_api_key.get_secret_value():
            raise LLMError("SARVAM_API_KEY is not set. Add it to the .env file.")
        self._model = settings.sarvam_model
        # The SDK retries rate limits (429) and server errors (5xx) with backoff.
        self._client = OpenAI(
            api_key=settings.sarvam_api_key.get_secret_value(),
            base_url=settings.sarvam_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            http_client=http_client,
        )

    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 1024,
        reasoning_effort: ReasoningEffort = "low",
    ) -> LLMResponse:
        """Return a plain-text answer."""
        return self._call(messages, max_tokens, reasoning_effort)

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
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": name, "schema": schema, "strict": True},
        }
        response = self._call(messages, max_tokens, reasoning_effort, response_format)
        try:
            response.data = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise LLMError(f"Expected JSON, got: {response.text[:200]!r}") from error
        return response

    def _call(
        self,
        messages: list[Message],
        max_tokens: int,
        reasoning_effort: ReasoningEffort,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        extra = {"response_format": response_format} if response_format else {}
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                **extra,
            )
        except openai.APIError as error:
            raise LLMError(f"Sarvam call failed: {error}") from error

        choice = completion.choices[0]
        text = (choice.message.content or "").strip()
        if not text and choice.finish_reason == "length":
            # A reasoning model can spend the whole budget thinking.
            raise LLMError(
                f"Ran out of tokens before answering (max_tokens={max_tokens}). "
                "Raise max_tokens or lower reasoning_effort."
            )

        usage = completion.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        details = usage.completion_tokens_details if usage else None
        return LLMResponse(
            text=text,
            model=completion.model or self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=(details.reasoning_tokens or 0) if details else 0,
            cost_inr=_cost_inr(input_tokens, output_tokens),
        )


def _cost_inr(input_tokens: int, output_tokens: int) -> float:
    """Price of one call in rupees."""
    return (
        input_tokens * settings.llm_input_price_inr
        + output_tokens * settings.llm_output_price_inr
    ) / 1_000_000
