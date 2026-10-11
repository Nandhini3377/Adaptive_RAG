"""Self-correction: relevance gate, query rewriting, and the grounding check (FR28-FR34)."""

from statistics import mean

from adaptive_rag.config import settings
from adaptive_rag.llm.base import LLM, LLMError
from adaptive_rag.schemas import Answer, SearchHit

# ---------------------------------------------------------------- relevance


def relevance_score(reranked: list[SearchHit]) -> float:
    """0-1 from reranker scores (no LLM call): average of top-1 and mean of top-3 (FR28)."""
    if not reranked:
        return 0.0
    scores = [hit.score for hit in reranked]
    return round((scores[0] + mean(scores[:3])) / 2, 3)


def needs_retry(relevance: float, attempt: int) -> bool:
    """Return True if retrieval should be retried with a rewritten query."""
    # Stop retrying once the budget is used up, even if relevance is low
    return relevance < settings.relevance_threshold and attempt < settings.max_retries


# ------------------------------------------------------------------ rewrite

_REWRITE_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
    "additionalProperties": False,
}

_REWRITE_PROMPT = """A search over company documents found nothing relevant for this question.
Rewrite it as a clearer search query: expand abbreviations, use the likely formal terms
documents would use, and keep every specific name, ID, or number. Do not answer it.

Original question: {question}
{previous}"""


def rewrite_query(question: str, previous: list[str], llm: LLM) -> str:
    """One LLM call that rephrases the question for search; avoids earlier attempts."""
    tried = (
        "Already tried (write something different):\n" + "\n".join(f"- {q}" for q in previous)
        if previous
        else ""
    )
    try:
        response = llm.complete_json(
            [
                {
                    "role": "user",
                    "content": _REWRITE_PROMPT.format(question=question, previous=tried),
                }
            ],
            _REWRITE_SCHEMA,
            name="rewrite",
            max_tokens=settings.rewrite_max_tokens,
            reasoning_effort=settings.structured_reasoning_effort,
        )
    except LLMError:
        return question
    rewritten = str((response.data or {}).get("query", "")).strip()
    return rewritten or question


# ---------------------------------------------------------------- grounding

_GROUNDING_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "supported": {"type": "boolean"},
                },
                "required": ["claim", "supported"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}

_GROUNDING_PROMPT = """Check an answer against its cited evidence.
Split the answer into factual claims. For each claim, decide if the evidence chunk it
cites (by [number]) clearly supports it. A claim with no citation, or citing a chunk
that does not say it, is NOT supported.

Evidence:
{evidence}

Answer:
{answer}"""


class GroundingResult:
    """Share of claims supported by their citations, and which ones failed."""

    def __init__(self, score: float, unsupported: list[str], tokens: int, cost_inr: float):
        self.score = score
        self.unsupported = unsupported
        self.tokens = tokens
        self.cost_inr = cost_inr

    @property
    def passed(self) -> bool:
        return not self.unsupported


def check_grounding(answer: Answer, llm: LLM) -> GroundingResult:
    """One LLM call: is each claim supported by the chunk it cites? (FR33)"""
    if answer.insufficient_evidence or not answer.citations:
        return GroundingResult(1.0 if answer.insufficient_evidence else 0.0, [], 0, 0.0)
    evidence = "\n\n".join(f"[{c.number}] {c.text}" for c in answer.citations)
    response = llm.complete_json(
        [
            {
                "role": "user",
                "content": _GROUNDING_PROMPT.format(evidence=evidence, answer=answer.text),
            }
        ],
        _GROUNDING_SCHEMA,
        name="grounding",
        max_tokens=settings.grounding_max_tokens,
        reasoning_effort=settings.grounding_reasoning_effort,
    )
    claims = (response.data or {}).get("claims", [])
    supported = [c for c in claims if c.get("supported")]
    unsupported = [c["claim"] for c in claims if not c.get("supported")]
    score = round(len(supported) / len(claims), 3) if claims else 1.0
    return GroundingResult(
        score, unsupported, response.input_tokens + response.output_tokens, response.cost_inr
    )
