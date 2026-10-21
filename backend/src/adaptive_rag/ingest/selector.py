"""Step 3: scan + intent -> strategy, with a confidence and a plain-language reason (FR15).

The PRD decision table, row by row:

| Scan says          | Uploader intent          | Strategy     | Notes                      |
|--------------------|--------------------------|--------------|----------------------------|
| Small, plain prose | facts only               | vector       | cheapest path              |
| Few relationships  | facts and/or exact_terms | hybrid       | default for most documents |
| Few relationships  | connections or compare   | hybrid       | warn: few relationships    |
| Many relationships | connections or compare   | graph_hybrid | full graph extraction runs |
| Many relationships | facts and/or exact_terms | hybrid       | marked graph_candidate     |
| Many relationships | skipped                  | graph_hybrid | scan alone decides         |
"""

from adaptive_rag.config import settings
from adaptive_rag.ingest.intent import many_relationships
from adaptive_rag.schemas import DocumentProfile, Intent, StrategyDecision

_GRAPH_INTENTS = {"connections", "compare"}


def is_small_plain(profile: DocumentProfile) -> bool:
    """PRD FR16: short, few IDs, few tables."""
    return (
        profile.page_count < settings.small_plain_max_pages
        and profile.identifier_density < settings.small_plain_max_identifier_density
        and profile.table_share < settings.small_plain_max_table_share
    )


def decide(profile: DocumentProfile, intents: list[Intent] | None) -> StrategyDecision:
    """Pick vector, hybrid, or graph_hybrid. `intents=None` means the uploader skipped."""
    many = many_relationships(profile)
    small_plain = is_small_plain(profile)
    scan_summary = _scan_summary(profile, many)
    clarity = _signal_clarity(profile)

    if intents is None:
        if many:
            return StrategyDecision(
                strategy="graph_hybrid",
                confidence=_confidence(clarity),
                reason=f"{scan_summary} No intent was given, so the scan decides: build the graph.",
            )
        strategy = "vector" if small_plain else "hybrid"
        return StrategyDecision(
            strategy=strategy,
            confidence=_confidence(clarity),
            reason=f"{scan_summary} No intent was given, so the scan decides.",
        )

    wants_graph = bool(_GRAPH_INTENTS.intersection(intents))
    if many and wants_graph:
        return StrategyDecision(
            strategy="graph_hybrid",
            confidence=_confidence(clarity, agrees=True),
            reason=f"{scan_summary} You want to explore connections, so a graph is built.",
        )
    if many:
        return StrategyDecision(
            strategy="hybrid",
            confidence=_confidence(clarity, agrees=False),
            reason=(
                f"{scan_summary} You mainly want facts and exact terms, so the graph is skipped "
                "for now. It will be recommended if you ask relationship questions."
            ),
            graph_candidate=True,
        )
    if wants_graph:
        return StrategyDecision(
            strategy="hybrid",
            confidence=_confidence(clarity, agrees=False),
            reason=f"{scan_summary} Hybrid search fits best.",
            warning=(
                "This document has few relationships, so a graph would add little. "
                "You can still build it manually."
            ),
        )
    if small_plain and set(intents) == {"facts"}:
        return StrategyDecision(
            strategy="vector",
            confidence=_confidence(clarity, agrees=True),
            reason=f"{scan_summary} Plain fact lookups need only vector search (cheapest).",
        )
    return StrategyDecision(
        strategy="hybrid",
        confidence=_confidence(clarity, agrees=True),
        reason=f"{scan_summary} Hybrid (meaning + exact keywords) is the safe default.",
    )


def _scan_summary(profile: DocumentProfile, many: bool) -> str:
    """One sentence with the numbers behind the decision."""
    relationships = "many relationships" if many else "few relationships"
    return (
        f"The scan found {relationships} ({profile.relationship_density:.1f} per entity in "
        f"the sample, {profile.cross_ref_rate:.1f} cross-references and "
        f"{profile.relationship_phrase_rate:.1f} relationship phrases per 1,000 words), "
        f"{profile.identifier_density:.1f} IDs per 1,000 words, "
        f"{profile.table_share:.0%} of text in tables, and about {profile.page_count} pages."
    )


def _signal_clarity(profile: DocumentProfile) -> float:
    """0-1: how far the relationship signal is from its threshold (far = clear)."""
    threshold = settings.many_relationships_density
    distance = abs(profile.relationship_density - threshold) / threshold
    return min(1.0, distance)


def _confidence(clarity: float, agrees: bool | None = None) -> float:
    """Start at 0.6; a clear scan adds up to 0.2; intent agreeing adds 0.15, disagreeing -0.1."""
    confidence = 0.6 + 0.2 * clarity
    if agrees is True:
        confidence += 0.15
    elif agrees is False:
        confidence -= 0.1
    return round(min(0.95, max(0.3, confidence)), 2)
