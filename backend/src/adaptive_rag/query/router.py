"""Pick the retrieval mode: ideal for the question, but only from indexes that exist (FR25-27).

The router never builds anything. If a better index is missing it answers with
what exists and attaches a recommendation the user can accept with one click.
"""

from adaptive_rag.schemas import (
    MODE_INDEXES,
    Index,
    Mode,
    QueryType,
    Recommendation,
    RoutingDecision,
    index_names,
)

IDEAL_MODE: dict[QueryType, Mode] = {
    "fact_lookup": "vector",
    "semantic": "vector",
    "keyword": "hybrid",
    "relationship": "graph",
    "multi_hop": "graph",
    "comparison": "graph_hybrid",
    "aggregation": "graph_hybrid",
}

# Fallback order, weakest first. Graph alone is weakest as a fallback: it only finds
# entities named in the question (measured: it found nothing on 2 of 7 live questions).
_STRENGTH: list[Mode] = ["graph", "keyword", "vector", "hybrid", "graph_hybrid"]

_NAMES = {"vector": "the vector index", "bm25": "the keyword index", "graph": "the knowledge graph"}
_MODE_NAMES = {
    "vector": "Vector search",
    "keyword": "Keyword search",
    "hybrid": "Hybrid search",
    "graph": "GraphRAG",
    "graph_hybrid": "GraphRAG + Hybrid",
}


class RoutingError(Exception):
    """No mode can run on these documents, or a requested mode is not available."""


def available_modes(indexes: set[Index] | frozenset[Index]) -> set[Mode]:
    """Modes whose indexes all exist (for several documents: indexes they all have)."""
    return {mode for mode, needs in MODE_INDEXES.items() if needs <= indexes}


def route(
    query_type: QueryType,
    indexes: set[Index] | frozenset[Index],
    requested: Mode | None = None,
) -> RoutingDecision:
    """Ideal mode if available; else the strongest available mode plus a recommendation."""
    ideal = IDEAL_MODE[query_type]
    available = available_modes(indexes)
    if not available:
        raise RoutingError(
            "These documents share no search index (each was indexed differently). "
            "Ask them separately, or add the same index to all of them."
        )

    if requested is not None:  # manual override for debugging and comparisons
        if requested not in available:
            raise RoutingError(f"Mode '{requested}' needs an index these documents don't have")
        return RoutingDecision(ideal_mode=ideal, mode=requested, reason="mode chosen manually")

    if ideal in available:
        return RoutingDecision(
            ideal_mode=ideal,
            mode=ideal,
            reason=f"{query_type.replace('_', ' ')} question -> {ideal} (index available)",
        )

    fallback = next(mode for mode in reversed(_STRENGTH) if mode in available)
    return RoutingDecision(
        ideal_mode=ideal,
        mode=fallback,
        reason=(
            f"{query_type.replace('_', ' ')} question would be best with {ideal}, "
            f"which isn't built for these documents; using {fallback}"
        ),
        recommendation=_recommend(ideal, indexes),
    )


def _recommend(ideal: Mode, indexes: set[Index] | frozenset[Index]) -> Recommendation:
    """Which indexes to build so the ideal mode becomes available (PRD FR26 table)."""
    missing = MODE_INDEXES[ideal] - indexes
    what = " and ".join(_NAMES[index] for index in ("vector", "bm25", "graph") if index in missing)
    return Recommendation(
        better_mode=ideal,
        index_to_build=index_names(missing),
        message=f"{_MODE_NAMES[ideal]} would be more effective for this question. "
        f"Build {what} for this document?",
    )
