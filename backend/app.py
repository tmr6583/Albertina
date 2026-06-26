from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:
    psycopg = None
    dict_row = None


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
SQLITE_DB_PATH = DATA_DIR / "albertina.db"
DATABASE_URL = os.getenv("ALBERTINA_DATABASE_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SESSION_DURATION_HOURS = 12
OAUTH_STATE_DURATION_MINUTES = 10
ACCESS_TOKEN_FALLBACK_SECONDS = 4 * 60 * 60
REFRESH_TOKEN_FALLBACK_SECONDS = 24 * 60 * 60
POSTGRES_PREFIXES = ("postgres://", "postgresql://")
DB_ENGINE = "postgresql" if DATABASE_URL.lower().startswith(POSTGRES_PREFIXES) else "sqlite"
OLIST_AUTH_URL = "https://accounts.tiny.com.br/realms/tiny/protocol/openid-connect/auth"
OLIST_TOKEN_URL = "https://accounts.tiny.com.br/realms/tiny/protocol/openid-connect/token"
OLIST_API_TEST_RESOURCE = "categorias/todas"
RowData = Mapping[str, Any]

SQLITE_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS olist_settings (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  client_secret TEXT NOT NULL,
  redirect_uri TEXT NOT NULL,
  api_base_url TEXT NOT NULL,
  auth_mode TEXT NOT NULL,
  status TEXT NOT NULL,
  token_status TEXT NOT NULL,
  message TEXT NOT NULL,
  access_token TEXT,
  refresh_token TEXT,
  access_token_expires_at TEXT,
  refresh_token_expires_at TEXT,
  token_type TEXT,
  scope TEXT,
  oauth_state TEXT,
  oauth_state_expires_at TEXT,
  last_callback_at TEXT,
  last_connect_attempt_at TEXT,
  last_token_refresh_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS connection_logs (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  event TEXT NOT NULL,
  status TEXT NOT NULL,
  description TEXT NOT NULL,
  tone TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

POSTGRES_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL,
      status TEXT NOT NULL,
      initials TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL,
      last_access_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      token_hash TEXT NOT NULL UNIQUE,
      created_at TIMESTAMPTZ NOT NULL,
      expires_at TIMESTAMPTZ NOT NULL,
      revoked_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audits (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      description TEXT NOT NULL,
      tone TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS olist_settings (
      id TEXT PRIMARY KEY,
      client_id TEXT NOT NULL,
      client_secret TEXT NOT NULL,
      redirect_uri TEXT NOT NULL,
      api_base_url TEXT NOT NULL,
      auth_mode TEXT NOT NULL,
      status TEXT NOT NULL,
      token_status TEXT NOT NULL,
      message TEXT NOT NULL,
      access_token TEXT,
      refresh_token TEXT,
      access_token_expires_at TIMESTAMPTZ,
      refresh_token_expires_at TIMESTAMPTZ,
      token_type TEXT,
      scope TEXT,
      oauth_state TEXT,
      oauth_state_expires_at TIMESTAMPTZ,
      last_callback_at TIMESTAMPTZ,
      last_connect_attempt_at TIMESTAMPTZ,
      last_token_refresh_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS connection_logs (
      id TEXT PRIMARY KEY,
      provider TEXT NOT NULL,
      event TEXT NOT NULL,
      status TEXT NOT NULL,
      description TEXT NOT NULL,
      tone TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_audits_created_at ON audits (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_connection_logs_created_at ON connection_logs (created_at DESC)",
]

POSTGRES_OLIST_ALTER_STATEMENTS = [
    "ALTER TABLE olist_settings ADD COLUMN IF NOT EXISTS access_token_expires_at TIMESTAMPTZ",
    "ALTER TABLE olist_settings ADD COLUMN IF NOT EXISTS refresh_token_expires_at TIMESTAMPTZ",
    "ALTER TABLE olist_settings ADD COLUMN IF NOT EXISTS token_type TEXT",
    "ALTER TABLE olist_settings ADD COLUMN IF NOT EXISTS scope TEXT",
    "ALTER TABLE olist_settings ADD COLUMN IF NOT EXISTS oauth_state TEXT",
    "ALTER TABLE olist_settings ADD COLUMN IF NOT EXISTS oauth_state_expires_at TIMESTAMPTZ",
    "ALTER TABLE olist_settings ADD COLUMN IF NOT EXISTS last_callback_at TIMESTAMPTZ",
]

SQLITE_OLIST_MISSING_COLUMNS = {
    "access_token_expires_at": "TEXT",
    "refresh_token_expires_at": "TEXT",
    "token_type": "TEXT",
    "scope": "TEXT",
    "oauth_state": "TEXT",
    "oauth_state_expires_at": "TEXT",
    "last_callback_at": "TEXT",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def to_db_timestamp(value: datetime | None = None) -> datetime | str:
    actual = value or utc_now()
    return actual if DB_ENGINE == "postgresql" else actual.isoformat()


def parse_timestamp(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Valor de timestamp não suportado: {value!r}")


def normalize_timestamp(value: Any, fallback: str | None = None) -> str:
    if value in {None, ""}:
        if fallback is None:
            raise ValueError("Timestamp obrigatório ausente.")
        return fallback
    if isinstance(value, datetime):
        normalized = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.isoformat()
    return str(value)


def future_timestamp(seconds: int) -> datetime:
    return utc_now() + timedelta(seconds=seconds)


def sqlite_table_columns(db: sqlite3.Connection, table_name: str) -> set[str]:
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def request_form_json(url: str, payload: Mapping[str, str]) -> dict[str, Any]:
    encoded = urlencode(payload).encode("utf-8")
    request = Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        try:
            payload_data = json.loads(error_body)
        except json.JSONDecodeError as decode_error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao consultar a Olist: {error_body or error.reason}",
            ) from decode_error

        detail = (
            payload_data.get("error_description")
            or payload_data.get("error")
            or payload_data.get("message")
            or "A Olist recusou a operação OAuth."
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(detail)) from error
    except URLError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Não foi possível alcançar o provedor OAuth da Olist: {error.reason}",
        ) from error

    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A Olist retornou uma resposta OAuth inválida.",
        ) from error


class OlistApiRequestError(Exception):
    def __init__(self, detail: str, *, unauthorized: bool = False):
        super().__init__(detail)
        self.detail = detail
        self.unauthorized = unauthorized


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
) -> tuple[Any, dict[str, str]]:
    request = Request(url, headers=dict(headers or {}), method=method)
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            response_headers = {key: value for key, value in response.headers.items()}
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        detail = error_body or error.reason
        try:
            payload_data = json.loads(error_body) if error_body else {}
        except json.JSONDecodeError:
            payload_data = {}

        detail = str(
            payload_data.get("message")
            or payload_data.get("error_description")
            or payload_data.get("error")
            or detail
            or "A API da Olist recusou a solicitação."
        )
        raise OlistApiRequestError(detail, unauthorized=error.code in {401, 403}) from error
    except URLError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Não foi possível alcançar a API da Olist: {error.reason}",
        ) from error

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A API da Olist retornou uma resposta JSON inválida.",
        ) from error

    if not isinstance(payload, (dict, list)):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A API da Olist retornou um formato de payload inesperado.",
        )

    return payload, response_headers


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


def row_value(row: RowData, key: str) -> Any:
    return row[key]


def format_user(row: RowData) -> dict[str, Any]:
    return {
        "id": str(row_value(row, "id")),
        "email": row_value(row, "email"),
        "role": row_value(row, "role"),
        "status": row_value(row, "status"),
        "createdAt": normalize_timestamp(row_value(row, "created_at")),
        "lastAccess": normalize_timestamp(row_value(row, "last_access_at"), fallback="Nunca acessou"),
        "initials": row_value(row, "initials"),
    }


def format_audit(row: RowData) -> dict[str, Any]:
    return {
        "id": str(row_value(row, "id")),
        "title": row_value(row, "title"),
        "description": row_value(row, "description"),
        "time": normalize_timestamp(row_value(row, "created_at")),
        "tone": row_value(row, "tone"),
    }


def format_connection_log(row: RowData) -> dict[str, Any]:
    return {
        "id": str(row_value(row, "id")),
        "title": f"{row_value(row, 'provider')} - {row_value(row, 'event')}",
        "description": row_value(row, "description"),
        "time": normalize_timestamp(row_value(row, "created_at")),
        "tone": row_value(row, "tone"),
        "status": row_value(row, "status"),
    }


def build_database_summary() -> dict[str, Any]:
    if DB_ENGINE != "postgresql":
        with get_db() as db:
            user_total = row_value(fetchone(db, "SELECT COUNT(*) AS total FROM users"), "total")
        return {
            "provider": "SQLite",
            "status": "Ativo",
            "database": SQLITE_DB_PATH.name,
            "host": "Local",
            "users": user_total,
            "detail": "Persistência local em arquivo SQLite.",
        }

    parsed = urlparse(DATABASE_URL)
    with get_db() as db:
        user_total = row_value(fetchone(db, "SELECT COUNT(*) AS total FROM users"), "total")

    host_label = parsed.hostname or "Supabase"
    provider = "Supabase" if "supabase.co" in host_label else "PostgreSQL"
    database_name = parsed.path.removeprefix("/") or "postgres"
    return {
        "provider": provider,
        "status": "Conectado",
        "database": database_name,
        "host": host_label,
        "users": user_total,
        "detail": "Conexão validada para persistência de usuários, sessões e auditoria.",
    }


def derive_olist_connection_state(row: RowData) -> tuple[str, str, str]:
    stored_status = str(row_value(row, "status") or "").strip()
    stored_token_status = str(row_value(row, "token_status") or "").strip()
    stored_message = str(row_value(row, "message") or "").strip()
    client_secret = str(row_value(row, "client_secret") or "").strip()
    refresh_token = str(row_value(row, "refresh_token") or "").strip()
    access_token = str(row_value(row, "access_token") or "").strip()
    connect_attempt = row_value(row, "last_connect_attempt_at")

    if refresh_token and stored_status and stored_token_status and stored_message:
        return (stored_status, stored_token_status, stored_message)

    if access_token and stored_status and stored_token_status and stored_message:
        return (stored_status, stored_token_status, stored_message)

    if stored_status.startswith("Falha") and stored_token_status and stored_message:
        return (stored_status, stored_token_status, stored_message)

    if not client_secret:
        return (
            "Pendente de Client Secret",
            "Não conectado",
            "Informe o Client Secret para preparar a conexão OAuth com a Olist.",
        )

    if refresh_token:
        return (
            "Conectada",
            "Refresh token disponível",
            "A conexão OAuth possui refresh token persistido e está pronta para renovação.",
        )

    if access_token:
        return (
            "Conectada parcialmente",
            "Access token disponível",
            "Existe access token persistido, mas o refresh token ainda não foi registrado.",
        )

    if connect_attempt:
        return (
            "Aguardando autorização",
            "OAuth pendente",
            "Configure a Redirect URL no ERP Olist e conclua a autorização da aplicação.",
        )

    return (
        "Pronta para conectar",
        "Sem token",
        "O Client Secret está salvo. O próximo passo é conectar a aplicação na Olist.",
    )


def build_olist_settings_payload(row: RowData) -> dict[str, Any]:
    status_value, token_status, message = derive_olist_connection_state(row)
    return {
        "status": status_value,
        "tokenStatus": token_status,
        "clientId": row_value(row, "client_id"),
        "clientSecret": row_value(row, "client_secret"),
        "redirectUri": row_value(row, "redirect_uri"),
        "redirectInstruction": (
            "Configure exatamente esta URL de redirecionamento no ERP Olist para concluir a autorização."
        ),
        "apiBaseUrl": row_value(row, "api_base_url"),
        "authMode": row_value(row, "auth_mode"),
        "message": message,
        "accessTokenExpiresAt": normalize_timestamp(
            row_value(row, "access_token_expires_at"),
            fallback="Não disponível",
        ),
        "refreshTokenExpiresAt": normalize_timestamp(
            row_value(row, "refresh_token_expires_at"),
            fallback="Não disponível",
        ),
        "lastCallbackAt": normalize_timestamp(
            row_value(row, "last_callback_at"),
            fallback="Nenhum callback recebido",
        ),
        "lastConnectAttemptAt": normalize_timestamp(
            row_value(row, "last_connect_attempt_at"),
            fallback="Nenhuma tentativa registrada",
        ),
        "lastTokenRefreshAt": normalize_timestamp(
            row_value(row, "last_token_refresh_at"),
            fallback="Nenhuma renovação registrada",
        ),
        "scope": row_value(row, "scope") or "openid",
        "tokenType": row_value(row, "token_type") or "Bearer",
        "hasRefreshToken": bool(str(row_value(row, "refresh_token") or "").strip()),
    }


def build_olist_authorization_url(row: RowData, state: str) -> str:
    query = urlencode(
        {
            "client_id": row_value(row, "client_id"),
            "redirect_uri": row_value(row, "redirect_uri"),
            "scope": "openid",
            "response_type": "code",
            "state": state,
        }
    )
    return f"{OLIST_AUTH_URL}?{query}"


def build_olist_api_url(row: RowData, resource_path: str) -> str:
    base_url = str(row_value(row, "api_base_url") or "").strip() or "https://api.tiny.com.br/public-api/v3/"
    normalized_base_url = base_url.rstrip("/") + "/"
    normalized_resource_path = resource_path.lstrip("/")
    return f"{normalized_base_url}{normalized_resource_path}"


def summarize_olist_api_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        return {
            "rootKeys": [],
            "categoryCount": len(payload),
            "sampleCategory": payload[0] if payload else None,
        }

    root_keys = list(payload.keys())
    category_items = payload.get("itens") or payload.get("items") or payload.get("categorias") or []
    category_count = len(category_items) if isinstance(category_items, list) else None
    return {
        "rootKeys": root_keys,
        "categoryCount": category_count,
        "sampleCategory": category_items[0] if category_count else None,
    }


def compile_query(query: str) -> str:
    return query.replace("?", "%s") if DB_ENGINE == "postgresql" else query


def execute(db: Any, query: str, params: Iterable[Any] = ()) -> Any:
    return db.execute(compile_query(query), tuple(params))


def fetchone(db: Any, query: str, params: Iterable[Any] = ()) -> RowData | None:
    cursor = execute(db, query, params)
    try:
        return cursor.fetchone()
    finally:
        cursor.close()


def fetchall(db: Any, query: str, params: Iterable[Any] = ()) -> list[RowData]:
    cursor = execute(db, query, params)
    try:
        return cursor.fetchall()
    finally:
        cursor.close()


@contextmanager
def get_sqlite_db() -> Generator[sqlite3.Connection, None, None]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(SQLITE_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def get_postgres_db() -> Generator[Any, None, None]:
    if psycopg is None or dict_row is None:
        raise RuntimeError(
            "O suporte a PostgreSQL requer o pacote psycopg. Instale com: pip install -r backend/requirements.txt"
        )
    connection = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def get_db() -> Generator[Any, None, None]:
    if DB_ENGINE == "postgresql":
        with get_postgres_db() as connection:
            yield connection
        return

    with get_sqlite_db() as connection:
        yield connection


def create_tables() -> None:
    if DB_ENGINE == "postgresql":
        with get_db() as db:
            for statement in POSTGRES_SCHEMA_STATEMENTS:
                execute(db, statement)
            for statement in POSTGRES_OLIST_ALTER_STATEMENTS:
                execute(db, statement)
        return

    with get_db() as db:
        db.executescript(SQLITE_SCHEMA)
        existing_columns = sqlite_table_columns(db, "olist_settings")
        for column_name, column_type in SQLITE_OLIST_MISSING_COLUMNS.items():
            if column_name not in existing_columns:
                db.execute(f"ALTER TABLE olist_settings ADD COLUMN {column_name} {column_type}")


def append_audit(db: Any, title: str, description: str, tone: str = "neutral") -> None:
    execute(
        db,
        """
        INSERT INTO audits (id, title, description, tone, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(uuid4()), title, description, tone, to_db_timestamp()),
    )


def append_connection_log(
    db: Any,
    event: str,
    status_text: str,
    description: str,
    tone: str = "neutral",
    provider: str = "Olist",
) -> None:
    execute(
        db,
        """
        INSERT INTO connection_logs (id, provider, event, status, description, tone, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid4()), provider, event, status_text, description, tone, to_db_timestamp()),
    )


def migrate_sqlite_to_postgres_if_needed() -> None:
    if DB_ENGINE != "postgresql" or not SQLITE_DB_PATH.exists():
        return

    with get_db() as target_db:
        counts = {
            "users": row_value(fetchone(target_db, "SELECT COUNT(*) AS total FROM users"), "total"),
            "sessions": row_value(fetchone(target_db, "SELECT COUNT(*) AS total FROM sessions"), "total"),
            "audits": row_value(fetchone(target_db, "SELECT COUNT(*) AS total FROM audits"), "total"),
        }
        if any(counts.values()):
            return

    source = sqlite3.connect(SQLITE_DB_PATH)
    source.row_factory = sqlite3.Row
    try:
        users = source.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
        sessions = source.execute("SELECT * FROM sessions ORDER BY created_at ASC").fetchall()
        audits = source.execute("SELECT * FROM audits ORDER BY created_at ASC").fetchall()
    finally:
        source.close()

    if not users and not sessions and not audits:
        return

    with get_db() as target_db:
        for row in users:
            execute(
                target_db,
                """
                INSERT INTO users (id, email, password_hash, role, status, initials, created_at, updated_at, last_access_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    row["id"],
                    row["email"],
                    row["password_hash"],
                    row["role"],
                    row["status"],
                    row["initials"],
                    parse_timestamp(row["created_at"]),
                    parse_timestamp(row["updated_at"]),
                    parse_timestamp(row["last_access_at"]),
                ),
            )

        for row in sessions:
            execute(
                target_db,
                """
                INSERT INTO sessions (id, user_id, token_hash, created_at, expires_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    row["id"],
                    row["user_id"],
                    row["token_hash"],
                    parse_timestamp(row["created_at"]),
                    parse_timestamp(row["expires_at"]),
                    parse_timestamp(row["revoked_at"]),
                ),
            )

        for row in audits:
            execute(
                target_db,
                """
                INSERT INTO audits (id, title, description, tone, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    row["id"],
                    row["title"],
                    row["description"],
                    row["tone"],
                    parse_timestamp(row["created_at"]),
                ),
            )

        append_audit(
            target_db,
            "Migração local concluída",
            "Dados existentes em SQLite foram copiados automaticamente para o PostgreSQL configurado.",
            "accent",
        )


def bootstrap_olist_settings() -> None:
    now_value = to_db_timestamp()
    default_redirect_uri = os.getenv("OLIST_REDIRECT_URI", "http://localhost:3500/olist/callback").strip()
    default_client_id = os.getenv("OLIST_CLIENT_ID", "").strip()

    with get_db() as db:
        settings = fetchone(db, "SELECT * FROM olist_settings WHERE id = ?", ("default",))
        if settings is not None:
            execute(
                db,
                """
                UPDATE olist_settings
                SET client_id = ?, redirect_uri = ?, api_base_url = ?, auth_mode = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    default_client_id or row_value(settings, "client_id"),
                    default_redirect_uri or row_value(settings, "redirect_uri"),
                    "https://api.tiny.com.br/public-api/v3/",
                    "OAuth 2 Authorization Code",
                    now_value,
                    "default",
                ),
            )
            return

        execute(
            db,
            """
            INSERT INTO olist_settings (
              id,
              client_id,
              client_secret,
              redirect_uri,
              api_base_url,
              auth_mode,
              status,
              token_status,
              message,
              token_type,
              scope,
              created_at,
              updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "default",
                default_client_id,
                "",
                default_redirect_uri,
                "https://api.tiny.com.br/public-api/v3/",
                "OAuth 2 Authorization Code",
                "Pendente de Client Secret",
                "Não conectado",
                "Informe o Client Secret para preparar a conexão OAuth com a Olist.",
                "Bearer",
                "openid",
                now_value,
                now_value,
            ),
        )
        append_audit(
            db,
            "Configuração Olist inicializada",
            "A base de configuração da conexão Olist foi criada para uso administrativo.",
            "accent",
        )
        append_connection_log(
            db,
            "Configuração inicializada",
            "Pronta",
            "A base administrativa da conexão Olist foi criada no banco de dados.",
            "accent",
        )


def bootstrap_admin() -> None:
    admin_email = os.getenv("ALBERTINA_ADMIN_EMAIL", "admin@empresa.com").strip().lower()
    admin_password = os.getenv("ALBERTINA_ADMIN_PASSWORD", "Betin@01012023").strip()
    created_at = to_db_timestamp()

    with get_db() as db:
        user_count = row_value(fetchone(db, "SELECT COUNT(*) AS total FROM users"), "total")
        if user_count:
            return

        execute(
            db,
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


class OlistSettingsPayload(BaseModel):
    clientSecret: str = ""


class OlistCallbackPayload(BaseModel):
    code: str | None = None
    state: str | None = None
    error: str | None = None
    error_description: str | None = None


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


app = FastAPI(title="Albertina API", version="0.2.0")
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
    migrate_sqlite_to_postgres_if_needed()
    bootstrap_admin()
    bootstrap_olist_settings()


def get_olist_settings(db: Any) -> RowData:
    row = fetchone(db, "SELECT * FROM olist_settings WHERE id = ?", ("default",))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A configuração da Olist ainda não foi inicializada.",
        )
    return row


def get_current_user(authorization: str | None = Header(default=None)) -> RowData:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou ausente.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    token_hash = hash_secret(token)
    now_value = to_db_timestamp()

    with get_db() as db:
        row = fetchone(
            db,
            """
            SELECT users.*
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
              AND sessions.revoked_at IS NULL
              AND sessions.expires_at > ?
            """,
            (token_hash, now_value),
        )

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sessão expirada ou inválida.",
            )

        if row_value(row, "status") != "Ativo":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O usuário autenticado está inativo.",
            )

        return row


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "database": DB_ENGINE}


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginPayload) -> dict[str, Any]:
    email = validate_email(payload.email)
    password = payload.password.strip()

    with get_db() as db:
        user = fetchone(db, "SELECT * FROM users WHERE email = ?", (email,))
        if user is None or not verify_password(password, row_value(user, "password_hash")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="E-mail ou senha inválidos.",
            )

        if row_value(user, "status") != "Ativo":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O usuário está inativo.",
            )

        token = secrets.token_urlsafe(32)
        now = utc_now()
        expires_at = now + timedelta(hours=SESSION_DURATION_HOURS)
        execute(
            db,
            """
            INSERT INTO sessions (id, user_id, token_hash, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                row_value(user, "id"),
                hash_secret(token),
                to_db_timestamp(now),
                to_db_timestamp(expires_at),
            ),
        )
        execute(
            db,
            "UPDATE users SET last_access_at = ?, updated_at = ? WHERE id = ?",
            (to_db_timestamp(now), to_db_timestamp(now), row_value(user, "id")),
        )
        append_audit(
            db,
            "Login realizado",
            f"O usuário {email} acessou a área administrativa da aplicação.",
            "success",
        )
        refreshed = fetchone(db, "SELECT * FROM users WHERE id = ?", (row_value(user, "id"),))

        return {"token": token, "user": format_user(refreshed)}


