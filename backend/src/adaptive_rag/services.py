"""Shared, long-lived objects (one per process), created on first use.

Embedded Qdrant locks its folder, so the whole app must share one VectorStore.
Tests swap these out with `override`.
"""

from typing import Any

from adaptive_rag.llm.base import LLM
from adaptive_rag.store.vector_store import VectorStore

_instances: dict[str, Any] = {}


def vector_store() -> VectorStore:
    if "vector_store" not in _instances:
        _instances["vector_store"] = VectorStore()
    return _instances["vector_store"]


def llm() -> LLM:
    if "llm" not in _instances:
        from adaptive_rag.llm.cache import get_llm

        _instances["llm"] = get_llm()
    return _instances["llm"]


def override(**instances: Any) -> None:
    """Replace shared objects, e.g. override(vector_store=..., llm=FakeLLM())."""
    _instances.update(instances)


def reset() -> None:
    _instances.clear()
