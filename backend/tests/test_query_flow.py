"""Tests for classification, routing, self-correction, and the LangGraph query flow."""

import pytest

from adaptive_rag.query.answer import INSUFFICIENT_EVIDENCE
from adaptive_rag.query.classifier import classify, classify_by_rules
from adaptive_rag.query.correction import check_grounding, needs_retry, relevance_score
from adaptive_rag.query.pipeline import QueryPipeline
from adaptive_rag.query.router import RoutingError, route
from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.schemas import Answer, Chunk, Citation, RetrievalResult, SearchHit
from tests.conftest import FakeLLM

# ------------------------------------------------------------- classifier


@pytest.mark.parametrize(
    ("question", "expected"),
    [  # the PRD's own example questions (Section 16)
        ("How many days of annual leave do employees get?", "fact_lookup"),
        ("What does error code AUTH-403 mean?", "keyword"),
        ("What services depend on Auth Service?", "relationship"),
        ("Which teams own services affected by the payment migration?", "multi_hop"),
        ("Compare auth approaches in Service A and Service B.", "comparison"),
        ("List all services in the platform", "aggregation"),
        ('What is the "grace period"?', "keyword"),
        ("Who owns the Payments service?", "relationship"),
        ("What is the relationship between Orders and Payments?", "relationship"),
        ("Which services indirectly depend on the database?", "multi_hop"),
    ],
)
def test_rules_classify_prd_examples(question, expected):
    result = classify_by_rules(question)
    assert result.query_type == expected
    assert result.confident


def test_rules_extract_ids_and_quoted_terms_as_entities():
    assert classify_by_rules('Is "SOC 2" related to AUTH-403?').entities == ["SOC 2", "AUTH-403"]


def test_unsure_rules_fall_back_to_the_llm_once():
    llm = FakeLLM(data={"query_type": "semantic"})
    result = classify("Tell me about our approach to customer data deletion", llm)
    assert result.source == "llm" and result.query_type == "semantic"
    assert len(llm.calls) == 1


def test_confident_rules_never_call_the_llm():
    llm = FakeLLM()
    classify("Compare plan A and plan B", llm)
    assert llm.calls == []


# ------------------------------------------------------------------ router


@pytest.mark.parametrize(
    ("built", "query_type", "used", "build"),
    [  # PRD FR26 table: built indexes x ideal mode -> mode used + recommendation
        ("vector", "fact_lookup", "vector", None),
        ("vector", "keyword", "vector", "bm25"),
        ("vector", "relationship", "vector", "bm25+graph"),
        ("vector", "comparison", "vector", "bm25+graph"),
        ("hybrid", "fact_lookup", "vector", None),
        ("hybrid", "keyword", "hybrid", None),
        ("hybrid", "relationship", "hybrid", "graph"),
        ("hybrid", "aggregation", "hybrid", "graph"),
        ("graph_hybrid", "relationship", "graph", None),
        ("graph_hybrid", "comparison", "graph_hybrid", None),
        ("graph_hybrid", "keyword", "hybrid", None),
    ],
)
def test_routing_table(built, query_type, used, build):
    has_bm25 = built in ("hybrid", "graph_hybrid")
    has_graph = built == "graph_hybrid"
    decision = route(query_type, has_bm25, has_graph)
    assert decision.mode == used
    if build is None:
        assert decision.recommendation is None
    else:
        assert decision.recommendation.index_to_build == build
        assert "Build" in decision.recommendation.message


def test_manual_mode_override_and_its_limits():
    assert route("fact_lookup", True, False, requested="hybrid").mode == "hybrid"
    with pytest.raises(RoutingError):
        route("fact_lookup", False, False, requested="graph")


# --------------------------------------------------------- self-correction


def hits(*scores: float) -> list[SearchHit]:
    return [
        SearchHit(chunk=Chunk(id=f"c{i}", document_id="d", owner_id="u", text=f"t{i}"), score=s)
        for i, s in enumerate(scores)
    ]


def test_relevance_mixes_top1_and_top3_mean():
    assert relevance_score(hits(0.9, 0.3, 0.0)) == pytest.approx((0.9 + 0.4) / 2)
    assert relevance_score([]) == 0.0


def test_retry_budget():
    assert needs_retry(0.01, attempt=0)
    assert not needs_retry(0.01, attempt=2)  # MAX_RETRIES = 2
    assert not needs_retry(0.9, attempt=0)