@app.get("/api/auth/me", response_model=UserResponse)
def me(current_user: RowData = Depends(get_current_user)) -> dict[str, Any]:
    return format_user(current_user)


@app.post("/api/auth/logout")
def logout(
    current_user: RowData = Depends(get_current_user),
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    token = authorization.removeprefix("Bearer ").strip()
    with get_db() as db:
        execute(
            db,
            "UPDATE sessions SET revoked_at = ? WHERE token_hash = ?",
            (to_db_timestamp(), hash_secret(token)),
        )
        append_audit(
            db,
            "Logout realizado",
            f"O usuário {row_value(current_user, 'email')} encerrou a sessão atual.",
            "neutral",
        )

    return {"status": "ok"}


@app.get("/api/users", response_model=list[UserResponse])
def list_users(current_user: RowData = Depends(get_current_user)) -> list[dict[str, Any]]:
    del current_user
    with get_db() as db:
        rows = fetchall(db, "SELECT * FROM users ORDER BY created_at DESC, email ASC")
        return [format_user(row) for row in rows]


@app.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserPayload,
    current_user: RowData = Depends(get_current_user),
) -> dict[str, Any]:
    email = validate_email(payload.email)
    password = payload.password.strip()
    status_value = payload.status.strip().title()
    if status_value not in {"Ativo", "Inativo"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O status deve ser Ativo ou Inativo.",
        )

    now = to_db_timestamp()
    user_id = str(uuid4())

    with get_db() as db:
        exists = fetchone(db, "SELECT 1 AS found FROM users WHERE email = ?", (email,))
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe um usuário com este e-mail.",
            )

        execute(
            db,
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
            f"O usuário {row_value(current_user, 'email')} criou a conta {email}.",
            "success",
        )
        created = fetchone(db, "SELECT * FROM users WHERE id = ?", (user_id,))
        return format_user(created)


