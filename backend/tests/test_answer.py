"""Tests for grounded answer generation."""

from adaptive_rag.query.answer import (
    INSUFFICIENT_EVIDENCE,
    build_messages,
    cited_chunks,
    generate_answer,
)
from adaptive_rag.schemas import Chunk, SearchHit
from tests.conftest import FakeLLM


def hit(n: int, text: str, section: str = "", page: int | None = None) -> SearchHit:
    chunk = Chunk(id=f"c{n}", document_id="d", owner_id="u", text=text, section=section, page=page)
    return SearchHit(chunk=chunk, score=0.9)


HITS = [
    hit(1, "Employees receive 20 days of annual leave.", "Leave Policy", 3),
    hit(2, "Sick leave is 10 days.", "Leave Types"),
]


def test_prompt_numbers_evidence_with_sources():
    """Each chunk appears as [n] with its section and page."""
    user_prompt = build_messages("How much leave?", HITS)[1]["content"]
    assert "[1] (Section: Leave Policy, page 3)\nEmployees receive 20 days" in user_prompt
    assert "[2] (Section: Leave Types)\nSick leave is 10 days." in user_prompt
    assert user_prompt.endswith("Question: How much leave?")


def test_answer_keeps_text_and_collects_citations():
    """Citations are the chunks the answer cites, not every retrieved chunk."""
    llm = FakeLLM("Employees get 20 days of annual leave [1].")
    answer = generate_answer("How much leave?", HITS, llm)
    assert answer.text == "Employees get 20 days of annual leave [1]."
    assert [c.chunk_id for c in answer.citations] == ["c1"]
    assert answer.citations[0].section == "Leave Policy"
    assert answer.input_tokens == 100 and answer.cost_inr == 0.01


def test_citation_formats_and_bad_numbers():
    """[1][2], [2, 1], repeats, and out-of-range numbers are handled."""
    assert [c.number for c in cited_chunks("A [2, 1]. B [1][2]. C [9].", HITS)] == [
        1,
        2,
    ]


def test_model_refusal_becomes_insufficient_evidence():
    """When the model says NO_ANSWER, the user gets the standard refusal."""
    answer = generate_answer("What is the CEO's salary?", HITS, FakeLLM("NO_ANSWER"))
    assert answer.insufficient_evidence is True
    assert answer.text == INSUFFICIENT_EVIDENCE
    assert answer.citations == []


def test_no_hits_refuses_without_calling_the_llm():
    """Nothing retrieved means nothing to ground on, so skip the LLM call."""
    llm = FakeLLM("should not be used")
    answer = generate_answer("Anything?", [], llm)
    assert answer.insufficient_evidence is True
    assert llm.calls == []


def test_strict_mode_adds_stricter_rules():
    """The regenerate-once path (FR34) uses a stricter system prompt."""
    normal = build_messages("q", HITS)[0]["content"]
    strict = build_messages("q", HITS, strict=True)[0]["content"]
    assert "STRICT MODE" in strict and "STRICT MODE" not in normal
