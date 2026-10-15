"""Upload, analyze, choose intent, build indexes, list, inspect, and delete documents."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from adaptive_rag import services
from adaptive_rag.api.deps import SessionDep, UserDep, owned_document
from adaptive_rag.api.limits import require_document_quota
from adaptive_rag.config import settings
from adaptive_rag.ingest import jobs
from adaptive_rag.ingest.intent import INTENT_LABELS
from adaptive_rag.schemas import DocumentProfile, Intent
from adaptive_rag.store import db, files

router = APIRouter(prefix="/documents", tags=["documents"])


class UploadOut(BaseModel):
    document_id: str
    duplicate: bool = False


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    progress: int
    stage: str
    error: str
    strategy: str
    strategy_reason: str
    has_bm25: bool
    graph_status: str
    created_at: datetime

    @classmethod
    def of(cls, document: db.Document) -> "DocumentOut":
        return cls.model_validate(document, from_attributes=True)


class IntentOption(BaseModel):
    id: Intent
    label: str
    suggested: bool


class AnalysisOut(BaseModel):
    status: str
    profile: DocumentProfile
    intent_options: list[IntentOption]
    suggested_intents: list[str]
    user_intents: list[str] | None
    strategy: str | None
    confidence: float | None
    reason: str


class IntentIn(BaseModel):
    intents: list[Intent] = []
    skip: bool = False


class BuildIndexIn(BaseModel):
    index: Literal["bm25", "graph", "bm25+graph"]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload(
    file: UploadFile,
    user: UserDep,
    session: SessionDep,
    background: BackgroundTasks,
    intents: Annotated[list[Intent] | None, Form()] = None,
) -> UploadOut:
    """Validate and save the file, then analyze it in the background (202 = accepted).

    Send `intents` with the upload to skip the intent question (FR14).
    """
    # Read one byte past the limit at most: enough to know the file is too big
    limit = settings.max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"File is larger than {settings.max_upload_mb} MB"
        )
    filename = file.filename or "upload"
    try:
        file_type = files.detect_file_type(filename, content)
    except files.InvalidFileError as error:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(error)) from error

    file_hash, path = files.save_upload(user.id, file_type, content)
    existing = (
        session.query(db.Document)
        .filter(db.Document.owner_id == user.id, db.Document.file_hash == file_hash)
        .first()
    )
    if existing is not None:  # same bytes uploaded again: reuse, don't duplicate (FR7)
        return UploadOut(document_id=existing.id, duplicate=True)
    try:
        require_document_quota(session, user.id)
    except HTTPException:
        files.delete_upload(str(path))
        raise

    document = db.Document(
        owner_id=user.id,
        filename=filename,
        file_type=file_type,
        file_hash=file_hash,
        file_path=str(path),
    )
    session.add(document)
    session.commit()  # the background job reads it from a separate session
    background.add_task(jobs.analyze_document, document.id, intents)
    return UploadOut(document_id=document.id)


@router.get("")
def list_documents(user: UserDep, session: SessionDep) -> list[DocumentOut]:
    documents = (
        session.query(db.Document)
        .filter(db.Document.owner_id == user.id)
        .order_by(db.Document.created_at.desc())
    )
    lab = db.lab_document_ids(session, user.id)  # the Lab's snippet lives on its own page
    return [DocumentOut.of(document) for document in documents if document.id not in lab]


@router.get("/{document_id}")
def get_document(document_id: str, user: UserDep, session: SessionDep) -> DocumentOut:
    return DocumentOut.of(owned_document(session, user, document_id))


@router.get("/{document_id}/analysis")
def get_analysis(document_id: str, user: UserDep, session: SessionDep) -> AnalysisOut:
    """Scan signals, suggested intents, and (once decided) the strategy and reason."""
    document = owned_document(session, user, document_id)
    analysis = session.get(db.DocumentAnalysis, document_id)
    if analysis is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Analysis not ready ({document.status})")
    suggested = set(analysis.suggested_intents)
    return AnalysisOut(
        status=document.status,
        profile=DocumentProfile.model_validate(analysis.raw_features["profile"]),
        intent_options=[
            IntentOption(id=intent, label=label, suggested=intent in suggested)
            for intent, label in INTENT_LABELS.items()
        ],
        suggested_intents=analysis.suggested_intents,
        user_intents=analysis.user_intents,
        strategy=analysis.recommended_strategy or None,
        confidence=analysis.confidence if analysis.recommended_strategy else None,
        reason=analysis.reason,
    )


@router.post("/{document_id}/intent", status_code=status.HTTP_202_ACCEPTED)
def set_intent(
    document_id: str,
    body: IntentIn,
    user: UserDep,
    session: SessionDep,
    background: BackgroundTasks,
) -> DocumentOut:
    """The uploader's answer (or skip); runs the decision and indexing in the background."""
    document = owned_document(session, user, document_id)
    if document.status != "awaiting_intent":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Document is {document.status}")
    document.status, document.stage = "indexing", "Deciding strategy"
    session.commit()
    intents = None if body.skip or not body.intents else body.intents
    background.add_task(jobs.apply_intent, document.id, intents)
    return DocumentOut.of(document)


@router.post("/{document_id}/build-index", status_code=status.HTTP_202_ACCEPTED)
def build_index(
    document_id: str,
    body: BuildIndexIn,
    user: UserDep,
    session: SessionDep,
    background: BackgroundTasks,
) -> DocumentOut:
    """Add the keyword index and/or the graph, usually from a recommendation (FR20)."""
    document = owned_document(session, user, document_id)
    if document.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Document is {document.status}")
    if "graph" in body.index and services.graph_store() is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Neo4j is not running")
    document.status, document.stage = "indexing", f"Building {body.index}"
    session.commit()
    background.add_task(jobs.build_index, document.id, body.index)
    return DocumentOut.of(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, user: UserDep, session: SessionDep) -> Response:
    """Remove the document from every store: vectors, keywords, graph, chunks, file, row."""
    remove_document(session, owned_document(session, user, document_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def remove_document(session: Session, document: db.Document) -> None:
    """Delete a document from every store; the caller's session commits the row delete."""
    services.vector_store().delete_document(document.id)
    services.bm25_store().remove(document.id)
    if document.graph_status != "none" and (graph := services.graph_store()) is not None:
        graph.delete_document(document.id)
    files.delete_upload(document.file_path)
    session.delete(document)  # chunks, analysis, and Lab rows cascade
