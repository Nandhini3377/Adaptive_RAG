"""Keyword search (BM25) per document, kept in memory and rebuilt from SQLite.

Vector search finds meaning; BM25 finds exact words. A question about
"AUTH-403" needs the chunk that literally contains AUTH-403.

Uses rank-bm25 directly. (The PRD named LangChain's BM25Retriever, but that
lives in langchain-community, which is being discontinued, and it only wraps
rank-bm25 anyway.)

BM25Plus, not the classic BM25Okapi: Okapi gives words found in most chunks a
negative weight, so a 1- or 2-chunk document could never match anything.
"""

import re
import threading
from dataclasses import dataclass

from rank_bm25 import BM25Plus
from sqlalchemy.orm import Session

from adaptive_rag.schemas import Chunk, SearchHit
from adaptive_rag.store import db

# Words and IDs: keeps "auth-403", "v2.1", "user_id" whole; drops punctuation
_TOKEN = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*")

# Question words carry no topic, so they should not decide the ranking
_STOPWORDS = frozenset(
    (
        "a an and are as at be by can do does for from how i in is it me my of on or our "
        "should the this to was we what when where which who why will with you your"
    ).split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase tokens without stopwords; 'AUTH-403.' matches 'auth-403'."""
    return [_singular(token) for token in _TOKEN.findall(text.lower()) if token not in _STOPWORDS]


def _singular(token: str) -> str:
    """Very light stemming so 'means' matches 'mean' and 'services' matches 'service'."""
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss") and token.isalpha():
        return token[:-1]
    return token


@dataclass
class _Index:
    owner_id: str
    bm25: BM25Plus
    chunks: list[Chunk]
    token_sets: list[set[str]]  # each chunk's words, to skip chunks with no match


class BM25Store:
    """One BM25 index per document that has keyword search enabled."""

    def __init__(self) -> None:
        self._indexes: dict[str, _Index] = {}  # document id -> its index
        self._lock = threading.Lock()  # background indexing and queries share this

    def build(self, document_id: str, chunks: list[Chunk]) -> None:
        """(Re)build the index for one document."""
        if not chunks:
            return
        tokens = [tokenize(chunk.text) for chunk in chunks]
        index = _Index(
            owner_id=chunks[0].owner_id,
            bm25=BM25Plus(tokens),
            chunks=chunks,
            token_sets=[set(t) for t in tokens],
        )
        with self._lock:
            self._indexes[document_id] = index

    def remove(self, document_id: str) -> None:
        with self._lock:
            self._indexes.pop(document_id, None)

    def has(self, document_id: str) -> bool:
        return document_id in self._indexes

    def search(
        self, question: str, owner_id: str, document_ids: list[str], k: int
    ) -> list[SearchHit]:
        """Top-k chunks by BM25 score across the owner's indexed documents."""
        tokens = tokenize(question)
        if not tokens:
            return []
        with self._lock:
            indexes = [
                index
                for document_id, index in self._indexes.items()
                if index.owner_id == owner_id and document_id in document_ids
            ]
        hits: list[SearchHit] = []
        for index in indexes:
            scores = index.bm25.get_scores(tokens)
            for chunk, words, score in zip(index.chunks, index.token_sets, scores, strict=True):
                if words.intersection(tokens):  # only chunks sharing a word with the question
                    hits.append(SearchHit(chunk=chunk, score=float(score)))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:k]

    def rebuild_from_db(self, session: Session) -> int:
        """On server start: rebuild every enabled index from saved chunks."""
        documents = session.query(db.Document).filter(db.Document.has_bm25.is_(True)).all()
        for document in documents:
            self.build(document.id, db.load_chunks(session, document.id))
        return len(documents)
