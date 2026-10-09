"""Shared, long-lived objects (one per process), created on first use.

Embedded Qdrant locks its folder, so the whole app must share one VectorStore.
Neo4j is optional: without it, graph features report themselves unavailable.
Tests swap these out with `override`.
"""

import logging
from typing import Any

from adaptive_rag.llm.base import LLM
from adaptive_rag.store.bm25_store import BM25Store
from adaptive_rag.store.graph_store import GraphStore, GraphUnavailableError
from adaptive_rag.store.vector_store import VectorStore

log = logging.getLogger(__name__)
_instances: dict[str, Any] = {}


def vector_store() -> VectorStore:
    if "vector_store" not in _instances:
        _instances["vector_store"] = VectorStore()
    return _instances["vector_store"]


def bm25_store() -> BM25Store:
    if "bm25_store" not in _instances:
        _instances["bm25_store"] = BM25Store()
    return _instances["bm25_store"]


def graph_store() -> GraphStore | None:
    """The Neo4j store, or None if Neo4j is not configured or not reachable."""
    if "graph_store" not in _instances:
        try:
            _instances["graph_store"] = GraphStore()
        except GraphUnavailableError as error:
            log.warning("Graph features disabled: %s", error)
            return None  # not cached: Neo4j may be started later
    return _instances["graph_store"]


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
