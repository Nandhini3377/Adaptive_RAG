"""Tests for precision and relative recall measured on a live question."""

from adaptive_rag.llm.base import LLMError
from adaptive_rag.query.pipeline import QueryPipeline
from adaptive_rag.query.quality import measure_quality, select_mode
from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.schemas import Chunk, RetrievalResult, SearchHit
from tests.conftest import FakeLLM


def hit(chunk_id: str) -> SearchHit:
    chunk = Chunk(id=chunk_id, document_id="d", owner_id="u", text=f"text of {chunk_id}")
    return SearchHit(chunk=chunk, score=0.5)


class FixedRetriever(Retriever):
    def __init__(self, mode, chunk_ids):
        self.mode = mode
        self.chunk_ids = chunk_ids
        self.queries: list[str] = []

    def retrieve(self, question, owner_id, document_ids, k):
        self.queries.append(question)
        return RetrievalResult(hits=[hit(c) for c in self.chunk_ids])


class BrokenRetriever(Retriever):
    mode = "graph"

    def retrieve(self, question, owner_id, document_ids, k):
        raise RuntimeError("graph database is down")


def judge(*relevant_numbers: int) -> FakeLLM:
    return FakeLLM(data={"relevant": list(relevant_numbers)})


def measure(used, others, llm, rerank=None):
    return measure_quality(
        "q?",
        "search words",
        [hit(c) for c in used],
        others,
        "u",
        ["d"],
        llm,
        used_mode="vector",
        rerank=rerank,
    )


def test_precision_is_the_relevant_share_of_the_chunks_used():
    # Pool order: a, b, c, d (used first). The judge marks a and c.
    quality = measure(["a", "b", "c", "d"], {}, judge(1, 3))
    assert quality.precision == 0.5
    assert (quality.relevant_used, quality.used) == (2, 4)


def test_relative_recall_counts_relevant_chunks_other_modes_found():
    # Used: a, b. Hybrid also finds b (a duplicate) and x, y. Pool: a, b, x, y.
    hybrid = FixedRetriever("hybrid", ["b", "x", "y"])
    quality = measure(["a", "b"], {"hybrid": hybrid}, judge(1, 3, 4))  # a, x, y are relevant
    assert quality.pool_size == 4  # b is pooled once
    assert quality.precision == 0.5  # a of [a, b]
    assert quality.relative_recall == 0.333  # found a, missed x and y
    assert quality.compared_modes == ["hybrid"]
    assert hybrid.queries == ["search words"]  # the same search the answer used


def test_finding_everything_the_other_modes_found_is_full_recall():
    quality = measure(["a", "b"], {"hybrid": FixedRetriever("hybrid", ["a", "z"])}, judge(1, 2))
    assert quality.relative_recall == 1.0


def test_no_other_mode_means_recall_is_not_measured():
    """With only one index there is no pool to compare against: 100% would be misleading."""
    quality = measure(["a", "b"], {}, judge(1))
    assert quality.precision == 0.5
    assert quality.relative_recall is None


def test_nothing_relevant_anywhere_leaves_recall_undefined():
    quality = measure(["a"], {"hybrid": FixedRetriever("hybrid", ["x"])}, judge())
    assert quality.precision == 0.0
    assert quality.relative_recall is None


def test_a_failing_mode_is_left_out_of_the_pool():
    others = {"graph": BrokenRetriever(), "hybrid": FixedRetriever("hybrid", ["x"])}
    quality = measure(["a"], others, judge(1, 2))
    assert quality.compared_modes == ["hybrid"]
    assert quality.relative_recall == 0.5


def test_numbers_the_judge_invents_are_ignored():
    quality = measure(["a", "b"], {}, judge(0, 2, 9))
    assert quality.relevant_used == 1


def test_every_mode_gets_its_own_precision_and_recall():
    # Used (vector): a, b. Hybrid: b, x, y. Pool: a, b, x, y; relevant: a, x, y.
    hybrid = FixedRetriever("hybrid", ["b", "x", "y"])
    quality = measure(["a", "b"], {"hybrid": hybrid}, judge(1, 3, 4))
    used, other = quality.modes
    assert (used.mode, used.used, used.relevant, used.precision, used.recall) == (
        "vector",
        True,
        1,
        0.5,
        0.333,
    )
    assert (other.mode, other.used, other.relevant, other.precision, other.recall) == (
        "hybrid",
        False,
        2,
        0.667,
        0.667,
    )


def test_a_mode_that_finds_nothing_has_no_precision():
    quality = measure(["a"], {"graph": FixedRetriever("graph", [])}, judge(1))
    graph = quality.modes[1]
    assert (graph.found, graph.precision, graph.recall) == (0, None, 0.0)


def test_other_modes_are_reranked_against_the_question_like_the_used_one():
    seen = []

    def reverse(question, hits, top_n):
        seen.append((question, len(hits), top_n))
        return list(reversed(hits))[:top_n]

    hybrid = FixedRetriever("hybrid", ["x", "y"])
    quality = measure(["a"], {"hybrid": hybrid}, judge(2), rerank=reverse)
    assert seen == [("q?", 2, 5)]  # the original question, not the search words
    assert quality.modes[1].relevant == 1  # pool: a, y, x; the judge marks y


