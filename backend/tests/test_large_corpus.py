"""Checks on the large evaluation corpus (offline, no LLM).

Like test_demo_corpus: if a gold sentence is not inside one chunk, the Evaluation Lab
would score retrieval against evidence nobody can find. Also checks the documents are
the size they claim and big enough that the modes can differ.
"""

import json
from pathlib import Path

import pytest

from adaptive_rag.ingest.chunker import chunk_elements
from adaptive_rag.ingest.parser import parse_file

ROOT = Path(__file__).resolve().parents[2] / "data" / "eval_large"
QUESTIONS = [json.loads(line) for line in (ROOT / "questions.jsonl").read_text().splitlines()]


@pytest.fixture(scope="module")
def chunks_by_doc():
    return {
        path.name: chunk_elements(parse_file(path), document_id=path.stem, owner_id="eval")
        for path in (ROOT / "docs").iterdir()
    }


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_every_gold_sentence_sits_whole_inside_one_chunk(question, chunks_by_doc):
    chunks = [c for doc in question["documents"] for c in chunks_by_doc[doc]]
    for evidence in question["gold_evidence"]:
        forms = [evidence] if isinstance(evidence, str) else evidence
        for form in forms:
            assert any(form in " ".join(c.text.split()) for c in chunks), form


def test_documents_are_about_twenty_pages_and_many_chunks(chunks_by_doc):
    for name, chunks in chunks_by_doc.items():
        words = len((ROOT / "docs" / name).read_text().split())
        assert 7_000 <= words <= 12_000, (name, words)  # ~15-25 pages at 500 words a page
        assert len(chunks) >= 40, (name, len(chunks))  # top 5 is a small share of it


def test_gold_evidence_fits_in_the_top_five():
    assert all(len(q["gold_evidence"]) <= 5 for q in QUESTIONS)
