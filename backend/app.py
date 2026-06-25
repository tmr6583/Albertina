from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "albertina.db"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SESSION_DURATION_HOURS = 12


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 480_000)
    return f"{salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        salt_hex, hash_hex = encoded_hash.split("$", 1)
    except ValueError:
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        480_000,
    )
    return hmac.compare_digest(candidate.hex(), hash_hex)


def build_initials(email: str) -> str:
    local_part = email.split("@", 1)[0]
    parts = [part for part in re.split(r"[.\-_]+", local_part) if part]
    if not parts:
        return email[:2].upper()
    initials = "".join(part[0].upper() for part in parts[:2])
    return initials[:2]


def validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe um e-mail válido.",
        )
    return normalized


def format_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "lastAccess": row["last_access_at"] or "Nunca acessou",
        "initials": row["initials"],
    }


def format_audit(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "time": row["created_at"],
        "tone": row["tone"],
    }


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def create_tables() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL,
              status TEXT NOT NULL,
              initials TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              last_access_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              revoked_at TEXT,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audits (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              description TEXT NOT NULL,
              tone TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )


def append_audit(db: sqlite3.Connection, title: str, description: str, tone: str = "neutral") -> None:
    db.execute(
        """
        INSERT INTO audits (id, title, description, tone, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(uuid4()), title, description, tone, iso_now()),
    )


def bootstrap_admin() -> None:
    admin_email = os.getenv("ALBERTINA_ADMIN_EMAIL", "admin@empresa.com").strip().lower()
    admin_password = os.getenv("ALBERTINA_ADMIN_PASSWORD", "Betin@01012023").strip()
    created_at = iso_now()

    with get_db() as db:
        user_count = db.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        if user_count:
            return

        db.execute(
            """
            INSERT INTO users (id, email, password_hash, role, status, initials, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                admin_email,
                hash_password(admin_password),
                "Administrador",
                "Ativo",
                build_initials(admin_email),
                created_at,
                created_at,
            ),
        )
        append_audit(
            db,
            "Bootstrap administrativo concluído",
            "Conta inicial criada para o primeiro acesso administrativo da aplicação.",
        )
        append_audit(
            db,
            "Autenticação própria habilitada",
            "Backend FastAPI preparado para login e gestão inicial de usuários.",
            "accent",
        )


class LoginPayload(BaseModel):
    email: str
    password: str


class CreateUserPayload(BaseModel):
    email: str
    password: str = Field(min_length=8)
    status: str = "Ativo"


class PasswordPayload(BaseModel):
    password: str = Field(min_length=8)
    confirmPassword: str = Field(min_length=8)


class StatusPayload(BaseModel):
    status: str


class UserResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    email: str
    role: str
    status: str
    createdAt: str
    lastAccess: str
    initials: str


class LoginResponse(BaseModel):
    token: str
    user: UserResponse


class AuditResponse(BaseModel):
    id: str
    title: str
    description: str
    time: str
    tone: str


