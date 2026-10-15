"""Tests for precision and relative recall measured on a live question."""

from adaptive_rag.llm.base import LLMError
from adaptive_rag.query.pipeline import QueryPipeline
from adaptive_rag.query.quality import measure_quality
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


def test_pipeline_measures_the_used_mode_against_the_other_modes():
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
    assert "measure" in state["timings"]


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