def test_no_chunks_means_nothing_to_measure():
    llm = judge(1)
    assert measure([], {}, llm) is None
    assert llm.calls == []


# ------------------------------------------------------------ in the pipeline


def keep_order(question, candidates, top_n):
    return candidates[:top_n]


def pipeline_llm(judge_error: bool = False) -> FakeLLM:
    class Scripted(FakeLLM):
        def complete_json(self, messages, schema, **kwargs):
            if judge_error and "numbered passages" in messages[0]["content"]:
                raise LLMError("judge unavailable")
            return super().complete_json(messages, schema, **kwargs)

    def data(messages):
        content = messages[0]["content"]
        if "numbered passages" in content:
            return {"relevant": [1, 3]}
        if "Check an answer" in content:
            return {"claims": [{"claim": "x", "supported": True}]}
        return {}

    return Scripted("Twenty days [1].", data=data)


def test_pipeline_measures_the_used_mode_against_the_other_modes(monkeypatch):
    monkeypatch.setattr("adaptive_rag.query.pipeline.settings.compare_modes", "always")
    retrievers = {
        "vector": FixedRetriever("vector", ["a", "b"]),
        "hybrid": FixedRetriever("hybrid", ["b", "x"]),
    }
    pipeline = QueryPipeline(retrievers, pipeline_llm(), keep_order)
    state, _ = pipeline.run("How many leave days?", "u", ["d"], indexes={"vector", "bm25"})
    assert state["routing"].mode == "vector"
    quality = state["quality"]  # pool: a, b, x; relevant: a and x
    assert quality.precision == 0.5
    assert quality.relative_recall == 0.5
    assert quality.compared_modes == ["hybrid"]
    assert [m.mode for m in quality.modes] == ["vector", "hybrid"]
    assert "select" in state["timings"]


def test_a_failed_judge_call_keeps_the_answer(monkeypatch):
    pipeline = QueryPipeline(
        {"vector": FixedRetriever("vector", ["a"])}, pipeline_llm(judge_error=True), keep_order
    )
    state, _ = pipeline.run("How many leave days?", "u", ["d"], indexes={"vector"})
    assert state["answer"].text == "Twenty days [1]."
    assert state["quality"] is None


def test_measuring_can_be_switched_off(monkeypatch):
    monkeypatch.setattr("adaptive_rag.query.pipeline.settings.retrieval_quality_enabled", False)
    llm = pipeline_llm()
    pipeline = QueryPipeline({"vector": FixedRetriever("vector", ["a"])}, llm, keep_order)
    state, meter = pipeline.run("How many leave days?", "u", ["d"], indexes={"vector"})
    assert state["quality"] is None
    assert meter.calls == 2  # answer + grounding only


# ------------------------------------------------------- choosing the evidence


def select(routed_hits, others, llm, switch=True):
    return select_mode(
        "q?",
        "search words",
        "hybrid",
        [hit(c) for c in routed_hits],
        others,
        "u",
        ["d"],
        llm,
        switch=switch,
    )


def test_the_mode_with_more_relevant_chunks_is_chosen():
    # Hybrid (router): a, b. Graph: x, y. Relevant: x, y.
    chosen = select(["a", "b"], {"graph": FixedRetriever("graph", ["x", "y"])}, judge(3, 4))
    assert chosen.mode == "graph"
    assert [h.chunk.id for h in chosen.hits] == ["x", "y"]
    assert chosen.quality.modes[0].mode == "graph" and chosen.quality.modes[0].used


def test_on_equal_evidence_fewer_irrelevant_chunks_wins():
    """The live case: hybrid and keyword both found the 2 relevant chunks; keyword sent no noise."""
    keyword = FixedRetriever("keyword", ["a", "b"])
    chosen = select(["a", "b", "c", "d", "e"], {"keyword": keyword}, judge(1, 2))
    assert chosen.mode == "keyword"
    assert (chosen.quality.precision, chosen.quality.relative_recall) == (1.0, 1.0)


def test_a_full_tie_keeps_the_routers_pick():
    chosen = select(["a", "b"], {"vector": FixedRetriever("vector", ["a", "b"])}, judge(1))
    assert chosen.mode == "hybrid"


def test_nothing_relevant_keeps_the_routers_pick():
    chosen = select(["a"], {"vector": FixedRetriever("vector", ["x"])}, judge())
    assert chosen.mode == "hybrid"


def test_a_mode_chosen_by_hand_is_never_switched():
    chosen = select(["a"], {"graph": FixedRetriever("graph", ["x"])}, judge(2), switch=False)
    assert chosen.mode == "hybrid"
    assert chosen.quality.modes[1].relevant == 1  # still measured


