import hashlib
from enum import StrEnum

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import app.repository as repo
from app.database import get_db
from app.models import User

MIN_PASSWORD_LENGTH = 8
# bcrypt truncates inputs at 72 bytes. Hash the password first so passwords
# longer than 72 bytes still contribute their full entropy.
_BCRYPT_MAX_BYTES = 72


def _prepare(plain: str) -> bytes:
    encoded = plain.encode("utf-8")
    if len(encoded) <= _BCRYPT_MAX_BYTES:
        return encoded
    return hashlib.sha256(encoded).hexdigest().encode("ascii")


class SessionKey(StrEnum):
    USER_ID = "user_id"


class AuthRedirect(Exception):
    """Raised by HTML-route auth dependencies to trigger a redirect to /login.

    The exception handler in `app.main` translates this into either an
    `HX-Redirect` 204 response (for HTMX requests) or a normal 303 redirect.
    """


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("ascii"))
    except ValueError:
        return False


def _load_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get(SessionKey.USER_ID)
    if not user_id:
        return None
    return repo.get_user_by_id(db, user_id)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Auth dependency for JSON/REST routes — 401 on failure."""
    user = _load_user(request, db)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def current_user_or_redirect(request: Request, db: Session = Depends(get_db)) -> User:
    """Auth dependency for HTML routes — redirect to /login on failure."""
    user = _load_user(request, db)
    if user is None:
        request.session.clear()
        raise AuthRedirect()
    return user


def optional_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Resolve the current user if any, returning None when anonymous."""
    return _load_user(request, db)
