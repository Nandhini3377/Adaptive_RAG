"""Tests for BM25, rank fusion, hybrid retrieval, and reranking."""

import uuid

import pytest

from adaptive_rag.models.reranker import rerank
from adaptive_rag.retrieval.base import rerank_hits
from adaptive_rag.retrieval.fusion import reciprocal_rank_fusion
from adaptive_rag.retrieval.hybrid import HybridRetriever
from adaptive_rag.retrieval.vector import VectorRetriever
from adaptive_rag.schemas import Chunk, GraphPath, SearchHit
from adaptive_rag.store.bm25_store import BM25Store, tokenize
from adaptive_rag.store.vector_store import VectorStore

# A runbook where the answer's error code is buried in a long chunk, next to
# chunks that merely look similar ("403 Forbidden", "AUTH-401").
_FILLER = (
    "Sign-in problems are the most common support ticket. First confirm the identity "
    "provider is healthy, then check whether a recent deploy changed session settings. "
    "Ask the user which browser they use and whether cookies are enabled. Most issues "
    "are solved by clearing the session cache. "
)
RUNBOOK = [
    _FILLER + "Escalate to the platform team if nothing works.",
    _FILLER + "Rare cases show error AUTH-403 in the logs, which means the signing key rotated.",
    _FILLER + "Document the ticket in the incident tracker.",
    "Error codes like AUTH-401 and AUTH-402 relate to passwords and locked accounts.",
    "The authentication service returns 403 Forbidden for blocked IP addresses.",
]
ANSWER = RUNBOOK[1]


def chunk(text: str, owner: str = "alice", doc: str = "runbook") -> Chunk:
    return Chunk(id=str(uuid.uuid4()), document_id=doc, owner_id=owner, text=text)


@pytest.fixture(scope="module")
def stores():
    chunks = [chunk(text) for text in RUNBOOK]
    vectors = VectorStore(location=":memory:")
    vectors.add_chunks([*chunks, chunk("AUTH-403 at Bob's company", owner="bob", doc="b")])
    bm25 = BM25Store()
    bm25.build("runbook", chunks)
    bm25.build("b", [chunk("AUTH-403 at Bob's company", owner="bob", doc="b")])
    return vectors, bm25


# ------------------------------------------------------------------- BM25


def test_tokenizer_keeps_ids_and_ignores_case_punctuation_and_stopwords():
    assert tokenize("What does Error AUTH-403 mean? See v2.1 (user_id).") == [
        "error",
        "auth-403",
        "mean",
        "see",
        "v2.1",
        "user_id",
    ]


def test_tokenizer_matches_simple_plurals():
    assert tokenize("services means") == tokenize("service mean")
    assert tokenize("access class") == ["access", "class"]  # 'ss' words are left alone


def test_bm25_finds_the_exact_code(stores):
    _, bm25 = stores
    hits = bm25.search("What does AUTH-403 mean?", "alice", ["runbook"], k=3)
    assert hits[0].chunk.text == ANSWER


def test_bm25_respects_owner_and_document_filters(stores):
    _, bm25 = stores
    assert all(
        h.chunk.owner_id == "alice" for h in bm25.search("AUTH-403", "alice", ["runbook", "b"], 10)
    )
    assert bm25.search("AUTH-403", "alice", ["other-doc"], k=5) == []


def test_bm25_works_on_tiny_documents():
    """A one-chunk document is still searchable (classic BM25 scores it below zero)."""
    bm25 = BM25Store()
    bm25.build("tiny", [chunk("Error AUTH-403 means the key rotated.", doc="tiny")])
    hits = bm25.search("AUTH-403", "alice", ["tiny"], k=5)
    assert len(hits) == 1 and hits[0].score > 0


def test_bm25_skips_chunks_with_no_shared_words(stores):
    _, bm25 = stores
    assert bm25.search("cafeteria lunch menu", "alice", ["runbook"], k=5) == []


# ----------------------------------------------------------------- fusion


def hit(chunk_id: str) -> SearchHit:
    return SearchHit(
        chunk=Chunk(id=chunk_id, document_id="d", owner_id="u", text=chunk_id), score=0
    )


