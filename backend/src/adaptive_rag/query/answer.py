"""Write a grounded answer from retrieved chunks, with [n] citations (FR32)."""

import re

from adaptive_rag.config import settings
from adaptive_rag.llm.base import LLM, Message
from adaptive_rag.schemas import Answer, Citation, SearchHit

INSUFFICIENT_EVIDENCE = (
    "I don't have enough evidence in the knowledge base to answer this reliably."
)
# The model replies with this exact token when the evidence has no answer.
_NO_ANSWER_TOKEN = "NO_ANSWER"

_SYSTEM_PROMPT = f"""You answer questions about the user's documents.
Rules:
- Use ONLY the numbered evidence below. Do not use outside knowledge.
- After every sentence that states a fact, cite its evidence like [1] or [1][3].
- If the evidence does not contain the answer, reply with exactly: {_NO_ANSWER_TOKEN}
- Start with the answer itself. Do not describe your steps or restate the question.
- Be concise. Keep table values exactly as written."""

_STRICT_SUFFIX = """
- STRICT MODE: a previous answer made claims the evidence did not support.
  Only state what a cited chunk says word for word or nearly so."""

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

    response = llm.complete(
        build_messages(question, hits, strict),
        max_tokens=settings.answer_max_tokens,
        reasoning_effort=settings.answer_reasoning_effort,
    )
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
