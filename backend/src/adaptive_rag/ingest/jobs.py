"""Background work for an uploaded document, with status and progress in SQLite."""

import logging
from pathlib import Path

from adaptive_rag import services
from adaptive_rag.ingest.chunker import chunk_elements
from adaptive_rag.ingest.parser import parse_file
from adaptive_rag.store import db

log = logging.getLogger(__name__)


def set_status(document_id: str, status: str, progress: int, stage: str) -> None:
    """Record where the document is in the pipeline; the UI polls this."""
    with db.session_scope() as session:
        document = session.get(db.Document, document_id)
        if document is not None:
            document.status = status
            document.progress = progress
            document.stage = stage


def index_document(document_id: str) -> None:
    """Parse, chunk, embed, and store a document, then mark it ready."""
    try:
        with db.session_scope() as session:
            document = session.get(db.Document, document_id)
            if document is None:
                return
            path, owner_id = Path(document.file_path), document.owner_id

        set_status(document_id, "indexing", 10, "Parsing")
        elements = parse_file(path)

        set_status(document_id, "indexing", 30, "Chunking")
        chunks = chunk_elements(elements, document_id=document_id, owner_id=owner_id)

        set_status(document_id, "indexing", 50, "Embedding chunks")
        services.vector_store().add_chunks(chunks)

        with db.session_scope() as session:
            db.save_chunks(session, chunks)
            document = session.get(db.Document, document_id)
            if document is not None:
                document.strategy = document.strategy or "vector"
        set_status(document_id, "ready", 100, "Ready")
    except Exception as error:
        log.exception("Indexing failed for %s", document_id)
        with db.session_scope() as session:
            document = session.get(db.Document, document_id)
            if document is not None:
                document.status = "failed"
                document.stage = "Failed"
                document.error = str(error)[:1000]
