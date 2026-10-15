"""Limits that keep a public deployment from being abused.

- Login attempts per email, so passwords cannot be guessed at speed.
- Documents per user and questions per day, because both spend LLM credits.

Login attempts are counted in memory (the app runs as one process). The other two
are counted from the database, so they survive a restart.
"""

import threading
import time
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from adaptive_rag.config import settings
from adaptive_rag.store import db

_MAX_TRACKED_EMAILS = 10_000  # forget expired entries once this many emails are tracked


class LoginLimiter:
    """Remembers recent wrong passwords per email."""

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, email: str) -> None:
        """Raise 429 if this email has used up its attempts for the window."""
        with self._lock:
            if len(self._recent(email)) >= settings.login_max_attempts:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Too many failed logins. Try again in {settings.login_window_minutes} "
                    "minutes.",
                )

    def record_failure(self, email: str) -> None:
        with self._lock:
            if len(self._failures) >= _MAX_TRACKED_EMAILS:
                for known in list(self._failures):
                    self._recent(known)
            self._failures[email] = [*self._recent(email), time.monotonic()]

    def reset(self, email: str) -> None:
        """A correct password clears the count."""
        with self._lock:
            self._failures.pop(email, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()

    def _recent(self, email: str) -> list[float]:
        """This email's failures inside the window; forgets the email when none are left."""
        cutoff = time.monotonic() - settings.login_window_minutes * 60
        recent = [moment for moment in self._failures.get(email, []) if moment > cutoff]
        if recent:
            self._failures[email] = recent
        else:
            self._failures.pop(email, None)
        return recent


login_limiter = LoginLimiter()


def require_registration_open(session: Session) -> None:
    """Raise 403 when sign-ups are switched off or the account cap is reached."""
    if not settings.registration_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is closed")
    if session.query(db.User).count() >= settings.max_users:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is closed: no places left")


def require_document_quota(session: Session, owner_id: str) -> None:
    """Raise 429 when the user already has the maximum number of documents."""
    count = session.query(db.Document).filter(db.Document.owner_id == owner_id).count()
    count -= len(db.lab_document_ids(session, owner_id))  # the Lab snippet is not counted
    if count >= settings.max_documents_per_user:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"You can keep up to {settings.max_documents_per_user} documents. "
            "Delete one to upload another.",
        )


def require_query_quota(session: Session, owner_id: str) -> None:
    """Raise 429 when the user has asked the day's maximum number of questions."""
    since = db.now() - timedelta(days=1)
    count = (
        session.query(db.QueryRecord)
        .filter(db.QueryRecord.owner_id == owner_id, db.QueryRecord.created_at >= since)
        .count()
    )
    if count >= settings.max_queries_per_day:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Daily limit of {settings.max_queries_per_day} questions reached. Try again tomorrow.",
        )