def test_the_answer_is_written_from_the_chosen_modes_chunks(monkeypatch):
    monkeypatch.setattr("adaptive_rag.query.pipeline.settings.compare_modes", "always")
    retrievers = {
        "vector": FixedRetriever("vector", ["a", "b"]),
        "keyword": FixedRetriever("keyword", ["a"]),
    }
    llm = pipeline_llm()  # the judge marks passages 1 and 3 of the pool a, b: only a exists
    state, _ = QueryPipeline(retrievers, llm, keep_order).run(
        "How many leave days?", "u", ["d"], indexes={"vector", "bm25"}
    )
    assert state["routing"].mode == "vector"  # the router's prediction
    assert state["mode_used"] == "keyword"  # same relevant chunk, no noise
    answer_prompt = next(c for c in llm.calls if c[0]["role"] == "system")[1]["content"]
    assert "text of a" in answer_prompt and "text of b" not in answer_prompt


# --------------------------------------------- compare only when needed (default)


def test_a_simple_question_uses_the_router_pick_without_comparing():
    """No search with other modes; the router's pick is still measured on its own."""
    hybrid = FixedRetriever("hybrid", ["b"])
    retrievers = {"vector": FixedRetriever("vector", ["a"]), "hybrid": hybrid}
    state, meter = QueryPipeline(retrievers, pipeline_llm(), keep_order).run(
        "How many leave days?", "u", ["d"], indexes={"vector", "bm25"}
    )
    assert state["mode_used"] == "vector"
    assert state["quality"].recall_scope == "candidates"
    assert "simple question" in state["comparison_reason"]
    assert hybrid.queries == []  # the other mode never searched
    assert meter.calls == 3  # judge (one mode's own chunks) + answer + grounding


def test_a_multi_hop_question_uses_the_router_pick_by_default():
    """Measured: the router was already best on multi-hop questions, so no comparison."""
    vector = FixedRetriever("vector", ["a"])
    retrievers = {"vector": vector, "hybrid": FixedRetriever("hybrid", ["b"])}
    state, meter = QueryPipeline(retrievers, pipeline_llm(), keep_order).run(
        "Which teams own services affected by the payment migration?",
        "u",
        ["d"],
        indexes={"vector", "bm25"},
    )
    assert state["classification"].query_type == "multi_hop"
    assert state["mode_used"] == "hybrid"  # no graph built: the router's fallback pick
    assert vector.queries == []  # not compared
    assert state["quality"].recall_scope == "candidates" and meter.calls == 3


def test_question_types_can_be_set_to_compare_every_mode(monkeypatch):
    monkeypatch.setattr("adaptive_rag.query.pipeline.settings.compare_modes_for", ["multi_hop"])
    retrievers = {
        "vector": FixedRetriever("vector", ["a"]),
        "hybrid": FixedRetriever("hybrid", ["b", "x"]),
    }
    state, _ = QueryPipeline(retrievers, pipeline_llm(), keep_order).run(
        "Which teams own services affected by the payment migration?",
        "u",
        ["d"],
        indexes={"vector", "bm25"},
    )
    assert state["classification"].query_type == "multi_hop"
    assert state["quality"] is not None
    assert "multi hop" in state["comparison_reason"]


def test_no_answer_from_the_router_pick_tries_every_mode_before_rewriting():
    replies = iter(["NO_ANSWER", "Twenty days [1]."])

    def data(messages):
        content = messages[0]["content"]
        if "numbered passages" in content:
            return {"relevant": [2]}  # only the keyword chunk helps
        if "Check an answer" in content:
            return {"claims": [{"claim": "x", "supported": True}]}
        return {}

    retrievers = {
        "vector": FixedRetriever("vector", ["a"]),
        "keyword": FixedRetriever("keyword", ["k"]),
    }
    llm = FakeLLM(reply=lambda _m: next(replies), data=data)
    state, _ = QueryPipeline(retrievers, llm, keep_order).run(
        "How many leave days?", "u", ["d"], indexes={"vector", "bm25"}
    )
    assert state["weak"] and state["compared"]
    assert state["mode_used"] == "keyword"
    assert state["rewrites"] == []  # the other mode answered, no rewrite needed
    assert state["answer"].text == "Twenty days [1]."
    assert "found no answer" in state["comparison_reason"]


def test_one_mode_is_measured_against_everything_it_fetched():
    """Precision over the top k; recall = relevant in the top k / relevant fetched."""
    from adaptive_rag.query.quality import measure_single

    used = [hit("a"), hit("b")]
    candidates = [hit("a"), hit("b"), hit("c"), hit("d")]
    llm = FakeLLM(data={"relevant": [1, 3]})  # pool order a, b, c, d: a and c help
    quality = measure_single("q", "vector", used, candidates, llm)
    assert quality.precision == 0.5  # a of a, b
    assert quality.relative_recall == 0.5  # a of a, c: ranking dropped c
    assert (quality.pool_size, quality.relevant_in_pool) == (4, 2)
    assert quality.recall_scope == "candidates" and quality.compared_modes == []
