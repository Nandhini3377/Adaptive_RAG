"""Tests for the Qdrant vector store."""

import uuid

import pytest

from adaptive_rag.schemas import Chunk
from adaptive_rag.store.vector_store import VectorStore


def make_chunk(text: str, owner: str = "alice", doc: str = "handbook") -> Chunk:
    """Build a chunk with a fresh UUID."""
    return Chunk(id=str(uuid.uuid4()), document_id=doc, owner_id=owner, text=text)


@pytest.fixture
def store() -> VectorStore:
    """A fresh in-memory store with Alice's handbook and Bob's private note."""
    s = VectorStore(location=":memory:")
    s.add_chunks(
        [
            make_chunk("Employees receive 20 days of annual leave per year."),
            make_chunk("Leave the building by the nearest exit during a fire alarm."),
            make_chunk("The Payment service depends on the Auth service.", doc="architecture"),
            make_chunk("Bob's salary is confidential.", owner="bob"),
        ]
    )
    return s


def test_search_finds_closest_meaning(store):
    """The best hit for a vacation question is the annual-leave chunk."""
    hits = store.search("How many vacation days do I get?", owner_id="alice")
    assert "annual leave" in hits[0].chunk.text
    assert hits[0].score > hits[1].score


def test_owner_never_sees_other_users_chunks(store):
    """Alice's search can never return Bob's chunk, even on a direct match."""
    hits = store.search("What is Bob's salary?", owner_id="alice")
    assert all(hit.chunk.owner_id == "alice" for hit in hits)


def test_filter_by_document(store):
    """Limiting to one document returns only that document's chunks."""
    hits = store.search("services", owner_id="alice", document_ids=["architecture"])
    assert [hit.chunk.document_id for hit in hits] == ["architecture"]


def test_top_k_limits_results(store):
    """top_k caps how many chunks come back."""
    assert len(store.search("leave", owner_id="alice", top_k=1)) == 1


def test_delete_document(store):
    """Deleting a document removes all its chunks from search."""
    store.delete_document("handbook")
    hits = store.search("annual leave", owner_id="alice")
    assert all(hit.chunk.document_id != "handbook" for hit in hits)