@app.patch("/api/users/{user_id}/password")
def update_password(
    user_id: str,
    payload: PasswordPayload,
    current_user: RowData = Depends(get_current_user),
) -> dict[str, str]:
    if payload.password != payload.confirmPassword:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A confirmação da senha não confere.",
        )

    with get_db() as db:
        user = fetchone(db, "SELECT * FROM users WHERE id = ?", (user_id,))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

        execute(
            db,
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (hash_password(payload.password), to_db_timestamp(), user_id),
        )
        append_audit(
            db,
            "Senha atualizada",
            f"O usuário {row_value(current_user, 'email')} alterou a senha da conta {row_value(user, 'email')}.",
            "accent",
        )

    return {"status": "ok"}


@app.patch("/api/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: str,
    payload: StatusPayload,
    current_user: RowData = Depends(get_current_user),
) -> dict[str, Any]:
    status_value = payload.status.strip().title()
    if status_value not in {"Ativo", "Inativo"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O status deve ser Ativo ou Inativo.",
        )

    if user_id == row_value(current_user, "id") and status_value == "Inativo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido desativar o usuário autenticado.",
        )

    with get_db() as db:
        user = fetchone(db, "SELECT * FROM users WHERE id = ?", (user_id,))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

        execute(
            db,
            "UPDATE users SET status = ?, updated_at = ? WHERE id = ?",
            (status_value, to_db_timestamp(), user_id),
        )
        if status_value == "Inativo":
            execute(
                db,
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (to_db_timestamp(), user_id),
            )
            append_audit(
                db,
                "Usuário desativado",
                f"O usuário {row_value(current_user, 'email')} desativou a conta {row_value(user, 'email')}.",
                "accent",
            )
        else:
            append_audit(
                db,
                "Usuário ativado",
                f"O usuário {row_value(current_user, 'email')} ativou a conta {row_value(user, 'email')}.",
                "success",
            )

        updated = fetchone(db, "SELECT * FROM users WHERE id = ?", (user_id,))
        return format_user(updated)


