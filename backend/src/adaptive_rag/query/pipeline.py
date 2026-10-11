"""The adaptive query flow as a LangGraph state machine (PRD 7.5-7.7).

    classify -> route -> retrieve -> rerank -> evaluate -> generate
                            ^                                 |
                            |             answered? ----------+--- yes --> ground -> done
                            |                                 |              |
                            +---- rewrite <-------------------+ no           | unsupported
                                  (retries left)              |              v
                                          no retries left -> done    regenerate (strict) -> ground
                                          ("not enough evidence")    still unsupported -> refuse

The LLM, not the reranker, decides whether the evidence answers the question. The
reranker only sorts chunks: its absolute score is unreliable as a pass/fail gate
(measured: 0.003 for a chunk the LLM answered from, 0.98 for an unanswerable question).
`evaluate` still records the relevance score, as a signal for the "Why" panel.

Each node does one job and records its time; the state carries everything the
"Why did I get this answer?" panel shows.
"""

import time
from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from adaptive_rag.config import settings
from adaptive_rag.llm.base import LLM, LLMError
from adaptive_rag.llm.meter import MeteredLLM
from adaptive_rag.query.answer import INSUFFICIENT_EVIDENCE, generate_answer
from adaptive_rag.query.classifier import classify
from adaptive_rag.query.correction import (
    check_grounding,
    needs_retry,
    relevance_score,
    rewrite_query,
)
from adaptive_rag.query.router import route
from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.schemas import (
    Answer,
    Classification,
    GraphPath,
    Mode,
    RoutingDecision,
    SearchHit,
)

Reranker = Callable[[str, list[SearchHit], int], list[SearchHit]]


class QueryState(TypedDict, total=False):
    # input
    question: str
    owner_id: str
    document_ids: list[str]
    has_bm25: bool
    has_graph: bool
    requested_mode: Mode | None
    # decisions
    classification: Classification
    routing: RoutingDecision
    search_query: str
    rewrites: list[str]
    attempt: int
    rewrite_repeated: bool
    # evidence
    candidates: list[SearchHit]
    reranked: list[SearchHit]
    graph_paths: list[GraphPath]
    relevance: float
    relevance_history: list[float]
    # output
    answer: Answer
    grounding_score: float | None
    grounding_passed: bool
    unsupported_claims: list[str]
    regenerated: bool
    refused_reason: str
    timings: dict[str, float]


