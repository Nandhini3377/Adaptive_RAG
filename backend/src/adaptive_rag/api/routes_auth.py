"""POST /auth/register and /auth/login."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from adaptive_rag.api.deps import SessionDep, UserDep
from adaptive_rag.auth import create_token, hash_password, verify_password
from adaptive_rag.store import db

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt reads at most 72 bytes


class UserOut(BaseModel):
    id: str
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: Credentials, session: SessionDep) -> UserOut:
    email = body.email.lower()
    if session.query(db.User).filter(db.User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = db.User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    session.flush()
    return UserOut(id=user.id, email=user.email)


@router.post("/login")
def login(body: Credentials, session: SessionDep) -> TokenOut:
    user = session.query(db.User).filter(db.User.email == body.email.lower()).first()
    # Same message for unknown email and wrong password: don't reveal which
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    return TokenOut(access_token=create_token(user.id))


@router.get("/me")
def me(user: UserDep) -> UserOut:
    return UserOut(id=user.id, email=user.email)
