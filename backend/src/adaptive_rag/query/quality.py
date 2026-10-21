"""Retrieval quality for one live question: precision and relative recall.

A real question has no gold answer, so relevance is judged by the LLM, and recall is
measured against a pool (the "pooling" method from search evaluation):

- Pool: the chunks the answer was written from, plus the top chunks that every other
  available mode finds for the same search.
- One LLM call marks which pooled chunks help answer the question.
- Precision       = relevant chunks used / chunks used
- Relative recall = relevant chunks used / relevant chunks in the whole pool

Relative recall is an upper bound on true recall: a relevant chunk that no mode found
is never counted.

Single mode (`measure_single`, the default when modes are not compared): the pool is the
candidates that one mode fetched (up to `quality_pool_size`), so
- Precision = relevant chunks in the top k / top k
- Recall    = relevant chunks in the top k / relevant chunks among the candidates
That recall shows whether reranking kept the useful chunks; a chunk the search never
fetched is not counted.

The same numbers are reported for every mode in the pool, so the answer can be compared
with the other indexes the documents have (vector-only is plain, traditional RAG). Every
mode is reranked the same way, so the comparison is between indexes, not rerankers.
"""

import logging
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel

from adaptive_rag.config import settings
from adaptive_rag.llm.base import LLM
from adaptive_rag.llm.safety import DATA_RULE, quoted
from adaptive_rag.retrieval.base import Retriever, rerank_hits
from adaptive_rag.schemas import Chunk, Mode, SearchHit

log = logging.getLogger(__name__)

Reranker = Callable[[str, list[SearchHit], int], list[SearchHit]]

_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"relevant": {"type": "array", "items": {"type": "integer"}}},
    "required": ["relevant"],
    "additionalProperties": False,
}

_JUDGE_PROMPT = """Decide which of the numbered passages help answer the question.
A passage is relevant when it states the answer or part of it, or a rule, number, or
relationship needed to work the answer out. A passage on the same topic that does not
help answer this question is NOT relevant.
Return the ids of the relevant passages, or an empty list when none help.
{data_rule}

Question: {question}

Passages:
{passages}"""


class ModeQuality(BaseModel):
    """How one search mode did on the question, against the shared pool."""

    mode: str
    used: bool  # the answer was written from this mode's chunks
    found: int  # chunks this mode returned (at most top_k)
    relevant: int  # of those, judged relevant
    precision: float | None  # None when the mode found nothing
    recall: float | None  # None with a single mode, or when nothing relevant was found


class RetrievalQuality(BaseModel):
    """How good the retrieved chunks were for one question."""

    precision: float
    relative_recall: float | None  # None: no other mode to compare, or nothing relevant found
    used: int  # chunks the answer was written from
    relevant_used: int
    relevant_in_pool: int
    pool_size: int
    compared_modes: list[str]
    modes: list[ModeQuality] = []  # the used mode first, then the others
    # "modes": recall against every mode's chunks; "candidates": against one mode's fetch
    recall_scope: Literal["modes", "candidates"] = "modes"


class Selection(BaseModel):
    """The mode whose chunks the answer is written from, and how every mode did."""

    mode: str
    hits: list[SearchHit]
    quality: RetrievalQuality


def select_mode(
    question: str,
    search_query: str,
    routed_mode: str,
    routed_hits: list[SearchHit],
    other_retrievers: dict[Mode, Retriever],
    owner_id: str,
    document_ids: list[str],
    llm: LLM,
    *,
    rerank: Reranker | None = None,
    switch: bool = True,
) -> Selection | None:
    """Search every mode, judge the pool in one LLM call, and pick the best evidence.

    Best = most relevant chunks; on a tie, the higher precision (fewer irrelevant chunks
    for the model to read); on a full tie, the router's pick. The router's pick is kept
    when nothing relevant was found, or when `switch` is off (a mode chosen by hand).
    None when no mode found any chunk.
    """
    results: dict[str, list[SearchHit]] = {routed_mode: routed_hits}
    for mode, retriever in other_retrievers.items():
        try:
            results[mode] = search_mode(
                retriever, question, search_query, owner_id, document_ids, rerank
            )
        except Exception:  # an optional comparison must never break the answer
            log.exception("Could not search with %s for the comparison pool", mode)
    if not any(results.values()):
        return None

    comparison = compare_modes(question, results, llm, routed_mode)
    chosen = routed_mode
    if switch:
        best = max(
            comparison.modes,
            key=lambda m: (m.relevant, m.precision or 0.0, m.mode == routed_mode),
        )
        if best.relevant:
            chosen = best.mode
    return Selection(mode=chosen, hits=results[chosen], quality=_quality_for(comparison, chosen))


