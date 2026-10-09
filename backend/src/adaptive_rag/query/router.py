"""Pick the retrieval mode: ideal for the question, but only from indexes that exist (FR25-27).

The router never builds anything. If a better index is missing it answers with
what exists and attaches a recommendation the user can accept with one click.
"""

from adaptive_rag.schemas import Mode, QueryType, Recommendation, RoutingDecision

IDEAL_MODE: dict[QueryType, Mode] = {
    "fact_lookup": "vector",
    "semantic": "vector",
    "keyword": "hybrid",
    "relationship": "graph",
    "multi_hop": "graph",
    "comparison": "graph_hybrid",
    "aggregation": "graph_hybrid",
}

_STRENGTH: list[Mode] = ["vector", "hybrid", "graph_hybrid"]  # fallback order, weakest first


class RoutingError(Exception):
    """A manually requested mode is not available for these documents."""


def available_modes(has_bm25: bool, has_graph: bool) -> set[Mode]:
    """Modes a set of documents can run: vector always; others need their index."""
    modes: set[Mode] = {"vector"}
    if has_bm25:
        modes.add("hybrid")
    if has_graph:
        modes.add("graph")
    if has_bm25 and has_graph:
        modes.add("graph_hybrid")
    return modes


def route(
    query_type: QueryType,
    has_bm25: bool,
    has_graph: bool,
    requested: Mode | None = None,
) -> RoutingDecision:
    """Ideal mode if available; else the strongest available mode plus a recommendation."""
    ideal = IDEAL_MODE[query_type]
    available = available_modes(has_bm25, has_graph)

    if requested is not None:  # manual override for the Evaluation Lab and debugging
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
        recommendation=_recommend(ideal, has_bm25, has_graph),
    )


def _recommend(ideal: Mode, has_bm25: bool, has_graph: bool) -> Recommendation:
    """Which index to build so the ideal mode becomes available (PRD FR26 table)."""
    needs_graph = ideal in ("graph", "graph_hybrid") and not has_graph
    needs_bm25 = (ideal in ("hybrid", "graph_hybrid") or needs_graph) and not has_bm25
    if needs_graph and needs_bm25:
        index, what = "bm25+graph", "the keyword index and the knowledge graph"
    elif needs_graph:
        index, what = "graph", "the knowledge graph"
    else:
        index, what = "bm25", "the keyword index"
    names = {"graph": "GraphRAG", "graph_hybrid": "GraphRAG + Hybrid", "hybrid": "Hybrid search"}
    return Recommendation(
        better_mode=ideal,
        index_to_build=index,
        message=f"{names.get(ideal, ideal)} would be more effective for this question. "
        f"Build {what} for this document?",
    )
