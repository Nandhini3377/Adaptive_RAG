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


def needs_retry(insufficient_evidence: bool, attempt: int) -> bool:
    """Return True if retrieval should be retried with a rewritten query."""
    # Retry only when the model could not answer, and stop once the budget is used up
    return insufficient_evidence and attempt < settings.max_retries


# ------------------------------------------------------------------ rewrite

_REWRITE_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
    "additionalProperties": False,
}

_REWRITE_PROMPT = """A search over company documents did not find an answer to this question.
Rewrite it as ONE short, direct question that asks for the underlying fact or rule, in
the formal words a policy or technical document would use. Keep every specific name, ID,
or code. Do not answer it, and do not write a list of keywords.

Example: "i put 11 days sick leave is that ok"
      -> "How many days of sick leave are employees entitled to?"

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

_GROUNDING_PROMPT = """Check an answer against the evidence it cites.
List the factual claims in the answer. A claim is supported when any evidence chunk
states it, or when it follows directly from applying a rule, limit, or number that a
chunk states (for example "12 sick days is not allowed" follows from "sick leave is
10 days"). A claim is NOT supported when no chunk states or implies it.
List at most 6 claims, each once. Do not list sentences that only say what the
documents do not mention.

Evidence:
{evidence}

Answer:
{answer}"""


class GroundingResult:
    """Share of claims the evidence supports, and which ones it does not."""

    def __init__(self, score: float, unsupported: list[str], tokens: int, cost_inr: float):
        self.score = score
        self.unsupported = unsupported
        self.tokens = tokens
        self.cost_inr = cost_inr

    @property
    def passed(self) -> bool:
        """Enough of the answer is supported to show it (see `grounding_threshold`)."""
        return self.score >= settings.grounding_threshold


def check_grounding(answer: Answer, llm: LLM) -> GroundingResult:
    """One LLM call: what share of the answer's claims does its cited evidence support? (FR33)"""
    if answer.insufficient_evidence:
        return GroundingResult(1.0, [], 0, 0.0)
    if not answer.citations:  # nothing cited, so nothing can be checked: not grounded
        return GroundingResult(0.0, [answer.text], 0, 0.0)
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
