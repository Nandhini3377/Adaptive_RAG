"""Retrieval quality for one live question: precision and relative recall.

A real question has no gold answer, so relevance is judged by the LLM, and recall is
measured against a pool (the "pooling" method from search evaluation):

- Pool: the chunks the answer was written from, plus the top chunks that every other
  available mode finds for the same search.
- One LLM call marks which pooled chunks help answer the question.
- Precision       = relevant chunks used / chunks used
- Relative recall = relevant chunks used / relevant chunks in the whole pool

Relative recall is an upper bound on true recall: a relevant chunk that no mode found
is never counted. With a single mode there is nothing to compare, so it is None.
"""

import logging

from pydantic import BaseModel

from adaptive_rag.config import settings
from adaptive_rag.llm.base import LLM
from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.schemas import Chunk, Mode, SearchHit

log = logging.getLogger(__name__)

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
Return the numbers of the relevant passages, or an empty list when none help.

Question: {question}

Passages:
{passages}"""


class RetrievalQuality(BaseModel):
    """How good the retrieved chunks were for one question."""

    precision: float
    relative_recall: float | None  # None: no other mode to compare, or nothing relevant found
    used: int  # chunks the answer was written from
    relevant_used: int
    relevant_in_pool: int
    pool_size: int
    compared_modes: list[str]


def measure_quality(
    question: str,
    search_query: str,
    used: list[SearchHit],
    other_retrievers: dict[Mode, Retriever],
    owner_id: str,
    document_ids: list[str],
    llm: LLM,
) -> RetrievalQuality | None:
    """Judge the pooled chunks with one LLM call; None when no chunks were retrieved."""
    if not used:
        return None
    pool: dict[str, Chunk] = {hit.chunk.id: hit.chunk for hit in used}
    compared: list[str] = []
    for mode, retriever in other_retrievers.items():
        try:
            found = retriever.retrieve(search_query, owner_id, document_ids, settings.top_k)
        except Exception:  # an optional comparison must never break the answer
            log.exception("Could not search with %s for the recall pool", mode)
            continue
        compared.append(mode)
        for hit in found.hits[: settings.top_k]:
            pool.setdefault(hit.chunk.id, hit.chunk)

    relevant = _judge(question, list(pool.values()), llm)
    relevant_used = sum(hit.chunk.id in relevant for hit in used)
    return RetrievalQuality(
        precision=round(relevant_used / len(used), 3),
        relative_recall=round(relevant_used / len(relevant), 3) if compared and relevant else None,
        used=len(used),
        relevant_used=relevant_used,
        relevant_in_pool=len(relevant),
        pool_size=len(pool),
        compared_modes=compared,
    )


def _judge(question: str, chunks: list[Chunk], llm: LLM) -> set[str]:
    """IDs of the chunks the LLM marks as relevant to the question."""
    passages = "\n\n".join(f"[{n}] {chunk.text}" for n, chunk in enumerate(chunks, start=1))
    response = llm.complete_json(
        [{"role": "user", "content": _JUDGE_PROMPT.format(question=question, passages=passages)}],
        _JUDGE_SCHEMA,
        name="relevance",
        max_tokens=settings.quality_max_tokens,
        reasoning_effort=settings.structured_reasoning_effort,
    )
    numbers = (response.data or {}).get("relevant", [])
    return {chunks[n - 1].id for n in numbers if isinstance(n, int) and 1 <= n <= len(chunks)}
