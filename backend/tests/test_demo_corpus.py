"""Checks on the generated evaluation corpus (offline, no LLM).

If these fail, the Evaluation Lab would score retrieval against evidence that
the documents don't actually contain, so its numbers would be meaningless.
"""

import json
from pathlib import Path

import pytest

from adaptive_rag.ingest.chunker import chunk_elements
from adaptive_rag.ingest.parser import parse_file
from adaptive_rag.ingest.scanner import scan
from adaptive_rag.query.classifier import classify_by_rules

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "data" / "demo_docs"
QUESTIONS = [
    json.loads(line)
    for line in (ROOT / "data" / "eval" / "questions.jsonl").read_text().splitlines()
]


@pytest.fixture(scope="module")
def chunks_by_doc():
    return {
        path.name: chunk_elements(parse_file(path), document_id=path.stem, owner_id="eval")
        for path in DOCS.iterdir()
    }


def test_sixty_questions_in_the_prd_mix():
    counts: dict[str, int] = {}
    for q in QUESTIONS:
        counts[q["type"]] = counts.get(q["type"], 0) + 1
    assert counts == {
        "fact_lookup": 12,
        "keyword": 8,
        "semantic": 8,
        "relationship": 12,
        "multi_hop": 10,
        "comparison": 5,
        "unanswerable": 5,
    }
    assert len({q["id"] for q in QUESTIONS}) == 60


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_every_gold_sentence_sits_whole_inside_one_chunk(question, chunks_by_doc):
    chunks = [c for doc in question["documents"] for c in chunks_by_doc[doc]]
    for sentence in question["gold_evidence"]:
        assert any(sentence in " ".join(c.text.split()) for c in chunks), sentence


def test_unanswerable_questions_have_no_evidence():
    for q in QUESTIONS:
        assert (q["type"] == "unanswerable") == (not q["answerable"])
        if not q["answerable"]:
            assert q["gold_evidence"] == []


def test_documents_have_the_intended_profiles():
    """The scan sees what each document was designed to look like."""
    profiles = {path.name: scan(parse_file(path)) for path in DOCS.iterdir()}
    handbook = profiles["employee_handbook.md"]
    assert handbook.table_count == 0 and handbook.identifier_density < 1
    assert profiles["security_policy.html"].identifier_density > 20
    assert profiles["security_policy.html"].table_count == 2
    architecture = profiles["architecture.docx"]
    assert architecture.relationship_phrase_rate > 3 and architecture.cross_ref_rate > 2


def test_rule_classifier_coverage_on_the_eval_set():
    """Record how often rules alone are confident (the PRD's 'rule coverage')."""
    confident = sum(classify_by_rules(q["question"]).confident for q in QUESTIONS)
    assert confident / len(QUESTIONS) >= 0.8
