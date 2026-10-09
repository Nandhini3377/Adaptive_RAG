"""Vector mode: question embedding -> nearest chunks in Qdrant."""

from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.schemas import RetrievalResult
from adaptive_rag.store.vector_store import VectorStore


class VectorRetriever(Retriever):
    mode = "vector"

    def __init__(self, vector_store: VectorStore) -> None:
        self._vectors = vector_store

    def retrieve(
        self, question: str, owner_id: str, document_ids: list[str], k: int
    ) -> RetrievalResult:
        hits = self._vectors.search(question, owner_id, document_ids=document_ids, top_k=k)
        return RetrievalResult(hits=hits)