class QueryPipeline:
    """Builds the graph once; `run` answers one question."""

    def __init__(self, retrievers: dict[Mode, Retriever], llm: LLM, reranker: Reranker) -> None:
        self._retrievers = retrievers
        self._llm = llm
        self._rerank = reranker

    def run(
        self,
        question: str,
        owner_id: str,
        document_ids: list[str],
        has_bm25: bool,
        has_graph: bool,
        requested_mode: Mode | None = None,
    ) -> tuple[QueryState, MeteredLLM]:
        """Answer one question; returns the final state and the query's LLM usage."""
        meter = MeteredLLM(self._llm)
        graph = self._build(meter)
        state = graph.invoke(
            {
                "question": question,
                "owner_id": owner_id,
                "document_ids": document_ids,
                "has_bm25": has_bm25,
                "has_graph": has_graph,
                "requested_mode": requested_mode,
                "search_query": question,
                "rewrites": [],
                "attempt": 0,
                "relevance_history": [],
                "graph_paths": [],
                "regenerated": False,
                "grounding_score": None,
                "unsupported_claims": [],
                "refused_reason": "",
                "timings": {},
            }
        )
        return state, meter

    def _build(self, llm: MeteredLLM):  # type: ignore[no-untyped-def]
        def timed(name: str, step: Callable[[QueryState], dict[str, Any]]):  # type: ignore[no-untyped-def]
            def node(state: QueryState) -> dict[str, Any]:
                started = time.perf_counter()
                update = step(state)
                timings = dict(state["timings"])
                elapsed = round((time.perf_counter() - started) * 1000, 1)
                timings[name] = round(timings.get(name, 0.0) + elapsed, 1)  # retries add up
                return {**update, "timings": timings}

            return node

        def classify_step(state: QueryState) -> dict[str, Any]:
            return {"classification": classify(state["question"], llm)}

        def route_step(state: QueryState) -> dict[str, Any]:
            decision = route(
                state["classification"].query_type,
                state["has_bm25"],
                state["has_graph"],
                state["requested_mode"],
            )
            return {"routing": decision}

        def retrieve_step(state: QueryState) -> dict[str, Any]:
            retriever = self._retrievers[state["routing"].mode]
            result = retriever.retrieve(
                state["search_query"],
                state["owner_id"],
                state["document_ids"],
                settings.candidate_k,
            )
            paths = result.graph_paths or state["graph_paths"]
            return {"candidates": result.hits, "graph_paths": paths}

        def rerank_step(state: QueryState) -> dict[str, Any]:
            # Rerank against the original question: that's what the answer must address
            return {
                "reranked": self._rerank(state["question"], state["candidates"], settings.top_k)
            }

        def evaluate_step(state: QueryState) -> dict[str, Any]:
            score = relevance_score(state["reranked"])
            return {"relevance": score, "relevance_history": [*state["relevance_history"], score]}

        def rewrite_step(state: QueryState) -> dict[str, Any]:
            rewritten = rewrite_query(state["question"], state["rewrites"], llm)
            tried = {state["question"].lower(), *(r.lower() for r in state["rewrites"])}
            if rewritten.lower() in tried:  # nothing new to search for: stop retrying
                return {"attempt": settings.max_retries, "rewrite_repeated": True}
            return {
                "search_query": rewritten,
                "rewrites": [*state["rewrites"], rewritten],
                "attempt": state["attempt"] + 1,
                "rewrite_repeated": False,
            }

        def after_rewrite(state: QueryState) -> str:
            return "done" if state.get("rewrite_repeated") else "retrieve"

        def generate_step(state: QueryState) -> dict[str, Any]:
            answer = generate_answer(state["question"], state["reranked"], llm)
            reason = "the retrieved evidence does not contain the answer"
            return {
                "answer": answer,
                "refused_reason": reason if answer.insufficient_evidence else "",
            }

        def ground_step(state: QueryState) -> dict[str, Any]:
            if not settings.grounding_enabled:
                return {"grounding_score": None}
            try:
                result = check_grounding(state["answer"], llm)
            except LLMError:  # the answer stands, shown as unchecked rather than lost
                return {"grounding_score": None}
            return {
                "grounding_score": result.score,
                "grounding_passed": result.passed,
                "unsupported_claims": result.unsupported,
            }

        def regenerate_step(state: QueryState) -> dict[str, Any]:
            answer = generate_answer(state["question"], state["reranked"], llm, strict=True)
            return {"answer": answer, "regenerated": True}

        def refuse_step(_state: QueryState) -> dict[str, Any]:
            return {
                "answer": Answer(text=INSUFFICIENT_EVIDENCE, insufficient_evidence=True),
                "refused_reason": "answer still had unsupported claims after a strict retry",
            }

        def after_generate(state: QueryState) -> str:
            if not state["answer"].insufficient_evidence:
                return "ground"
            # The model could not answer from this evidence: search again with a rewrite
            return "rewrite" if needs_retry(True, state["attempt"]) else "done"

        def after_ground(state: QueryState) -> str:
            if state.get("grounding_passed", True):  # unchecked answers are shown as such
                return "done"
            return "refuse" if state["regenerated"] else "regenerate"

        graph = StateGraph(QueryState)
        for name, step in [
            ("classify", classify_step),
            ("route", route_step),
            ("retrieve", retrieve_step),
            ("rerank", rerank_step),
            ("evaluate", evaluate_step),
            ("rewrite", rewrite_step),
            ("generate", generate_step),
            ("ground", ground_step),
            ("regenerate", regenerate_step),
            ("refuse", refuse_step),
        ]:
            graph.add_node(name, timed(name, step))
        graph.add_edge(START, "classify")
        graph.add_edge("classify", "route")
        graph.add_edge("route", "retrieve")
        graph.add_edge("retrieve", "rerank")
        graph.add_edge("rerank", "evaluate")
        graph.add_edge("evaluate", "generate")
        graph.add_conditional_edges(
            "generate", after_generate, {"ground": "ground", "rewrite": "rewrite", "done": END}
        )
        graph.add_conditional_edges("rewrite", after_rewrite, {"retrieve": "retrieve", "done": END})
        graph.add_conditional_edges(
            "ground", after_ground, {"done": END, "regenerate": "regenerate", "refuse": "refuse"}
        )
        graph.add_edge("regenerate", "ground")
        graph.add_edge("refuse", END)
        return graph.compile()
