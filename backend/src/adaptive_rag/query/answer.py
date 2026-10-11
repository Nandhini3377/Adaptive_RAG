"""Write a grounded answer from retrieved chunks, with [n] citations (FR32)."""

import re

from adaptive_rag.config import settings
from adaptive_rag.llm.base import LLM, LLMTruncatedError, Message
from adaptive_rag.schemas import Answer, Citation, SearchHit

INSUFFICIENT_EVIDENCE = (
    "I don't have enough evidence in the knowledge base to answer this reliably."
)
# The model replies with this exact token when the evidence has no answer.
_NO_ANSWER_TOKEN = "NO_ANSWER"

_SYSTEM_PROMPT = f"""You answer questions about the user's documents.
Rules:
- Use ONLY the numbered evidence below. Do not use outside knowledge.
- Write full sentences, and end each factual sentence with its citation, like [1] or [1][3].
- For a plain question, give the fact in one or two sentences.
- When the user asks whether something in their own situation is allowed or needed,
  write in this order (the verdict comes LAST, after you have compared):
  1. The rule, limit, or number from the evidence, with its citation.
  2. The comparison: the user's number against that limit.
  3. The verdict: "So yes, ..." when it is at or below the limit, "So no, ..." when above.
- A limit only applies to the period the evidence names. A yearly allowance sets no
  limit for a single month: give the yearly figure and say no monthly limit is stated.
- Reply with exactly {_NO_ANSWER_TOKEN} only when the evidence has no fact or rule about
  what is asked.
- Do not restate the question, repeat these rules, or add remarks about what else the
  documents do not cover. Keep table values exactly as written."""

_STRICT_SUFFIX = """
- STRICT MODE: a previous answer made claims the evidence did not support.
  State only what a cited chunk says, or what follows directly from applying its
  stated rule or number. Leave out everything else."""

# Matches [1], [12], and lists like [1, 3]
_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def build_messages(question: str, hits: list[SearchHit], strict: bool = False) -> list[Message]:
    """The prompt: rules, then numbered evidence, then the question."""
    evidence = "\n\n".join(
        f"[{n}] {_source_label(hit)}\n{hit.chunk.text}" for n, hit in enumerate(hits, start=1)
    )
    system = _SYSTEM_PROMPT + (_STRICT_SUFFIX if strict else "")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Evidence:\n\n{evidence}\n\nQuestion: {question}"},
    ]


def generate_answer(question: str, hits: list[SearchHit], llm: LLM, strict: bool = False) -> Answer:
    """Ask the LLM to answer from the hits; refuse when there is no evidence."""
    if not hits:
        return Answer(text=INSUFFICIENT_EVIDENCE, insufficient_evidence=True)

    messages = build_messages(question, hits, strict)
    options = {
        "max_tokens": settings.answer_max_tokens,
        "reasoning_effort": settings.answer_reasoning_effort,
    }
    try:
        response = llm.complete(messages, **options)
    except LLMTruncatedError:  # a rare runaway reply; a second try is usually normal
        response = llm.complete(messages, **options)
    usage = {
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "reasoning_tokens": response.reasoning_tokens,
        "cost_inr": response.cost_inr,
    }
    if _NO_ANSWER_TOKEN in response.text:
        return Answer(text=INSUFFICIENT_EVIDENCE, insufficient_evidence=True, **usage)
    return Answer(text=response.text, citations=cited_chunks(response.text, hits), **usage)


def cited_chunks(text: str, hits: list[SearchHit]) -> list[Citation]:
    """The hits the answer actually cites, in order; bad numbers are ignored."""
    numbers: list[int] = []
    for match in _CITATION.finditer(text):
        for part in match.group(1).split(","):
            number = int(part)
            if 1 <= number <= len(hits) and number not in numbers:
                numbers.append(number)
    return [
        Citation(
            number=n,
            chunk_id=hits[n - 1].chunk.id,
            document_id=hits[n - 1].chunk.document_id,
            section=hits[n - 1].chunk.section,
            page=hits[n - 1].chunk.page,
            text=hits[n - 1].chunk.text,
        )
        for n in sorted(numbers)
    ]


def _source_label(hit: SearchHit) -> str:
    """'(Section: Leave Policy, page 3)' so the model can mention where facts are."""
    parts = []
    if hit.chunk.section:
        parts.append(f"Section: {hit.chunk.section}")
    if hit.chunk.page:
        parts.append(f"page {hit.chunk.page}")
    return f"({', '.join(parts)})" if parts else ""
