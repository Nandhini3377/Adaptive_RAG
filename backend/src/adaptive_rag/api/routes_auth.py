"""POST /auth/register and /auth/login."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from adaptive_rag.api.deps import SessionDep, UserDep
from adaptive_rag.api.limits import login_limiter, require_registration_open
from adaptive_rag.auth import create_token, hash_password, verify_password
from adaptive_rag.store import db

router = APIRouter(prefix="/auth", tags=["auth"])

# Checked when the email is unknown, so that reply takes as long as a wrong password
_UNKNOWN_USER_HASH = hash_password("no-such-user")


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def fits_bcrypt(cls, password: str) -> str:
        """bcrypt accepts at most 72 bytes, and one non-English character can be several."""
        if len(password.encode()) > 72:
            raise ValueError("Password is too long (72 bytes at most)")
        return password


class UserOut(BaseModel):
    id: str
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: Credentials, session: SessionDep) -> UserOut:
    require_registration_open(session)
    email = body.email.lower()
    if session.query(db.User).filter(db.User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = db.User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    session.flush()
    return UserOut(id=user.id, email=user.email)


@router.post("/login")
def login(body: Credentials, session: SessionDep) -> TokenOut:
    email = body.email.lower()
    login_limiter.check(email)
    user = session.query(db.User).filter(db.User.email == email).first()
    password_hash = user.password_hash if user is not None else _UNKNOWN_USER_HASH
    # Same message (and same work) for unknown email and wrong password: don't reveal which
    if not verify_password(body.password, password_hash) or user is None:
        login_limiter.record_failure(email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    login_limiter.reset(email)
    return TokenOut(access_token=create_token(user.id))


@router.get("/me")
def me(user: UserDep) -> UserOut:
    return UserOut(id=user.id, email=user.email)