def measure_single(
    question: str, mode: str, used: list[SearchHit], candidates: list[SearchHit], llm: LLM
) -> RetrievalQuality | None:
    """Precision and recall of one mode: its top k against everything it fetched.

    One LLM call judges the used chunks plus the other candidates (capped at
    `quality_pool_size`, in retrieval order). None when nothing was used.
    """
    if not used:
        return None
    pool: dict[str, Chunk] = {hit.chunk.id: hit.chunk for hit in used}
    for hit in candidates:
        if len(pool) >= max(settings.quality_pool_size, len(used)):
            break
        pool.setdefault(hit.chunk.id, hit.chunk)
    relevant = _judge(question, list(pool.values()), llm)
    relevant_used = sum(hit.chunk.id in relevant for hit in used)
    precision = round(relevant_used / len(used), 3)
    recall = round(relevant_used / len(relevant), 3) if relevant else None
    mine = ModeQuality(
        mode=mode,
        used=True,
        found=len(used),
        relevant=relevant_used,
        precision=precision,
        recall=recall,
    )
    return RetrievalQuality(
        precision=precision,
        relative_recall=recall,
        used=len(used),
        relevant_used=relevant_used,
        relevant_in_pool=len(relevant),
        pool_size=len(pool),
        compared_modes=[],
        modes=[mine],
        recall_scope="candidates",
    )


def measure_quality(
    question: str,
    search_query: str,
    used: list[SearchHit],
    other_retrievers: dict[Mode, Retriever],
    owner_id: str,
    document_ids: list[str],
    llm: LLM,
    *,
    used_mode: str,
    rerank: Reranker | None = None,
) -> RetrievalQuality | None:
    """Score the chunks a mode already used against the other modes (no switching).

    With `rerank`, each other mode is searched and reranked like the used one (fair);
    without it, each other mode's first `top_k` hits are taken as they come.
    """
    if not used:
        return None
    selection = select_mode(
        question,
        search_query,
        used_mode,
        used,
        other_retrievers,
        owner_id,
        document_ids,
        llm,
        rerank=rerank,
        switch=False,
    )
    return selection.quality if selection else None


def _quality_for(comparison: "ModeComparison", used_mode: str) -> RetrievalQuality:
    """The comparison seen from the mode the answer uses (listed first)."""
    modes = [m.model_copy(update={"used": m.mode == used_mode}) for m in comparison.modes]
    modes.sort(key=lambda m: not m.used)
    mine, *others = modes
    return RetrievalQuality(
        precision=mine.precision or 0.0,
        relative_recall=mine.recall,
        used=mine.found,
        relevant_used=mine.relevant,
        relevant_in_pool=len(comparison.relevant_ids),
        pool_size=comparison.pool_size,
        compared_modes=[m.mode for m in others],
        modes=modes,
    )


def search_mode(
    retriever: Retriever,
    question: str,
    search_query: str,
    owner_id: str,
    document_ids: list[str],
    rerank: Reranker | None,
) -> list[SearchHit]:
    """One mode's top chunks: candidates reranked against the question, or its first hits."""
    if rerank is None:
        found = retriever.retrieve(search_query, owner_id, document_ids, settings.top_k)
        return found.hits[: settings.top_k]
    found = retriever.retrieve(search_query, owner_id, document_ids, settings.candidate_k)
    return rerank_hits(rerank, question, found.hits, settings.top_k, found.graph_paths)


class ModeComparison(BaseModel):
    """Every mode scored against one shared, judged pool."""

    modes: list[ModeQuality]  # the used mode first
    relevant_ids: set[str]  # pooled chunks the judge marked relevant
    pool_size: int


def compare_modes(
    question: str, results: dict[str, list[SearchHit]], llm: LLM, used_mode: str | None = None
) -> ModeComparison:
    """Pool every mode's chunks, judge the pool in one LLM call, and score each mode."""
    pool: dict[str, Chunk] = {}
    for hits in results.values():
        for hit in hits:
            pool.setdefault(hit.chunk.id, hit.chunk)
    relevant = _judge(question, list(pool.values()), llm) if pool else set()
    comparable = len(results) > 1 and bool(relevant)

    modes: list[ModeQuality] = []
    for mode, hits in results.items():
        found = sum(hit.chunk.id in relevant for hit in hits)
        modes.append(
            ModeQuality(
                mode=mode,
                used=mode == used_mode,
                found=len(hits),
                relevant=found,
                precision=round(found / len(hits), 3) if hits else None,
                recall=round(found / len(relevant), 3) if comparable else None,
            )
        )
    modes.sort(key=lambda m: not m.used)  # stable: the used mode first, others in order
    return ModeComparison(modes=modes, relevant_ids=relevant, pool_size=len(pool))


def _judge(question: str, chunks: list[Chunk], llm: LLM) -> set[str]:
    """IDs of the chunks the LLM marks as relevant to the question."""
    passages = "\n\n".join(quoted(n, chunk.text) for n, chunk in enumerate(chunks, start=1))
    prompt = _JUDGE_PROMPT.format(question=question, passages=passages, data_rule=DATA_RULE)
    response = llm.complete_json(
        [{"role": "user", "content": prompt}],
        _JUDGE_SCHEMA,
        name="relevance",
        max_tokens=settings.quality_max_tokens,
        reasoning_effort=settings.structured_reasoning_effort,
    )
    numbers = (response.data or {}).get("relevant", [])
    return {chunks[n - 1].id for n in numbers if isinstance(n, int) and 1 <= n <= len(chunks)}