@app.delete("/api/users/{user_id}")
def delete_user(
    user_id: str,
    current_user: RowData = Depends(get_current_user),
) -> dict[str, str]:
    if user_id == row_value(current_user, "id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido excluir o usuário autenticado.",
        )

    with get_db() as db:
        user = fetchone(db, "SELECT * FROM users WHERE id = ?", (user_id,))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

        execute(db, "DELETE FROM users WHERE id = ?", (user_id,))
        append_audit(
            db,
            "Usuário excluído",
            f"O usuário {row_value(current_user, 'email')} removeu a conta {row_value(user, 'email')}.",
            "danger",
        )

    return {"status": "ok"}


@app.get("/api/audit", response_model=list[AuditResponse])
def list_audits(current_user: RowData = Depends(get_current_user)) -> list[dict[str, Any]]:
    del current_user
    with get_db() as db:
        rows = fetchall(db, "SELECT * FROM audits ORDER BY created_at DESC LIMIT 50")
        return [format_audit(row) for row in rows]


def olist_token_expiration(token_payload: Mapping[str, Any], key: str, fallback_seconds: int) -> datetime:
    try:
        seconds = int(token_payload.get(key) or fallback_seconds)
    except (TypeError, ValueError):
        seconds = fallback_seconds
    return future_timestamp(seconds)