app = FastAPI(title="Albertina API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3500", "http://127.0.0.1:3500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    create_tables()
    bootstrap_admin()


def get_current_user(authorization: str | None = Header(default=None)) -> sqlite3.Row:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou ausente.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    token_hash = hash_secret(token)
    now_iso = iso_now()

    with get_db() as db:
        row = db.execute(
            """
            SELECT users.*
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
              AND sessions.revoked_at IS NULL
              AND sessions.expires_at > ?
            """,
            (token_hash, now_iso),
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sessão expirada ou inválida.",
            )

        if row["status"] != "Ativo":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O usuário autenticado está inativo.",
            )

        return row


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginPayload) -> dict[str, Any]:
    email = validate_email(payload.email)
    password = payload.password.strip()

    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not verify_password(password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="E-mail ou senha inválidos.",
            )

        if user["status"] != "Ativo":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O usuário está inativo.",
            )

        token = secrets.token_urlsafe(32)
        now = utc_now()
        db.execute(
            """
            INSERT INTO sessions (id, user_id, token_hash, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                user["id"],
                hash_secret(token),
                now.isoformat(),
                (now + timedelta(hours=SESSION_DURATION_HOURS)).isoformat(),
            ),
        )
        db.execute(
            "UPDATE users SET last_access_at = ?, updated_at = ? WHERE id = ?",
            (now.isoformat(), now.isoformat(), user["id"]),
        )
        append_audit(
            db,
            "Login realizado",
            f"O usuário {email} acessou a área administrativa da aplicação.",
            "success",
        )
        refreshed = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()

        return {"token": token, "user": format_user(refreshed)}


@app.get("/api/auth/me", response_model=UserResponse)
def me(current_user: sqlite3.Row = Depends(get_current_user)) -> dict[str, Any]:
    return format_user(current_user)


@app.post("/api/auth/logout")
def logout(
    current_user: sqlite3.Row = Depends(get_current_user),
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    token = authorization.removeprefix("Bearer ").strip()
    with get_db() as db:
        db.execute(
            "UPDATE sessions SET revoked_at = ? WHERE token_hash = ?",
            (iso_now(), hash_secret(token)),
        )
        append_audit(
            db,
            "Logout realizado",
            f"O usuário {current_user['email']} encerrou a sessão atual.",
            "neutral",
        )

    return {"status": "ok"}


@app.get("/api/users", response_model=list[UserResponse])
def list_users(current_user: sqlite3.Row = Depends(get_current_user)) -> list[dict[str, Any]]:
    del current_user
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM users ORDER BY datetime(created_at) DESC, email ASC"
        ).fetchall()
        return [format_user(row) for row in rows]


@app.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserPayload,
    current_user: sqlite3.Row = Depends(get_current_user),
) -> dict[str, Any]:
    email = validate_email(payload.email)
    password = payload.password.strip()
    status_value = payload.status.strip().title()
    if status_value not in {"Ativo", "Inativo"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O status deve ser Ativo ou Inativo.",
        )

    now = iso_now()
    user_id = str(uuid4())

    with get_db() as db:
        exists = db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe um usuário com este e-mail.",
            )

        db.execute(
            """
            INSERT INTO users (id, email, password_hash, role, status, initials, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                email,
                hash_password(password),
                "Administrador",
                status_value,
                build_initials(email),
                now,
                now,
            ),
        )
        append_audit(
            db,
            "Usuário criado",
            f"O usuário {current_user['email']} criou a conta {email}.",
            "success",
        )
        created = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return format_user(created)


@app.patch("/api/users/{user_id}/password")
def update_password(
    user_id: str,
    payload: PasswordPayload,
    current_user: sqlite3.Row = Depends(get_current_user),
) -> dict[str, str]:
    if payload.password != payload.confirmPassword:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A confirmação da senha não confere.",
        )

    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

        db.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (hash_password(payload.password), iso_now(), user_id),
        )
        append_audit(
            db,
            "Senha atualizada",
            f"O usuário {current_user['email']} alterou a senha da conta {user['email']}.",
            "accent",
        )

    return {"status": "ok"}


@app.patch("/api/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: str,
    payload: StatusPayload,
    current_user: sqlite3.Row = Depends(get_current_user),
) -> dict[str, Any]:
    status_value = payload.status.strip().title()
    if status_value not in {"Ativo", "Inativo"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O status deve ser Ativo ou Inativo.",
        )

    if user_id == current_user["id"] and status_value == "Inativo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido desativar o usuário autenticado.",
        )

    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

        db.execute(
            "UPDATE users SET status = ?, updated_at = ? WHERE id = ?",
            (status_value, iso_now(), user_id),
        )
        if status_value == "Inativo":
            db.execute(
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (iso_now(), user_id),
            )
            append_audit(
                db,
                "Usuário desativado",
                f"O usuário {current_user['email']} desativou a conta {user['email']}.",
                "accent",
            )
        else:
            append_audit(
                db,
                "Usuário ativado",
                f"O usuário {current_user['email']} ativou a conta {user['email']}.",
                "success",
            )

        updated = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return format_user(updated)


@app.delete("/api/users/{user_id}")
def delete_user(
    user_id: str,
    current_user: sqlite3.Row = Depends(get_current_user),
) -> dict[str, str]:
    if user_id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido excluir o usuário autenticado.",
        )

    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        append_audit(
            db,
            "Usuário excluído",
            f"O usuário {current_user['email']} removeu a conta {user['email']}.",
            "danger",
        )

    return {"status": "ok"}


@app.get("/api/audit", response_model=list[AuditResponse])
def list_audits(current_user: sqlite3.Row = Depends(get_current_user)) -> list[dict[str, Any]]:
    del current_user
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM audits ORDER BY datetime(created_at) DESC LIMIT 50"
        ).fetchall()
        return [format_audit(row) for row in rows]


@app.get("/api/olist/overview")
def olist_overview(current_user: sqlite3.Row = Depends(get_current_user)) -> dict[str, Any]:
    del current_user
    return {
        "status": "Não configurada",
        "apiBaseUrl": "https://api.tiny.com.br/public-api/v3/",
        "redirectUri": os.getenv("OLIST_REDIRECT_URI", "http://localhost:3500/olist/callback"),
        "authMode": "OAuth 2 Authorization Code",
        "nextStep": "Implementar a conexão OAuth real com a conta Olist.",
    }
