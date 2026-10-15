"""Tests for classification, routing, self-correction, and the LangGraph query flow."""

import pytest

from adaptive_rag.llm.base import LLMError
from adaptive_rag.query.answer import INSUFFICIENT_EVIDENCE
from adaptive_rag.query.classifier import classify, classify_by_rules
from adaptive_rag.query.correction import check_grounding, needs_retry, relevance_score
from adaptive_rag.query.pipeline import QueryPipeline
from adaptive_rag.query.router import RoutingError, available_modes, route
from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.schemas import MODE_INDEXES, Answer, Chunk, Citation, RetrievalResult, SearchHit
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
        ("vector", "relationship", "vector", "graph"),
        ("vector", "comparison", "vector", "bm25+graph"),
        ("keyword", "fact_lookup", "keyword", "vector"),
        ("keyword", "keyword", "keyword", "vector"),
        ("keyword", "relationship", "keyword", "graph"),
        ("graph", "relationship", "graph", None),
        ("graph", "fact_lookup", "graph", "vector"),
        ("graph", "comparison", "graph", "vector+bm25"),
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
    decision = route(query_type, MODE_INDEXES[built])
    assert decision.mode == used
    if build is None:
        assert decision.recommendation is None
    else:
        assert decision.recommendation.index_to_build == build
        assert "Build" in decision.recommendation.message


def test_manual_mode_override_and_its_limits():
    assert route("fact_lookup", {"vector", "bm25"}, requested="hybrid").mode == "hybrid"
    with pytest.raises(RoutingError):
        route("fact_lookup", {"vector"}, requested="graph")


def test_documents_sharing_no_index_cannot_be_searched_together():
    with pytest.raises(RoutingError, match="share no search index"):
        route("fact_lookup", set())


def test_available_modes_follow_the_built_indexes():
    assert available_modes({"bm25"}) == {"keyword"}
    assert available_modes({"vector", "bm25"}) == {"vector", "keyword", "hybrid"}
    assert available_modes({"graph"}) == {"graph"}
    assert available_modes(MODE_INDEXES["graph_hybrid"]) == set(MODE_INDEXES)


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
    assert needs_retry(True, attempt=0)
    assert not needs_retry(True, attempt=2)  # MAX_RETRIES = 2
    assert not needs_retry(False, attempt=0)  # the model answered: nothing to retry


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
    assert result.passed  # half supported: shown, with the doubtful claim flagged

    llm.data["claims"].append({"claim": "Leave resets in March", "supported": False})
    assert not check_grounding(answer, llm).passed  # 1 of 3: mostly unsupported


def test_answer_without_citations_is_not_grounded():
    """Nothing cited means nothing can be checked, and no LLM call is spent finding out."""
    llm = FakeLLM()
    result = check_grounding(Answer(text="Leave is 20 days."), llm)
    assert result.score == 0.0 and not result.passed
    assert llm.calls == []


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
    options = {"indexes": {"vector", "bm25"}, **kwargs}
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
        "measure",
    }
    assert meter.calls == 3  # generate + grounding + relevance judge (rules classified it)


def test_low_reranker_score_does_not_block_the_answer():
    """The reranker only sorts: a weak score still goes to the LLM, which can reason."""
    retriever = FixedRetriever("vector", BAD)
    llm = scripted_llm(["No, sick leave is 10 days [1]."], [True])
    state, meter = run(QueryPipeline({"vector": retriever}, llm, keep_order))
    assert state["answer"].text == "No, sick leave is 10 days [1]."
    assert state["relevance"] < 0.05  # recorded for the Why panel, not used as a gate
    assert state["rewrites"] == []
    assert meter.calls == 3  # answer + grounding + relevance judge, no rewrite


def test_model_finding_no_answer_rewrites_then_answers():
    """Self-correction starts when the LLM says the evidence has no answer."""
    retriever = FixedRetriever("vector", GOOD)
    llm = scripted_llm(["NO_ANSWER", "Twenty days [1]."], [True])
    state, _ = run(QueryPipeline({"vector": retriever}, llm, keep_order))
    assert state["rewrites"] == ["annual leave entitlement days"]
    assert retriever.queries == ["How many leave days?", "annual leave entitlement days"]
    assert state["answer"].text == "Twenty days [1]."
    assert state["refused_reason"] == ""


def test_a_repeated_rewrite_stops_the_retries():
    """Searching the same words again would find the same chunks, so it stops early."""
    retriever = FixedRetriever("vector", GOOD)
    llm = scripted_llm(["NO_ANSWER", "NO_ANSWER"], [])  # the rewriter always says the same
    state, meter = run(QueryPipeline({"vector": retriever}, llm, keep_order))
    assert retriever.queries == ["How many leave days?", "annual leave entitlement days"]
    assert state["rewrites"] == ["annual leave entitlement days"]
    assert state["answer"].text == INSUFFICIENT_EVIDENCE
    assert meter.calls == 5  # 2 answers + 2 rewrites + relevance judge, not a third search