def has_valid_olist_access_token(settings: RowData) -> bool:
    access_token = str(row_value(settings, "access_token") or "").strip()
    if not access_token:
        return False

    expires_at = parse_timestamp(row_value(settings, "access_token_expires_at"))
    if expires_at is None:
        return True

    return expires_at > utc_now() + timedelta(seconds=30)


def persist_olist_tokens(
    db: Any,
    settings: RowData,
    token_payload: Mapping[str, Any],
    *,
    detail_message: str,
    update_refresh_timestamp: bool,
) -> RowData:
    now_value = to_db_timestamp()
    access_token = str(token_payload.get("access_token") or "").strip()
    refresh_token = str(token_payload.get("refresh_token") or row_value(settings, "refresh_token") or "").strip()
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A Olist não retornou access_token na resposta OAuth.",
        )

    execute(
        db,
        """
        UPDATE olist_settings
        SET access_token = ?,
            refresh_token = ?,
            access_token_expires_at = ?,
            refresh_token_expires_at = ?,
            token_type = ?,
            scope = ?,
            oauth_state = ?,
            oauth_state_expires_at = ?,
            status = ?,
            token_status = ?,
            message = ?,
            last_callback_at = ?,
            last_token_refresh_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            access_token,
            refresh_token,
            to_db_timestamp(olist_token_expiration(token_payload, "expires_in", ACCESS_TOKEN_FALLBACK_SECONDS)),
            to_db_timestamp(
                olist_token_expiration(token_payload, "refresh_expires_in", REFRESH_TOKEN_FALLBACK_SECONDS)
            ),
            str(token_payload.get("token_type") or "Bearer"),
            str(token_payload.get("scope") or "openid"),
            None,
            None,
            "Conectada",
            "Token ativo",
            detail_message,
            now_value,
            now_value if update_refresh_timestamp else row_value(settings, "last_token_refresh_at"),
            now_value,
            "default",
        ),
    )
    return get_olist_settings(db)


def renew_olist_token_in_db(
    db: Any,
    settings: RowData,
    *,
    actor_email: str | None = None,
    append_logs: bool,
) -> RowData:
    refresh_token = str(row_value(settings, "refresh_token") or "").strip()
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ainda não existe refresh token registrado. Conclua a conexão OAuth primeiro.",
        )

    try:
        token_payload = request_form_json(
            OLIST_TOKEN_URL,
            {
                "grant_type": "refresh_token",
                "client_id": str(row_value(settings, "client_id") or ""),
                "client_secret": str(row_value(settings, "client_secret") or ""),
                "refresh_token": refresh_token,
            },
        )
    except HTTPException as error:
        execute(
            db,
            """
            UPDATE olist_settings
            SET status = ?, token_status = ?, message = ?, updated_at = ?
            WHERE id = ?
            """,
            ("Conectada com alerta", "Falha na renovação", error.detail, to_db_timestamp(), "default"),
        )
        if append_logs:
            append_connection_log(
                db,
                "Falha ao renovar token",
                "Falha na renovação",
                f"A Olist recusou a renovação do refresh token: {error.detail}",
                "danger",
            )
        raise

    updated = persist_olist_tokens(
        db,
        settings,
        token_payload,
        detail_message="O refresh token foi utilizado com sucesso para renovar a sessão OAuth da Olist.",
        update_refresh_timestamp=True,
    )

    if append_logs:
        actor_prefix = f" por {actor_email}" if actor_email else ""
        append_audit(
            db,
            "Renovação de token registrada",
            f"O token OAuth da Olist foi renovado com sucesso{actor_prefix}.",
            "accent",
        )
        append_connection_log(
            db,
            "Token renovado",
            "Conectada",
            "A Olist aceitou o refresh token e retornou um novo access token para a integração.",
            "accent",
        )

    return updated


def ensure_olist_api_ready(db: Any, settings: RowData) -> RowData:
    client_id = str(row_value(settings, "client_id") or "").strip()
    client_secret = str(row_value(settings, "client_secret") or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Configure Client ID e Client Secret antes de consumir a API da Olist.",
        )

    if has_valid_olist_access_token(settings):
        return settings

    if str(row_value(settings, "refresh_token") or "").strip():
        return renew_olist_token_in_db(db, settings, append_logs=False)

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Conclua a autorização OAuth da Olist antes de consumir a API.",
    )


def request_olist_api_resource(
    db: Any,
    settings: RowData,
    resource_path: str,
) -> tuple[Any, dict[str, str], RowData]:
    active_settings = ensure_olist_api_ready(db, settings)
    access_token = str(row_value(active_settings, "access_token") or "").strip()
    url = build_olist_api_url(active_settings, resource_path)

    def perform_request(current_token: str) -> tuple[Any, dict[str, str]]:
        return request_json(
            url,
            headers={
                "Authorization": f"Bearer {current_token}",
                "Accept": "application/json",
            },
        )

    try:
        payload, response_headers = perform_request(access_token)
    except OlistApiRequestError as error:
        has_refresh_token = bool(str(row_value(active_settings, "refresh_token") or "").strip())
        if error.unauthorized and has_refresh_token:
            active_settings = renew_olist_token_in_db(db, active_settings, append_logs=False)
            access_token = str(row_value(active_settings, "access_token") or "").strip()
            try:
                payload, response_headers = perform_request(access_token)
            except OlistApiRequestError as retry_error:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"A API da Olist recusou a autenticação após renovar o token: {retry_error.detail}",
                ) from retry_error
        else:
            detail = (
                f"A API da Olist recusou a autenticação: {error.detail}"
                if error.unauthorized
                else f"A API da Olist retornou erro: {error.detail}"
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from error

    return payload, response_headers, active_settings


def get_connections_overview_payload() -> dict[str, Any]:
    with get_db() as db:
        olist_settings = get_olist_settings(db)
        logs = fetchall(db, "SELECT * FROM connection_logs ORDER BY created_at DESC LIMIT 12")
    return {
        "olist": build_olist_settings_payload(olist_settings),
        "supabase": build_database_summary(),
        "logs": [format_connection_log(row) for row in logs],
    }


@app.get("/api/connections/overview")
def connections_overview(current_user: RowData = Depends(get_current_user)) -> dict[str, Any]:
    del current_user
    return get_connections_overview_payload()


@app.get("/api/olist/overview")
def olist_overview_legacy(current_user: RowData = Depends(get_current_user)) -> dict[str, Any]:
    del current_user
    return get_connections_overview_payload()


@app.patch("/api/connections/olist/settings")
def update_olist_settings(
    payload: OlistSettingsPayload,
    current_user: RowData = Depends(get_current_user),
) -> dict[str, Any]:
    client_secret = payload.clientSecret.strip()
    now_value = to_db_timestamp()

    with get_db() as db:
        settings = get_olist_settings(db)
        status_value, token_status, message = derive_olist_connection_state(
            {**settings, "client_secret": client_secret}
        )
        execute(
            db,
            """
            UPDATE olist_settings
            SET client_secret = ?,
                access_token = ?,
                refresh_token = ?,
                access_token_expires_at = ?,
                refresh_token_expires_at = ?,
                oauth_state = ?,
                oauth_state_expires_at = ?,
                status = ?,
                token_status = ?,
                message = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                client_secret,
                None,
                None,
                None,
                None,
                None,
                None,
                status_value,
                token_status,
                message,
                now_value,
                "default",
            ),
        )
        append_audit(
            db,
            "Client Secret atualizado",
            f"O usuário {row_value(current_user, 'email')} atualizou o Client Secret da conexão Olist.",
            "accent",
        )
        append_connection_log(
            db,
            "Client Secret atualizado",
            status_value,
            f"O Client Secret da aplicação Olist foi atualizado por {row_value(current_user, 'email')}.",
            "accent",
        )
        updated = get_olist_settings(db)

    return build_olist_settings_payload(updated)


