"""Things routes ask for: a database session and the logged-in user."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from adaptive_rag.auth import AuthError, user_id_from_token
from adaptive_rag.store import db

_bearer = HTTPBearer(auto_error=False)


def get_session() -> Iterator[Session]:
    with db.session_scope() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> db.User:
    """Reject the request unless it carries a valid 'Authorization: Bearer <token>'."""
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not logged in",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        user_id = user_id_from_token(credentials.credentials)
    except AuthError as error:
        raise unauthorized from error
    user = session.get(db.User, user_id)
    if user is None:
        raise unauthorized
    return user


UserDep = Annotated[db.User, Depends(current_user)]


def owned_document(session: Session, user: db.User, document_id: str) -> db.Document:
    """Fetch a document only if this user owns it; otherwise 404 (do not reveal it exists)."""
    document = session.get(db.Document, document_id)
    if document is None or document.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document