def test_model_never_finds_an_answer_so_it_refuses_after_max_retries():
    retriever = FixedRetriever("vector", GOOD)
    rewrites = iter(["annual leave entitlement", "paid time off allowance"])

    def data(messages):
        return {"query": next(rewrites)} if "Rewrite it" in messages[0]["content"] else {}

    llm = FakeLLM(reply="NO_ANSWER", data=data)
    state, _ = run(QueryPipeline({"vector": retriever}, llm, keep_order))
    assert len(retriever.queries) == 3  # original + 2 different rewrites
    assert state["answer"].text == INSUFFICIENT_EVIDENCE
    assert "does not contain the answer" in state["refused_reason"]
    assert state["grounding_score"] is None  # nothing to check on a refusal


def test_one_doubtful_claim_does_not_discard_a_mostly_supported_answer():
    """The checker is noisy, so a single flagged claim is reported, not fatal."""

    def data(messages):
        if "Check an answer" in messages[0]["content"]:
            return {
                "claims": [
                    {"claim": "Sick leave is 10 days", "supported": True},
                    {"claim": "12 is more than 10", "supported": True},
                    {"claim": "12 days is not acceptable", "supported": False},
                ]
            }
        return {"query_type": "semantic"}

    llm = FakeLLM("No, sick leave is 10 days [1].", data=data)
    state, _ = run(QueryPipeline({"vector": FixedRetriever("vector", GOOD)}, llm, keep_order))
    assert state["answer"].text == "No, sick leave is 10 days [1]."
    assert state["regenerated"] is False
    assert state["grounding_score"] == pytest.approx(0.667, abs=0.001)
    assert state["unsupported_claims"] == ["12 days is not acceptable"]


def test_failed_grounding_regenerates_once_in_strict_mode():
    llm = scripted_llm(["Thirty days [1].", "Twenty days [1]."], [False, True])
    state, _ = run(QueryPipeline({"vector": FixedRetriever("vector", GOOD)}, llm, keep_order))
    assert state["regenerated"] is True
    assert state["answer"].text == "Twenty days [1]."
    # last three calls: regenerate, its grounding check, the relevance judge
    assert "STRICT MODE" in llm.calls[-3][0]["content"]


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


# ------------------------------------------------------------ reasoning effort


def test_every_call_uses_its_configured_reasoning_effort(monkeypatch):
    """Reasoning is off by default (measured: same accuracy, ~10x cheaper) and set per task."""
    from adaptive_rag.ingest.extractor import extract_graph
    from adaptive_rag.ingest.sampler import analyze_sample
    from adaptive_rag.query.answer import generate_answer
    from adaptive_rag.query.correction import rewrite_query
    from adaptive_rag.schemas import DocumentProfile, Section

    chunk = Chunk(id="c1", document_id="d", owner_id="u", text="Payments depends on Auth.")
    section = Section(id="0", title="Overview", text="Payments depends on Auth.")
    structured = FakeLLM(data={"entities": [], "relationships": [], "query": "q", "claims": []})
    extract_graph([chunk], structured)
    analyze_sample([section], DocumentProfile(), structured)
    rewrite_query("leave?", [], structured)
    classify("Tell me about our approach to data", structured)
    assert structured.efforts == [None, None, None, None]

    answering = FakeLLM("Twenty days [1].", data={"claims": []})
    answer = generate_answer("How many leave days?", hits(0.9), answering)
    check_grounding(answer, answering)
    assert answering.efforts == [None, None]

    monkeypatch.setattr("adaptive_rag.query.answer.settings.answer_reasoning_effort", "high")
    generate_answer("How many leave days?", hits(0.9), answering)
    assert answering.efforts[-1] == "high"


def test_failed_grounding_call_keeps_the_answer_unchecked():
    """If the checker itself fails, the user still gets the answer, marked as not checked."""

    class GroundingDown(FakeLLM):
        def complete_json(self, messages, schema, **kwargs):
            if "Check an answer" in messages[0]["content"]:
                raise LLMError("checker unavailable")
            return super().complete_json(messages, schema, **kwargs)

    llm = GroundingDown("Twenty days [1].")
    state, _ = run(QueryPipeline({"vector": FixedRetriever("vector", GOOD)}, llm, keep_order))
    assert state["answer"].text == "Twenty days [1]."
    assert state["grounding_score"] is None
