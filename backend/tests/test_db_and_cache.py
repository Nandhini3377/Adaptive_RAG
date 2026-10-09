"""Tests for the SQLite tables and the LLM response cache."""

import pytest
from sqlalchemy.exc import IntegrityError

from adaptive_rag.llm.cache import CachedLLM
from adaptive_rag.schemas import Chunk
from adaptive_rag.store import db

pytestmark = pytest.mark.usefixtures("memory_db")


def make_user_and_document() -> tuple[str, str]:
    with db.session_scope() as session:
        user = db.User(email="alice@example.com", password_hash="x")
        session.add(user)
        session.flush()
        document = db.Document(
            owner_id=user.id,
            filename="handbook.md",
            file_type="md",
            file_hash="abc",
            file_path="/tmp/handbook.md",
        )
        session.add(document)
        session.flush()
        return user.id, document.id


def test_chunks_are_saved_and_read_back_in_order():
    """Chunk text survives a round trip, in document order."""
    user_id, document_id = make_user_and_document()
    chunks = [
        Chunk(id=f"c{n}", document_id=document_id, owner_id=user_id, text=f"text {n}")
        for n in range(3)
    ]
    with db.session_scope() as session:
        db.save_chunks(session, chunks)
    with db.session_scope() as session:
        assert db.load_chunks(session, document_id) == chunks


def test_new_document_defaults():
    """A fresh upload starts in 'scanning' with no indexes built."""
    _, document_id = make_user_and_document()
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        assert document.status == "scanning"
        assert document.has_bm25 is False
        assert document.graph_status == "none"


def test_emails_are_unique():
    """Two accounts cannot share an email."""
    make_user_and_document()
    with pytest.raises(IntegrityError), db.session_scope() as session:
        session.add(db.User(email="alice@example.com", password_hash="y"))


def test_deleting_a_document_deletes_its_chunks():
    """Foreign keys cascade, so no orphan chunks are left behind."""
    user_id, document_id = make_user_and_document()
    with db.session_scope() as session:
        db.save_chunks(
            session,
            [Chunk(id="c1", document_id=document_id, owner_id=user_id, text="t")],
        )
    with db.session_scope() as session:
        session.delete(session.get(db.Document, document_id))
    with db.session_scope() as session:
        assert db.load_chunks(session, document_id) == []


# ------------------------------------------------------------------ cache


def test_second_identical_call_is_free(fake_llm):
    """The repeat call is served from SQLite: no LLM call, 0 tokens, 0 cost."""
    llm = CachedLLM(fake_llm)
    messages = [{"role": "user", "content": "hi"}]
    first = llm.complete(messages)
    second = llm.complete(messages)
    assert len(fake_llm.calls) == 1
    assert first.cached is False and first.input_tokens == 100
    assert second.cached is True
    assert second.text == first.text
    assert (second.input_tokens, second.output_tokens, second.cost_inr) == (0, 0, 0.0)


def test_different_parameters_miss_the_cache(fake_llm):
    """Changing the messages, token cap, or effort makes a new request."""
    llm = CachedLLM(fake_llm)
    llm.complete([{"role": "user", "content": "hi"}])
    llm.complete([{"role": "user", "content": "hello"}])
    llm.complete([{"role": "user", "content": "hi"}], max_tokens=50)
    llm.complete([{"role": "user", "content": "hi"}], reasoning_effort="high")
    assert len(fake_llm.calls) == 4


def test_json_calls_are_cached_with_their_data(fake_llm):
    """Structured answers come back from the cache with parsed data."""
    fake_llm.data = {"city": "Paris"}
    llm = CachedLLM(fake_llm)
    schema = {"type": "object"}
    llm.complete_json([{"role": "user", "content": "?"}], schema)
    again = llm.complete_json([{"role": "user", "content": "?"}], schema)
    assert again.cached is True
    assert again.data == {"city": "Paris"}
    assert len(fake_llm.calls) == 1
