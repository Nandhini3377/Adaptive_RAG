"""Password hashing (bcrypt) and login tokens (JWT)."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from adaptive_rag.config import settings


class AuthError(Exception):
    """Bad credentials or an invalid token."""


def hash_password(password: str) -> str:
    """Salted, slow hash: a stolen database does not reveal passwords."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user_id: str) -> str:
    """A signed token that proves who the user is until it expires."""
    expires = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expires}
    return jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def user_id_from_token(token: str) -> str:
    """Check the signature and expiry, then return the user ID inside."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret.get_secret_value(), algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as error:
        raise AuthError("Invalid or expired token") from error
    return str(payload["sub"])
