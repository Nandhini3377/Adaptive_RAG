"""Tests for the evaluation metrics and the Evaluation Lab (offline: fake LLM, no Neo4j)."""

import shutil
from pathlib import Path

import pytest

from adaptive_rag import services
from adaptive_rag.config import settings
from adaptive_rag.eval import metrics
from adaptive_rag.eval.lab import run_lab, to_markdown, write_report
from adaptive_rag.store.bm25_store import BM25Store
from adaptive_rag.store.vector_store import VectorStore
from tests.conftest import FakeLLM

REPO_DATA = Path(__file__).resolve().parents[2] / "data"

# ----------------------------------------------------------------- metrics

GOLD = ["Leave is 20 days.", "Sick leave is 10 days."]
RETRIEVED = ["Unrelated text.", "Policy: Leave is   20 days. More.", "Sick leave is 10 days."]


def test_hit_recall_and_mrr():
    assert metrics.hit_at_k(RETRIEVED, GOLD, k=1) == 0.0
    assert metrics.hit_at_k(RETRIEVED, GOLD, k=2) == 1.0
    assert metrics.recall_at_k(RETRIEVED, GOLD, k=2) == 0.5
    assert metrics.recall_at_k(RETRIEVED, GOLD, k=3) == 1.0
    assert metrics.reciprocal_rank(RETRIEVED, GOLD) == 0.5  # first gold chunk at rank 2
    assert metrics.reciprocal_rank(["nothing"], GOLD) == 0.0


def test_evidence_match_ignores_whitespace_and_case():
    assert metrics.contains_evidence("LEAVE IS\n20 days.", "Leave is 20 days.")


def test_a_fact_written_two_ways_counts_in_either_form():
    fact = [
        "The Ledger depends on the Postgres Cluster.",
        "| Ledger | Payments | Postgres Cluster |",
    ]
    table = "| Service | Team | Depends on |\n| Ledger | Payments | Postgres Cluster |"
    assert metrics.recall_at_k([table], [fact]) == 1.0
    assert metrics.recall_at_k(["unrelated"], [fact, "Leave is 20 days."]) == 0.0


def test_answer_correctness_needs_every_keyword():
    assert metrics.answer_correct(
        "Commerce, Data Platform and Payments [1]", ["Commerce", "Payments"]
    )
    assert not metrics.answer_correct("Only Commerce", ["Commerce", "Payments"])
    assert not metrics.answer_correct("anything", [])


def test_percentiles():
    values = [10.0, 20.0, 30.0, 40.0, 100.0]
    assert metrics.percentile(values, 50) == 30.0
    assert metrics.percentile(values, 95) == pytest.approx(88.0)
    assert metrics.percentile([], 95) == 0.0


# --------------------------------------------------------------------- lab
# These index the real demo corpus with the real embedder and reranker (~2 minutes).


def lab_llm(messages):
    content = messages[0]["content"]
    if "Check an answer" in content:
        return {"claims": [{"claim": "c", "supported": True}]}
    if "Extract named entities" in content:
        return {"entities": [{"name": "Ledger", "type": "service"}], "relationships": []}
    if "Rewrite it" in content:
        return {"query": "rewritten"}
    return {"query_type": "semantic"}


@pytest.fixture
def lab_env(memory_db, tmp_path, monkeypatch):
    """The demo corpus in a temp data folder, in-memory stores, a fake LLM, no Neo4j."""
    shutil.copy(REPO_DATA / "demo_spec.yaml", tmp_path / "demo_spec.yaml")
    shutil.copytree(REPO_DATA / "demo_docs", tmp_path / "demo_docs")
    (tmp_path / "eval").mkdir()
    shutil.copy(REPO_DATA / "eval" / "questions.jsonl", tmp_path / "eval" / "questions.jsonl")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    llm = FakeLLM("The answer is 20 days [1].", data=lab_llm)
    services.override(
        vector_store=VectorStore(location=":memory:"),
        bm25_store=BM25Store(),
        graph_store=None,
        llm=llm,
    )
    yield tmp_path, llm
    services.reset()


@pytest.mark.slow
def test_retrieval_lab_scores_every_mode_without_answer_calls(lab_env):
    _, llm = lab_env
    report = run_lab(question_types=["fact_lookup", "keyword", "unanswerable"])
    sample_calls = len(llm.calls)
    assert sample_calls == 4  # one sampled analysis per document; no per-question LLM calls

    assert report["run"]["questions"] == 25
    assert set(report["modes"]) == {"vector", "hybrid", "router"}  # no graph without Neo4j
    vector = report["modes"]["vector"]["overall"]
    assert vector["hit_at_5"] >= 0.8  # real embeddings on easy fact questions
    assert 0 <= vector["mrr"] <= 1
    assert report["router"]["accuracy"] is not None
    assert {d["document"] for d in report["strategy"]["documents"]} == {
        "employee_handbook.md",
        "security_policy.html",
        "incident_runbook.md",
    }
    assert report["rule_coverage"] >= 0.8


@pytest.mark.slow
def test_second_run_reuses_the_indexed_corpus(lab_env):
    _, llm = lab_env
    run_lab(limit=2)
    calls_after_first = len(llm.calls)
    run_lab(limit=2)
    assert len(llm.calls) == calls_after_first  # no re-analysis


@pytest.mark.slow
def test_full_lab_adds_answer_metrics(lab_env):
    report = run_lab(full=True, question_types=["fact_lookup"], limit=3, modes=["vector"])
    overall = report["modes"]["vector"]["overall"]
    assert {"answer_correctness", "faithfulness", "latency_ms_p95", "cost_inr_per_query"} <= set(
        overall
    )
    assert "router" in report["modes"]
    assert overall["cost_inr_per_query"] > 0


@pytest.mark.slow
def test_report_files_are_written(lab_env):
    tmp_path, _ = lab_env
    report = run_lab(limit=3)
    json_path, md_path = write_report(report)
    assert json_path.exists() and md_path.exists()
    markdown = to_markdown(report)
    assert "| recall_at_5 |" in markdown
    assert "Router accuracy" in markdown
