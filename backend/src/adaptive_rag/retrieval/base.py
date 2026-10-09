"""One interface for every retrieval mode (FR22), so the router can swap them."""

from abc import ABC, abstractmethod

from adaptive_rag.schemas import Mode, RetrievalResult


class Retriever(ABC):
    """Finds candidate chunks for a question within the owner's documents."""

    mode: Mode

    @abstractmethod
    def retrieve(
        self, question: str, owner_id: str, document_ids: list[str], k: int
    ) -> RetrievalResult:
        """Return up to k candidates, best first."""
