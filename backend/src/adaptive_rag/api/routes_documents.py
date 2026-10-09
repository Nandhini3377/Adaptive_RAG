"""Upload, list, inspect, and delete documents."""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, UploadFile, status
from pydantic import BaseModel

from adaptive_rag import services
from adaptive_rag.api.deps import SessionDep, UserDep, owned_document
from adaptive_rag.ingest import jobs
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


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload(
    file: UploadFile, user: UserDep, session: SessionDep, background: BackgroundTasks
) -> UploadOut:
    """Validate and save the file, then index it in the background (202 = accepted)."""
    content = await file.read()
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

    document = db.Document(
        owner_id=user.id,
        filename=filename,
        file_type=file_type,
        file_hash=file_hash,
        file_path=str(path),
    )
    session.add(document)
    session.commit()  # the background job reads it from a separate session
    background.add_task(jobs.index_document, document.id)
    return UploadOut(document_id=document.id)


@router.get("")
def list_documents(user: UserDep, session: SessionDep) -> list[DocumentOut]:
    documents = (
        session.query(db.Document)
        .filter(db.Document.owner_id == user.id)
        .order_by(db.Document.created_at.desc())
    )
    return [DocumentOut.of(document) for document in documents]


@router.get("/{document_id}")
def get_document(document_id: str, user: UserDep, session: SessionDep) -> DocumentOut:
    return DocumentOut.of(owned_document(session, user, document_id))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, user: UserDep, session: SessionDep) -> Response:
    """Remove the document from every store: vectors, chunks, file, and row."""
    document = owned_document(session, user, document_id)
    services.vector_store().delete_document(document.id)
    files.delete_upload(document.file_path)
    session.delete(document)  # chunks and analysis rows cascade
    return Response(status_code=status.HTTP_204_NO_CONTENT)
