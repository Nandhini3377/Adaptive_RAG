"""Cache LLM responses in SQLite so repeated calls cost nothing (PRD FR46)."""

import hashlib
import json
from functools import lru_cache
from typing import Any

from adaptive_rag.config import settings
from adaptive_rag.llm.base import LLM, LLMResponse, Message, ReasoningEffort
from adaptive_rag.store.db import LLMCacheEntry, session_scope


class CachedLLM(LLM):
    """Wraps another LLM; identical requests are answered from the cache."""

    def __init__(self, inner: LLM) -> None:
        self._inner = inner
        self.model_name = inner.model_name

    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 1024,
        reasoning_effort: ReasoningEffort = "low",
    ) -> LLMResponse:
        """Return a plain-text answer, from the cache when possible."""
        key = self._key("text", messages, None, max_tokens, reasoning_effort)
        return self._cached(key) or self._store(
            key,
            self._inner.complete(
                messages, max_tokens=max_tokens, reasoning_effort=reasoning_effort
            ),
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
        """Return a JSON answer, from the cache when possible."""
        key = self._key("json", messages, schema, max_tokens, reasoning_effort)
        return self._cached(key) or self._store(
            key,
            self._inner.complete_json(
                messages,
                schema,
                name=name,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
            ),
        )

    def _key(
        self,
        kind: str,
        messages: list[Message],
        schema: dict[str, Any] | None,
        max_tokens: int,
        reasoning_effort: str,
    ) -> str:
        """Same model + messages + parameters -> same key."""
        request = {
            "model": self.model_name,
            "kind": kind,
            "messages": messages,
            "schema": schema,
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
        }
        return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()

    def _cached(self, key: str) -> LLMResponse | None:
        with session_scope() as session:
            entry = session.get(LLMCacheEntry, key)
            if entry is None:
                return None
            response = LLMResponse.model_validate(entry.response)
        # A cache hit spends no tokens and costs nothing
        return response.model_copy(
            update={
                "cached": True,
                "input_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "cost_inr": 0.0,
            }
        )

    def _store(self, key: str, response: LLMResponse) -> LLMResponse:
        with session_scope() as session:
            session.merge(
                LLMCacheEntry(
                    key=key,
                    model=response.model,
                    response=response.model_dump(),
                    tokens=response.input_tokens + response.output_tokens,
                )
            )
        return response


@lru_cache(maxsize=1)
def get_llm() -> LLM:
    """The app-wide LLM: Sarvam, wrapped in the cache unless it is disabled."""
    from adaptive_rag.llm.sarvam import SarvamLLM  # import here: needs an API key

    llm: LLM = SarvamLLM()
    return CachedLLM(llm) if settings.llm_cache_enabled else llm