def test_rrf_rewards_chunks_found_by_both_lists():
    """'b' is 2nd in both lists, so it beats 'a' and 'c' (1st in only one each)."""
    fused = reciprocal_rank_fusion([[hit("a"), hit("b")], [hit("c"), hit("b")]], k=60)
    assert [h.chunk.id for h in fused] == ["b", "a", "c"]
    assert fused[0].score == pytest.approx(2 / 62)


def test_rrf_lists_each_chunk_once():
    fused = reciprocal_rank_fusion([[hit("a")], [hit("a")], [hit("a")]])
    assert len(fused) == 1


def alphabetical(_question, hits, top_n):
    """A stand-in reranker: alphabetical order, so the expected result is obvious."""
    return sorted(hits, key=lambda h: h.chunk.id)[:top_n]


def test_rerank_hits_keeps_the_chunk_most_graph_edges_cite():
    """'table' states both hops of the path but reranks last; it keeps a top slot."""
    hits = [hit(c) for c in ["a", "b", "c", "d", "table"]]
    paths = [
        GraphPath(nodes=["X", "Y"], relations=["<-DEPENDS_ON"], chunk_ids=["d"]),
        GraphPath(nodes=["X", "Y", "Z"], relations=["<-DEPENDS_ON"] * 2, chunk_ids=["table"] * 2),
    ]
    top = rerank_hits(alphabetical, "q", hits, 3, paths)
    assert [h.chunk.id for h in top] == ["a", "d", "table"]  # both kept, reranker order kept


def test_rerank_hits_changes_nothing_when_graph_evidence_already_made_the_cut():
    hits = [hit(c) for c in ["a", "b", "c", "d"]]
    paths = [GraphPath(nodes=["X", "Y"], relations=["<-DEPENDS_ON"], chunk_ids=["b"])]
    top = rerank_hits(alphabetical, "q", hits, 3, paths)
    assert [h.chunk.id for h in top] == ["a", "b", "c"]


def test_rerank_hits_without_paths_is_plain_reranking():
    hits = [hit(c) for c in ["c", "a", "b"]]
    assert [h.chunk.id for h in rerank_hits(alphabetical, "q", hits, 2)] == ["a", "b"]


# ----------------------------------------------------------------- hybrid


def test_hybrid_rescues_buried_code_that_vector_search_ranks_low(stores):
    """The build-plan check (2.1): keyword search lifts the exact-ID chunk.

    Vector search ranks the answer 3rd, behind chunks that only look similar.
    """
    vectors, bm25 = stores
    question = "What does AUTH-403 mean?"
    vector_hits = VectorRetriever(vectors).retrieve(question, "alice", ["runbook"], k=5).hits
    hybrid_hits = HybridRetriever(vectors, bm25).retrieve(question, "alice", ["runbook"], k=5).hits
    vector_rank = [h.chunk.text for h in vector_hits].index(ANSWER) + 1
    hybrid_rank = [h.chunk.text for h in hybrid_hits].index(ANSWER) + 1
    assert vector_rank >= 3
    assert hybrid_rank == 1


# --------------------------------------------------------------- reranker


def test_reranker_keeps_the_answering_chunk_near_the_top_with_0_to_1_scores(stores):
    """The small reranker (MiniLM) ranks the buried answer 2nd, behind the short
    AUTH-401/402 chunk; bge-reranker-base ranked it 1st but needs 1 GB. Either way
    it reaches the LLM, which gets the top few chunks, not just the first."""
    vectors, _ = stores
    question = "What does AUTH-403 mean?"
    candidates = vectors.search(question, "alice", top_k=5)
    reranked = rerank(question, candidates, top_n=3)
    assert len(reranked) == 3
    assert ANSWER in [h.chunk.text for h in reranked[:2]]
    assert all(0 <= h.score <= 1 for h in reranked)
    assert reranked[0].score >= reranked[1].score >= reranked[2].score


def test_reranker_scores_unrelated_text_low():
    irrelevant = [hit("The cafeteria serves lunch at noon.")]
    irrelevant[0].chunk.text = "The cafeteria serves lunch at noon."
    assert rerank("What does error AUTH-403 mean?", irrelevant)[0].score < 0.1
