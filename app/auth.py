"""Регистрация, вход и отзыв токена доступа."""

import hashlib
import hmac
import secrets
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User, UserSession

TOKEN_LIFETIME = 24 * 60 * 60
ITERATIONS = 260_000
bearer = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    user_token: str
    token_type: str = "bearer"


def make_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(digest, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def token_digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def validate_token(session: Session, raw_token: str) -> User | None:
    if not raw_token:
        return None
    stored = session.get(UserSession, token_digest(raw_token))
    if stored is None or stored.expires_at <= int(time.time()):
        return None
    return session.get(User, stored.user_id)


def make_auth_router(sessions):
    router = APIRouter(prefix="/auth", tags=["Авторизация"])

    def db_session():
        with sessions() as session:
            yield session

    Db = Annotated[Session, Depends(db_session)]
    Bearer = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]

    @router.post("/register", status_code=201)
    def register(data: Credentials, db: Db):
        user = User(username=data.username, password_hash=make_password_hash(data.password))
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Пользователь уже существует") from exc
        return {"id": user.id, "username": user.username}

    @router.post("/login", response_model=TokenResponse)
    def login(data: Credentials, db: Db):
        user = db.scalar(select(User).where(User.username == data.username))
        if user is None or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        token = secrets.token_urlsafe(32)
        db.add(UserSession(
            token_hash=token_digest(token),
            user_id=user.id,
            expires_at=int(time.time()) + TOKEN_LIFETIME,
        ))
        db.commit()
        return TokenResponse(user_token=token)

    @router.post("/logout", status_code=204)
    def logout(credentials: Bearer, db: Db):
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Требуется Bearer token")
        stored = db.get(UserSession, token_digest(credentials.credentials))
        if stored is None or stored.expires_at <= int(time.time()):
            raise HTTPException(status_code=401, detail="Недействительный токен")
        db.delete(stored)
        db.commit()
        return None

    return router
