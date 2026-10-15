"""Keyword mode: BM25 only, for documents indexed without vectors (exact IDs, codes, names)."""

from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.schemas import RetrievalResult
from adaptive_rag.store.bm25_store import BM25Store


class KeywordRetriever(Retriever):
    mode = "keyword"

    def __init__(self, bm25_store: BM25Store) -> None:
        self._bm25 = bm25_store

    def retrieve(
        self, question: str, owner_id: str, document_ids: list[str], k: int
    ) -> RetrievalResult:
        return RetrievalResult(hits=self._bm25.search(question, owner_id, document_ids, k))