def test_grounding_scores_supported_claims():
    answer = Answer(
        text="Leave is 20 days [1]. Sick leave is 30 days [1].",
        citations=[Citation(number=1, chunk_id="c", document_id="d", text="Leave is 20 days.")],
    )
    llm = FakeLLM(
        data={
            "claims": [
                {"claim": "Leave is 20 days", "supported": True},
                {"claim": "Sick leave is 30 days", "supported": False},
            ]
        }
    )
    result = check_grounding(answer, llm)
    assert result.score == 0.5
    assert result.unsupported == ["Sick leave is 30 days"]
    assert not result.passed


# ----------------------------------------------------------- whole pipeline


class FixedRetriever(Retriever):
    """Returns canned hits; records the search queries it was given."""

    def __init__(self, mode, results):
        self.mode = mode
        self.results = results
        self.queries: list[str] = []

    def retrieve(self, question, owner_id, document_ids, k):
        self.queries.append(question)
        found = self.results(question) if callable(self.results) else self.results
        return RetrievalResult(hits=found)


def keep_order(question, candidates, top_n):
    return candidates[:top_n]


def scripted_llm(answers, grounding):
    """FakeLLM whose plain replies and grounding verdicts are consumed in order."""
    answers, grounding = iter(answers), iter(grounding)

    def data(messages):
        content = messages[0]["content"]
        if "Check an answer" in content:
            supported = next(grounding)
            return {"claims": [{"claim": "x", "supported": supported}]}
        if "Rewrite it" in content:
            return {"query": "annual leave entitlement days"}
        return {"query_type": "semantic"}

    return FakeLLM(reply=lambda _m: next(answers), data=data)


GOOD = hits(0.9, 0.8)
BAD = hits(0.01, 0.0)


def run(pipeline, question="How many leave days?", **kwargs):
    options = {"has_bm25": True, "has_graph": False, **kwargs}
    return pipeline.run(question, "u", ["d"], **options)


def test_happy_path_answers_with_citations_and_timings():
    retriever = FixedRetriever("vector", GOOD)
    llm = scripted_llm(["Twenty days [1]."], [True])
    state, meter = run(QueryPipeline({"vector": retriever}, llm, keep_order))
    assert state["answer"].text == "Twenty days [1]."
    assert state["routing"].mode == "vector"
    assert state["grounding_score"] == 1.0
    assert state["rewrites"] == []
    assert set(state["timings"]) == {
        "classify",
        "route",
        "retrieve",
        "rerank",
        "evaluate",
        "generate",
        "ground",
    }
    assert meter.calls == 2  # generate + grounding (rules classified the question)


def test_low_relevance_rewrites_then_answers():
    retriever = FixedRetriever("vector", lambda q: GOOD if "entitlement" in q else BAD)
    llm = scripted_llm(["Twenty days [1]."], [True])
    state, _ = run(QueryPipeline({"vector": retriever}, llm, keep_order))
    assert state["rewrites"] == ["annual leave entitlement days"]
    assert retriever.queries == ["How many leave days?", "annual leave entitlement days"]
    assert state["relevance_history"][0] < state["relevance_history"][1]
    assert not state["answer"].insufficient_evidence


def test_relevance_never_improves_so_it_refuses_after_max_retries():
    retriever = FixedRetriever("vector", BAD)
    llm = scripted_llm([], [])
    state, _ = run(QueryPipeline({"vector": retriever}, llm, keep_order))
    assert len(retriever.queries) == 3  # original + 2 rewrites
    assert state["answer"].text == INSUFFICIENT_EVIDENCE
    assert "relevance" in state["refused_reason"]


def test_failed_grounding_regenerates_once_in_strict_mode():
    llm = scripted_llm(["Thirty days [1].", "Twenty days [1]."], [False, True])
    state, _ = run(QueryPipeline({"vector": FixedRetriever("vector", GOOD)}, llm, keep_order))
    assert state["regenerated"] is True
    assert state["answer"].text == "Twenty days [1]."
    assert "STRICT MODE" in llm.calls[-2][0]["content"]  # the regenerate prompt


def test_grounding_failing_twice_refuses():
    llm = scripted_llm(["Thirty days [1].", "Still thirty [1]."], [False, False])
    state, _ = run(QueryPipeline({"vector": FixedRetriever("vector", GOOD)}, llm, keep_order))
    assert state["answer"].insufficient_evidence
    assert "unsupported" in state["refused_reason"]


def test_relationship_question_without_graph_uses_hybrid_and_recommends_graph():
    retrievers = {
        "vector": FixedRetriever("vector", GOOD),
        "hybrid": FixedRetriever("hybrid", GOOD),
    }
    llm = scripted_llm(["Payments [1]."], [True])
    state, _ = run(QueryPipeline(retrievers, llm, keep_order), "What depends on Auth?")
    assert state["routing"].ideal_mode == "graph"
    assert state["routing"].mode == "hybrid"
    assert state["routing"].recommendation.index_to_build == "graph"
