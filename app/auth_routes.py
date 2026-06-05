from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy.orm import Session

import app.repository as repo
from app.auth import MIN_PASSWORD_LENGTH, SessionKey, hash_password, verify_password
from app.database import get_db

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


class _Credentials(BaseModel):
    email: EmailStr
    password: str


def _validate_credentials(email: str, password: str) -> tuple[_Credentials | None, str | None]:
    try:
        creds = _Credentials(email=email, password=password)
    except ValidationError:
        return None, "Please enter a valid email address."
    if len(password) < MIN_PASSWORD_LENGTH:
        return None, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return creds, None


def _render_auth(
    request: Request,
    template: str,
    *,
    error: str | None = None,
    email: str = "",
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        template,
        {"error": error, "email": email},
        status_code=status_code,
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    if request.session.get(SessionKey.USER_ID):
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return _render_auth(request, "login.html")


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> HTMLResponse:
    creds, error = _validate_credentials(email, password)
    if creds is None:
        return _render_auth(
            request, "login.html", error=error, email=email, status_code=status.HTTP_400_BAD_REQUEST
        )
    user = repo.get_user_by_email(db, creds.email)
    if user is None or not verify_password(creds.password, user.password_hash):
        return _render_auth(
            request,
            "login.html",
            error="Invalid email or password.",
            email=email,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    request.session[SessionKey.USER_ID] = user.id
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request) -> HTMLResponse:
    if request.session.get(SessionKey.USER_ID):
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return _render_auth(request, "register.html")


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> HTMLResponse:
    creds, error = _validate_credentials(email, password)
    if creds is None:
        return _render_auth(
            request,
            "register.html",
            error=error,
            email=email,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if repo.get_user_by_email(db, creds.email):
        return _render_auth(
            request,
            "register.html",
            error="An account with that email already exists.",
            email=email,
            status_code=status.HTTP_409_CONFLICT,
        )
    user = repo.create_user(db, creds.email, hash_password(creds.password))
    request.session[SessionKey.USER_ID] = user.id
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
