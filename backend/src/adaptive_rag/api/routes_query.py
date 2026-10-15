"""POST /query: run the adaptive pipeline over the user's ready documents."""

import logging
import time

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from adaptive_rag import services
from adaptive_rag.api.deps import SessionDep, UserDep
from adaptive_rag.api.limits import require_query_quota
from adaptive_rag.llm.base import LLMError
from adaptive_rag.models.reranker import rerank
from adaptive_rag.query.pipeline import QueryPipeline
from adaptive_rag.query.quality import RetrievalQuality
from adaptive_rag.query.router import RoutingError, available_modes
from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.retrieval.graph import GraphRetriever
from adaptive_rag.retrieval.graph_hybrid import GraphHybridRetriever
from adaptive_rag.retrieval.hybrid import HybridRetriever
from adaptive_rag.retrieval.keyword import KeywordRetriever
from adaptive_rag.retrieval.vector import VectorRetriever
from adaptive_rag.schemas import Citation, GraphPath, Index, Mode, Recommendation
from adaptive_rag.store import db

log = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


class QueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] | None = None  # None = all of the user's ready documents
    mode: Mode | None = None  # manual override (FR27)


class Scores(BaseModel):
    relevance: float
    relevance_history: list[float]
    grounding: float | None
    unsupported_claims: list[str] = []  # claims the checker could not find in the evidence


class QueryOut(BaseModel):
    query_id: str
    answer: str
    citations: list[Citation]
    insufficient_evidence: bool
    query_type: str
    classified_by: str
    mode: str  # the mode the answer was written from (best measured evidence)
    router_mode: str  # the router's prediction from the question type
    ideal_mode: str
    routing_reason: str
    recommendation: Recommendation | None
    recommendation_document_ids: list[str]
    rewrites: list[str]
    graph_paths: list[GraphPath]
    scores: Scores
    quality: RetrievalQuality | None  # precision and relative recall; None when not measured
    regenerated: bool
    refused_reason: str
    documents: dict[str, str]  # id -> filename, for showing evidence sources
    timings: dict[str, float]
    latency_ms: float
    tokens: int
    reasoning_tokens: int
    llm_calls: int
    cost_inr: float


@router.post("/query")
def query(body: QueryIn, user: UserDep, session: SessionDep) -> QueryOut:
    started = time.perf_counter()
    require_query_quota(session, user.id)
    documents = _ready_documents(session, user.id, body.document_ids)
    graph_up = services.graph_store() is not None
    indexes = frozenset.intersection(*(document_indexes(d, graph_up) for d in documents))

    pipeline = QueryPipeline(retrievers_for(indexes), services.llm(), rerank)
    try:
        state, meter = pipeline.run(
            body.question,
            user.id,
            [d.id for d in documents],
            indexes=indexes,
            requested_mode=body.mode,
        )
    except RoutingError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    except LLMError as error:  # the model was unreachable or could not finish an answer
        log.warning("Query failed for user %s: %s", user.id, error)  # details stay in the log
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The language model failed to answer. Please try again in a moment.",
        ) from error

    answer, routing, mode_used = state["answer"], state["routing"], state["mode_used"]
    recommendation_ids = _missing_index(documents, routing.recommendation)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    record = db.QueryRecord(
        owner_id=user.id,
        document_ids=[d.id for d in documents],
        query=body.question,
        query_type=state["classification"].query_type,
        ideal_mode=routing.ideal_mode,
        mode_used=mode_used,
        recommendation=routing.recommendation.model_dump() if routing.recommendation else None,
        routing_reason=routing.reason,
        rewritten_queries=state["rewrites"],
        answer=answer.text,
        stage_timings=state["timings"],
        latency_ms=latency_ms,
        tokens=meter.tokens,
        cost_inr=meter.cost_inr,
    )
    session.add(record)
    session.flush()
    session.add(
        db.Evaluation(
            query_id=record.id,
            retrieval_score=state["relevance"],
            faithfulness_score=state["grounding_score"],
            retry_count=len(state["rewrites"]),
        )
    )
    return QueryOut(
        query_id=record.id,
        answer=answer.text,
        citations=answer.citations,
        insufficient_evidence=answer.insufficient_evidence,
        query_type=state["classification"].query_type,
        classified_by=state["classification"].source,
        mode=mode_used,
        router_mode=routing.mode,
        ideal_mode=routing.ideal_mode,
        routing_reason=routing.reason,
        recommendation=routing.recommendation,
        recommendation_document_ids=recommendation_ids,
        rewrites=state["rewrites"],
        graph_paths=state["graph_paths"],
        scores=Scores(
            relevance=state["relevance"],
            relevance_history=state["relevance_history"],
            grounding=state["grounding_score"],
            unsupported_claims=state["unsupported_claims"],
        ),
        quality=state["quality"],
        regenerated=state["regenerated"],
        refused_reason=state["refused_reason"],
        documents={d.id: d.filename for d in documents},
        timings=state["timings"],
        latency_ms=latency_ms,
        tokens=meter.tokens,
        reasoning_tokens=meter.reasoning_tokens,
        llm_calls=meter.calls,
        cost_inr=round(meter.cost_inr, 4),
    )


def document_indexes(document: db.Document, graph_up: bool) -> frozenset[Index]:
    """The indexes one document can be searched with right now."""
    built: set[Index] = set()
    if document.has_vector:
        built.add("vector")
    if document.has_bm25:
        built.add("bm25")
    if graph_up and document.graph_status == "ready":
        built.add("graph")
    return frozenset(built)


def retrievers_for(indexes: set[Index] | frozenset[Index]) -> dict[Mode, Retriever]:
    """Only the retrievers whose indexes exist (the router never picks others)."""
    allowed = available_modes(indexes)
    vectors, bm25 = services.vector_store(), services.bm25_store()
    hybrid = HybridRetriever(vectors, bm25)
    built: dict[Mode, Retriever] = {
        "vector": VectorRetriever(vectors),
        "keyword": KeywordRetriever(bm25),
        "hybrid": hybrid,
    }
    graph_store = services.graph_store() if "graph" in indexes else None
    if graph_store is not None:
        graph = GraphRetriever(graph_store)
        built["graph"] = graph
        built["graph_hybrid"] = GraphHybridRetriever(graph, hybrid)
    return {mode: retriever for mode, retriever in built.items() if mode in allowed}


def _missing_index(
    documents: list[db.Document], recommendation: Recommendation | None
) -> list[str]:
    """Which of the searched documents the recommended indexes would be built for."""
    if recommendation is None:
        return []
    needed = set(recommendation.index_to_build.split("+"))
    graph_up = services.graph_store() is not None
    return [d.id for d in documents if needed - document_indexes(d, graph_up)]


def _ready_documents(
    session: Session, owner_id: str, requested: list[str] | None
) -> list[db.Document]:
    """The user's ready documents, limited to the requested ones if given."""
    query = session.query(db.Document).filter(
        db.Document.owner_id == owner_id, db.Document.status == "ready"
    )
    if requested:
        query = query.filter(db.Document.id.in_(requested))
    lab = db.lab_document_ids(session, owner_id)  # Lab snippets are asked on the Lab page
    documents = [document for document in query if document.id not in lab]
    if not documents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No ready documents to search")
    return documents
