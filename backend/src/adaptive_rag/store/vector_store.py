"""All Qdrant calls live here (embedded mode: no server needed)."""

from qdrant_client import QdrantClient, models

from adaptive_rag.config import settings
from adaptive_rag.models.embedder import embed_query, embed_texts, embedding_size
from adaptive_rag.schemas import Chunk, SearchHit

COLLECTION = "chunks"


class VectorStore:
    """Stores chunk embeddings and finds the chunks closest to a question."""

    def __init__(self, location: str | None = None) -> None:
        """Open the store on disk, or in memory when location is ":memory:"."""
        if location == ":memory:":
            self._client = QdrantClient(location=":memory:")
        else:
            path = location or str(settings.data_dir / "qdrant")
            self._client = QdrantClient(path=path)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create the collection the first time the store is opened."""
        if self._client.collection_exists(COLLECTION):
            return
        self._client.create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(
                size=embedding_size(), distance=models.Distance.COSINE
            ),
        )

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """Embed chunks and save them with their metadata."""
        if not chunks:
            return
        vectors = embed_texts([chunk.text for chunk in chunks])
        points = [
            models.PointStruct(id=chunk.id, vector=vector, payload=chunk.model_dump())
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self._client.upsert(collection_name=COLLECTION, points=points)

    def search(
        self,
        question: str,
        owner_id: str,
        document_ids: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[SearchHit]:
        """Return the owner's chunks closest in meaning to the question."""
        result = self._client.query_points(
            collection_name=COLLECTION,
            query=embed_query(question),
            query_filter=_owner_filter(owner_id, document_ids),
            limit=top_k or settings.top_k,
        )
        return [
            SearchHit(chunk=Chunk(**point.payload), score=point.score)
            for point in result.points
        ]

    def delete_document(self, document_id: str) -> None:
        """Remove every chunk of one document."""
        self._client.delete(
            collection_name=COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[_match("document_id", document_id)])
            ),
        )

    def count(self, owner_id: str) -> int:
        """Count the number of chunks belonging to an owner."""
        result = self._client.count(
            collection_name=COLLECTION,
            count_filter=models.Filter(must=[_match("owner_id", owner_id)]),
        )
        return result.count


def _match(field: str, value: str) -> models.FieldCondition:
    """Condition: payload field equals value."""
    return models.FieldCondition(key=field, match=models.MatchValue(value=value))


def _owner_filter(owner_id: str, document_ids: list[str] | None) -> models.Filter:
    """Only the owner's chunks, optionally limited to some documents."""
    conditions: list[models.Condition] = [_match("owner_id", owner_id)]
    if document_ids:
        conditions.append(
            models.FieldCondition(
                key="document_id", match=models.MatchAny(any=document_ids)
            )
        )
    return models.Filter(must=conditions)