@app.post("/api/connections/olist/connect")
def connect_olist(current_user: RowData = Depends(get_current_user)) -> dict[str, Any]:
    now = utc_now()
    now_value = to_db_timestamp(now)

    with get_db() as db:
        settings = get_olist_settings(db)
        client_id = str(row_value(settings, "client_id") or "").strip()
        client_secret = str(row_value(settings, "client_secret") or "").strip()
        redirect_uri = str(row_value(settings, "redirect_uri") or "").strip()
        if not client_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Configure o Client ID da aplicação Olist antes de conectar.",
            )
        if not client_secret:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Informe o Client Secret antes de conectar com a Olist.",
            )
        if not redirect_uri:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A Redirect URL da Olist não está configurada.",
            )

        state_value = secrets.token_urlsafe(24)
        authorization_url = build_olist_authorization_url(settings, state_value)

        execute(
            db,
            """
            UPDATE olist_settings
            SET oauth_state = ?,
                oauth_state_expires_at = ?,
                status = ?,
                token_status = ?,
                message = ?,
                last_connect_attempt_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                state_value,
                to_db_timestamp(now + timedelta(minutes=OAUTH_STATE_DURATION_MINUTES)),
                "Aguardando autorização",
                "OAuth pendente",
                "Configure a Redirect URL no ERP Olist e conclua a autorização da aplicação.",
                now_value,
                now_value,
                "default",
            ),
        )
        append_audit(
            db,
            "Conexão Olist iniciada",
            (
                f"O usuário {row_value(current_user, 'email')} iniciou a preparação da conexão Olist. "
                "A autorização OAuth ainda depende da configuração e confirmação no ERP."
            ),
            "success",
        )
        append_connection_log(
            db,
            "URL de autorização gerada",
            "OAuth pendente",
            "A URL oficial de autorização foi gerada e a aplicação aguarda o retorno da Olist.",
            "success",
        )
        updated = get_olist_settings(db)

    return {
        "status": "ok",
        "authorizationUrl": authorization_url,
        "olist": build_olist_settings_payload(updated),
        "detail": "A URL de autorização foi gerada. Redirecione o usuário para concluir a autorização na Olist.",
    }


@app.post("/api/connections/olist/callback")
def complete_olist_callback(
    payload: OlistCallbackPayload,
    current_user: RowData = Depends(get_current_user),
) -> dict[str, Any]:
    now = utc_now()
    updated: RowData | None = None
    deferred_error: HTTPException | None = None
    with get_db() as db:
        settings = get_olist_settings(db)
        stored_state = str(row_value(settings, "oauth_state") or "").strip()
        state_expires_at = parse_timestamp(row_value(settings, "oauth_state_expires_at"))

        if payload.error:
            detail = payload.error_description or payload.error
            execute(
                db,
                """
                UPDATE olist_settings
                SET oauth_state = ?, oauth_state_expires_at = ?, status = ?, token_status = ?, message = ?, updated_at = ?
                WHERE id = ?
                """,
                (None, None, "Falha na autorização", "OAuth recusado", str(detail), to_db_timestamp(now), "default"),
            )
            append_connection_log(
                db,
                "Callback recusado",
                "OAuth recusado",
                f"A Olist retornou erro de autorização: {detail}.",
                "danger",
            )
            deferred_error = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(detail))

        elif not payload.code or not payload.state:
            append_connection_log(
                db,
                "Callback incompleto",
                "Callback inválido",
                "O retorno OAuth não trouxe code e state válidos.",
                "danger",
            )
            deferred_error = HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="O callback OAuth não trouxe code e state válidos.",
            )

        elif not stored_state or payload.state != stored_state:
            append_connection_log(
                db,
                "State inválido",
                "Callback rejeitado",
                "O callback OAuth retornou com state inválido ou ausente.",
                "danger",
            )
            deferred_error = HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="State OAuth inválido.",
            )

        elif state_expires_at is not None and state_expires_at < now:
            append_connection_log(
                db,
                "State expirado",
                "Callback expirado",
                "O callback OAuth retornou após a expiração da janela de autorização.",
                "danger",
            )
            deferred_error = HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A autorização OAuth expirou.",
            )

        if deferred_error is None:
            try:
                token_payload = request_form_json(
                    OLIST_TOKEN_URL,
                    {
                        "grant_type": "authorization_code",
                        "client_id": str(row_value(settings, "client_id") or ""),
                        "client_secret": str(row_value(settings, "client_secret") or ""),
                        "redirect_uri": str(row_value(settings, "redirect_uri") or ""),
                        "code": payload.code,
                    },
                )
            except HTTPException as error:
                execute(
                    db,
                    """
                    UPDATE olist_settings
                    SET oauth_state = ?, oauth_state_expires_at = ?, status = ?, token_status = ?, message = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        None,
                        None,
                        "Falha na troca do código",
                        "OAuth com erro",
                        error.detail,
                        to_db_timestamp(now),
                        "default",
                    ),
                )
                append_connection_log(
                    db,
                    "Falha ao trocar código",
                    "OAuth com erro",
                    f"A Olist recusou a troca do código de autorização: {error.detail}",
                    "danger",
                )
                deferred_error = HTTPException(status_code=error.status_code, detail=error.detail)
            else:
                updated = persist_olist_tokens(
                    db,
                    settings,
                    token_payload,
                    detail_message="Conexão OAuth concluída com sucesso e tokens persistidos no banco.",
                    update_refresh_timestamp=False,
                )
                append_audit(
                    db,
                    "Conexão Olist concluída",
                    f"O usuário {row_value(current_user, 'email')} concluiu a autorização OAuth com a Olist.",
                    "success",
                )
                append_connection_log(
                    db,
                    "Tokens recebidos",
                    "Conectada",
                    "A Olist retornou um código de autorização válido e os tokens foram persistidos no banco.",
                    "success",
                )

    if deferred_error is not None:
        raise deferred_error

    return {
        "status": "ok",
        "olist": build_olist_settings_payload(updated),
        "detail": "A autorização OAuth foi concluída e os tokens foram persistidos com sucesso.",
    }


