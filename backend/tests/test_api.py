"""End-to-end API tests: auth, upload, background indexing, query, isolation."""

import pytest
from fastapi.testclient import TestClient

from adaptive_rag import services
from adaptive_rag.api.app import create_app
from adaptive_rag.config import settings
from adaptive_rag.store import db
from adaptive_rag.store.vector_store import VectorStore
from tests.conftest import FakeLLM

HANDBOOK = b"""# Leave Policy

Employees receive 20 days of annual leave per year.

# Security

Never share your password with anyone.
"""


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM("Employees receive 20 days of annual leave [1].")


@pytest.fixture
def client(memory_db, tmp_path, monkeypatch, llm):
    """An app with an in-memory database, in-memory Qdrant, a fake LLM, and a temp folder."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    services.override(vector_store=VectorStore(location=":memory:"), llm=llm)
    yield TestClient(create_app())
    services.reset()


def login(client: TestClient, email: str = "alice@example.com") -> dict[str, str]:
    """Register and log in; return the auth header."""
    credentials = {"email": email, "password": "correct-horse"}
    client.post("/auth/register", json=credentials)
    token = client.post("/auth/login", json=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def upload(client, headers, name="handbook.md", content=HANDBOOK):
    return client.post("/documents", files={"file": (name, content)}, headers=headers)


# ------------------------------------------------------------------- auth


def test_register_login_and_me(client):
    headers = login(client)
    assert client.get("/auth/me", headers=headers).json()["email"] == "alice@example.com"


def test_passwords_are_hashed_not_stored(client):
    login(client)
    with db.session_scope() as session:
        user = session.query(db.User).one()
        assert user.password_hash != "correct-horse"
        assert user.password_hash.startswith("$2")  # bcrypt format


def test_duplicate_email_and_wrong_password(client):
    login(client)
    duplicate = {"email": "alice@example.com", "password": "another-pass"}
    assert client.post("/auth/register", json=duplicate).status_code == 409
    assert client.post("/auth/login", json=duplicate).status_code == 401


def test_requests_without_a_valid_token_are_rejected(client):
    assert client.get("/documents").status_code == 401
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/documents", headers=bad).status_code == 401


# ---------------------------------------------------------------- uploads


def test_upload_is_accepted_then_indexed_in_the_background(client):
    headers = login(client)
    response = upload(client, headers)
    assert response.status_code == 202
    document = client.get(f"/documents/{response.json()['document_id']}", headers=headers).json()
    assert document["status"] == "ready"
    assert document["progress"] == 100
    assert document["filename"] == "handbook.md"
    with db.session_scope() as session:
        assert len(db.load_chunks(session, document["id"])) == 2  # one per section


def test_same_file_twice_is_not_duplicated(client):
    headers = login(client)
    first = upload(client, headers).json()
    second = upload(client, headers, name="copy.md").json()
    assert second == {"document_id": first["document_id"], "duplicate": True}
    assert len(client.get("/documents", headers=headers).json()) == 1


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("virus.exe", b"MZ..."),
        ("fake.pdf", b"just text pretending"),
        ("fake.docx", b"PK\x03\x04not really a zip"),
        ("binary.txt", b"\xff\xfe\x00\x00"),
        ("empty.md", b""),
    ],
)
def test_bad_files_are_rejected_by_content(client, name, content):
    response = upload(client, login(client), name=name, content=content)
    assert response.status_code == 415


# ------------------------------------------------------------------ query


def test_query_returns_cited_answer_and_is_recorded(client, llm):
    headers = login(client)
    upload(client, headers)
    response = client.post(
        "/query", json={"question": "How many leave days?"}, headers=headers
    ).json()
    assert response["answer"] == "Employees receive 20 days of annual leave [1]."
    assert response["citations"][0]["section"] == "Leave Policy"
    assert response["mode"] == "vector"
    assert set(response["timings"]) == {"retrieve_ms", "generate_ms"}
    assert "Employees receive 20 days" in llm.calls[0][1]["content"]  # evidence in prompt
    with db.session_scope() as session:
        assert session.get(db.QueryRecord, response["query_id"]).query == "How many leave days?"


def test_query_without_ready_documents_is_a_clear_error(client):
    response = client.post("/query", json={"question": "Hi?"}, headers=login(client))
    assert response.status_code == 400


# ------------------------------------------------------------- isolation


def test_users_never_see_each_others_documents(client, llm):
    alice = login(client, "alice@example.com")
    bob = login(client, "bob@example.com")
    alice_doc = upload(client, alice).json()["document_id"]
    upload(client, bob, name="bob.md", content=b"# Bob\n\nBob's salary is secret.")

    assert client.get(f"/documents/{alice_doc}", headers=bob).status_code == 404
    assert client.delete(f"/documents/{alice_doc}", headers=bob).status_code == 404
    assert [d["filename"] for d in client.get("/documents", headers=bob).json()] == ["bob.md"]

    # Bob asks about Alice's leave policy: none of her text reaches the LLM
    client.post("/query", json={"question": "How many leave days?"}, headers=bob)
    assert "annual leave" not in llm.calls[-1][1]["content"]

    # Bob cannot target Alice's document by ID either
    targeted = {"question": "Leave?", "document_ids": [alice_doc]}
    assert client.post("/query", json=targeted, headers=bob).status_code == 400


def test_delete_removes_document_everywhere(client):
    headers = login(client)
    document_id = upload(client, headers).json()["document_id"]
    assert client.delete(f"/documents/{document_id}", headers=headers).status_code == 204
    assert client.get(f"/documents/{document_id}", headers=headers).status_code == 404
    with db.session_scope() as session:
        assert db.load_chunks(session, document_id) == []
    assert services.vector_store().count(owner_id=_user_id("alice@example.com")) == 0


def _user_id(email: str) -> str:
    with db.session_scope() as session:
        return session.query(db.User).filter(db.User.email == email).one().id