@app.post("/api/olist/callback")
def complete_olist_callback_legacy(
    payload: OlistCallbackPayload,
    current_user: RowData = Depends(get_current_user),
) -> dict[str, Any]:
    return complete_olist_callback(payload, current_user)


@app.post("/api/connections/olist/renew-token")
def renew_olist_token(current_user: RowData = Depends(get_current_user)) -> dict[str, Any]:
    updated: RowData | None = None
    deferred_error: HTTPException | None = None
    with get_db() as db:
        settings = get_olist_settings(db)
        refresh_token = str(row_value(settings, "refresh_token") or "").strip()
        if not refresh_token:
            append_audit(
                db,
                "Renovação de token solicitada",
                (
                    f"O usuário {row_value(current_user, 'email')} tentou renovar o token da Olist, "
                    "mas ainda não existe refresh token persistido."
                ),
                "danger",
            )
            append_connection_log(
                db,
                "Renovação solicitada",
                "Sem refresh token",
                "A aplicação não possui refresh token persistido para renovar a sessão OAuth da Olist.",
                "danger",
            )
            current = get_olist_settings(db)
            return {
                "status": "pending",
                "olist": build_olist_settings_payload(current),
                "detail": "Ainda não existe refresh token registrado. Conclua a conexão OAuth primeiro.",
            }

        try:
            updated = renew_olist_token_in_db(
                db,
                settings,
                actor_email=str(row_value(current_user, "email")),
                append_logs=True,
            )
        except HTTPException as error:
            deferred_error = HTTPException(status_code=error.status_code, detail=error.detail)

    if deferred_error is not None:
        raise deferred_error

    return {
        "status": "ok",
        "olist": build_olist_settings_payload(updated),
        "detail": "O token OAuth da Olist foi renovado com sucesso.",
    }


@app.get("/api/connections/olist/api-test")
def test_olist_api(current_user: RowData = Depends(get_current_user)) -> dict[str, Any]:
    actor_email = str(row_value(current_user, "email"))
    with get_db() as db:
        settings = get_olist_settings(db)
        payload, response_headers, updated = request_olist_api_resource(db, settings, OLIST_API_TEST_RESOURCE)
        summary = summarize_olist_api_payload(payload)
        append_connection_log(
            db,
            "API validada",
            "Conectada",
            (
                f"O usuário {actor_email} validou a API real da Olist em "
                f"{build_olist_api_url(updated, OLIST_API_TEST_RESOURCE)}."
            ),
            "success",
        )

    return {
        "status": "ok",
        "detail": "A API real da Olist respondeu com sucesso.",
        "resource": OLIST_API_TEST_RESOURCE,
        "url": build_olist_api_url(updated, OLIST_API_TEST_RESOURCE),
        "rateLimit": {
            "limit": response_headers.get("X-RateLimit-Limit"),
            "remaining": response_headers.get("X-RateLimit-Remaining"),
            "reset": response_headers.get("X-RateLimit-Reset"),
        },
        "summary": summary,
        "olist": build_olist_settings_payload(updated),
    }
