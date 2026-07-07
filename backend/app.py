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

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from olist_extraction.service import extraction_service

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


def format_duration_human(total_seconds: float | int | None) -> str:
    if total_seconds is None:
        return "--"
    normalized_seconds = max(int(round(float(total_seconds))), 0)
    hours = normalized_seconds // 3600
    minutes = (normalized_seconds % 3600) // 60
    seconds = normalized_seconds % 60
    if hours > 0:
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    if minutes > 0:
        return f"{minutes:02d}m {seconds:02d}s"
    return f"{seconds:02d}s"


def build_duration_payload(started_at: Any, finished_at: Any) -> tuple[float | None, str]:
    started_value = parse_timestamp(started_at)
    finished_value = parse_timestamp(finished_at)
    if started_value is None or finished_value is None:
        return (None, "--")
    duration_seconds = max((finished_value - started_value).total_seconds(), 0.0)
    return (duration_seconds, format_duration_human(duration_seconds))


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


def _to_non_negative_int(value: Any) -> int:
    try:
        normalized = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(normalized, 0)


def normalize_extraction_run_details(details: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(details or {})
    source_contexts_processed = _to_non_negative_int(payload.get("sourceContextsProcessed"))
    source_contexts_total = _to_non_negative_int(payload.get("sourceContextsTotal"))
    source_contexts_remaining = max(source_contexts_total - source_contexts_processed, 0) if source_contexts_total > 0 else 0
    extracted_count = _to_non_negative_int(payload.get("extractedCount"))
    inserted_count = _to_non_negative_int(payload.get("insertedCount"))
    updated_count = _to_non_negative_int(payload.get("updatedCount"))

    payload.update(
        {
            "sourceContextsProcessed": source_contexts_processed,
            "sourceContextsTotal": source_contexts_total,
            "sourceContextsRemaining": source_contexts_remaining,
            "extractedCount": extracted_count,
            "insertedCount": inserted_count,
            "updatedCount": updated_count,
            "lineProgressLabel": (
                f"{source_contexts_processed}/{source_contexts_total}"
                if source_contexts_total > 0
                else ("0/0" if source_contexts_processed == 0 else str(source_contexts_processed))
            ),
            "lineRemainingLabel": str(source_contexts_remaining) if source_contexts_total > 0 else "--",
            "persistenceBreakdownLabel": f"{inserted_count} inseridas • {updated_count} atualizadas",
        }
    )
    return payload


def format_extraction_execution_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    runs = payload.get("runs") or []
    logs = payload.get("logs") or []
    duration_seconds, duration_label = build_duration_payload(payload.get("started_at"), payload.get("finished_at"))
    return {
        "executionId": str(payload.get("execution_id")),
        "executionType": str(payload.get("execution_type") or "incremental"),
        "startedAt": normalize_timestamp(payload.get("started_at"), fallback="Nao iniciado"),
        "finishedAt": normalize_timestamp(payload.get("finished_at"), fallback="Em andamento"),
        "durationSeconds": duration_seconds,
        "durationLabel": duration_label,
        "requestCount": int(payload.get("request_count") or 0),
        "successCount": int(payload.get("success_count") or 0),
        "errorCount": int(payload.get("error_count") or 0),
        "entityTotal": int(payload.get("entity_total") or 0),
        "entitiesSuccess": int(payload.get("entities_success") or 0),
        "entitiesCancelled": int(payload.get("entities_cancelled") or 0),
        "entitiesError": int(payload.get("entities_error") or 0),
        "entitiesRunning": int(payload.get("entities_running") or 0),
        "runs": [
            {
                "syncRunId": str(item.get("sync_run_id")),
                "entityName": item.get("entity_name"),
                "status": item.get("status"),
                "syncMode": item.get("sync_mode"),
                "executionType": item.get("execution_type"),
                "startedAt": normalize_timestamp(item.get("started_at"), fallback="Nao iniciado"),
                "finishedAt": normalize_timestamp(item.get("finished_at"), fallback="Em andamento"),
                "durationSeconds": build_duration_payload(item.get("started_at"), item.get("finished_at"))[0],
                "durationLabel": build_duration_payload(item.get("started_at"), item.get("finished_at"))[1],
                "requestCount": int(item.get("request_count") or 0),
                "successCount": int(item.get("success_count") or 0),
                "errorCount": int(item.get("error_count") or 0),
                "details": normalize_extraction_run_details(item.get("details") or {}),
            }
            for item in runs
        ],
        "logs": [
            {
                "id": str(item.get("log_id")),
                "entityName": item.get("entity_name"),
                "level": item.get("level"),
                "stage": item.get("stage"),
                "message": item.get("message"),
                "createdAt": normalize_timestamp(item.get("created_at"), fallback="Nao informado"),
                "extractedCount": int(item.get("extracted_count") or 0),
                "insertedCount": int(item.get("inserted_count") or 0),
                "updatedCount": int(item.get("updated_count") or 0),
                "errorCount": int(item.get("error_count") or 0),
                "stackTrace": item.get("stack_trace"),
            }
            for item in logs
        ],
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


def set_db_app_user_context(db: Any, user_id: str) -> None:
    if DB_ENGINE != "postgresql":
        return
    execute(db, "SELECT set_config('app.current_user_id', ?, true)", (user_id,))


def ensure_ai_layer_available(db: Any) -> None:
    if DB_ENGINE != "postgresql":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A camada de IA requer PostgreSQL/Supabase ativo.",
        )
    row = fetchone(db, "SELECT to_regnamespace('olist_ai') AS schema_name")
    if row is None or row_value(row, "schema_name") is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A camada semântica da IA ainda não foi migrada no banco.",
        )


def parse_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def fetch_user_tenants(db: Any, user_id: str) -> list[RowData]:
    return fetchall(
        db,
        """
        SELECT
          t.tenant_id,
          t.tenant_code,
          t.tenant_name,
          t.status,
          ut.role
        FROM olist_admin.user_tenants ut
        JOIN olist_admin.tenants t
          ON t.tenant_id = ut.tenant_id
        WHERE ut.user_id = ?
        ORDER BY
          CASE ut.role
            WHEN 'owner' THEN 1
            WHEN 'admin' THEN 2
            WHEN 'operator' THEN 3
            ELSE 4
          END,
          t.tenant_name ASC
        """,
        (user_id,),
    )


def resolve_ai_tenant_scope(db: Any, user_id: str, requested_tenant_id: str | None) -> tuple[str, list[RowData]]:
    ensure_ai_layer_available(db)
    set_db_app_user_context(db, user_id)
    tenants = fetch_user_tenants(db, user_id)
    if not tenants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="O usuário autenticado não possui tenant vinculado para consulta da IA.",
        )
    selected_tenant_id = requested_tenant_id or str(row_value(tenants[0], "tenant_id"))
    if not any(str(row_value(item, "tenant_id")) == selected_tenant_id for item in tenants):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="O tenant informado não está vinculado ao usuário autenticado.",
        )
    return selected_tenant_id, tenants


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def current_date_iso() -> str:
    return utc_now().date().isoformat()


def default_period_days(days: int = 30) -> tuple[str, str]:
    end_date = utc_now().date()
    start_date = end_date - timedelta(days=max(days - 1, 0))
    return start_date.isoformat(), end_date.isoformat()


def normalize_ai_limit(options: Mapping[str, Any] | None, *, default: int = 10, maximum: int = 100) -> int:
    raw_value = (options or {}).get("limit", default)
    try:
        limit_value = int(raw_value)
    except (TypeError, ValueError):
        limit_value = default
    return max(1, min(limit_value, maximum))


def normalize_ai_period(filters: Mapping[str, Any] | None, *, default_days: int = 30) -> tuple[str, str]:
    payload = dict(filters or {})
    start_date = str(payload.get("start_date") or payload.get("startDate") or "").strip()
    end_date = str(payload.get("end_date") or payload.get("endDate") or "").strip()
    if not start_date or not end_date:
        return default_period_days(default_days)
    return start_date, end_date


def normalize_text_filter(filters: Mapping[str, Any] | None, *keys: str) -> str | None:
    payload = dict(filters or {})
    for key in keys:
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return None


def normalize_reference_date(filters: Mapping[str, Any] | None) -> str:
    payload = dict(filters or {})
    value = str(payload.get("reference_date") or payload.get("referenceDate") or "").strip()
    return value or current_date_iso()


def build_ilike_param(value: str | None) -> str | None:
    if not value:
        return None
    return f"%{value}%"


def build_ai_summary_text(tool_name: str, summary_metrics: Mapping[str, Any]) -> str:
    if tool_name == "consultar_resumo_vendas":
        gross_sales = to_float(summary_metrics.get("grossSales"))
        orders_count = int(summary_metrics.get("ordersCount") or 0)
        average_ticket = to_float(summary_metrics.get("averageTicket"))
        return (
            f"No período consultado, o faturamento efetivo foi de {gross_sales:.2f}, "
            f"com {orders_count} pedidos faturados e ticket médio de {average_ticket:.2f}."
        )
    if tool_name == "consultar_estoque_baixo":
        low_stock_items = int(summary_metrics.get("itemsCount") or 0)
        return f"Foram encontrados {low_stock_items} itens com estoque igual ou abaixo do mínimo."
    if tool_name == "consultar_receber_vencidos":
        overdue_count = int(summary_metrics.get("titlesCount") or 0)
        overdue_amount = to_float(summary_metrics.get("openAmountTotal"))
        return f"Existem {overdue_count} títulos a receber vencidos, somando {overdue_amount:.2f} em aberto."
    if tool_name == "consultar_pagar_vencidos":
        overdue_count = int(summary_metrics.get("titlesCount") or 0)
        overdue_amount = to_float(summary_metrics.get("openAmountTotal"))
        return f"Existem {overdue_count} contas a pagar vencidas, somando {overdue_amount:.2f} em aberto."
    if tool_name == "explicar_metrica":
        metric_name = str(summary_metrics.get("metricName") or "métrica")
        return f"A métrica consultada foi identificada como {metric_name}."
    if tool_name == "buscar_glossario":
        term = str(summary_metrics.get("term") or "termo")
        return f"O termo consultado foi identificado como {term}."
    return "Consulta processada com sucesso."


def infer_ai_tool(question: str, explicit_tool_name: str | None) -> str:
    if explicit_tool_name:
        return explicit_tool_name.strip().lower()
    normalized = question.strip().lower()
    if any(term in normalized for term in ("glossário", "glossario", "o que significa", "definição", "definicao", "conceito")):
        return "buscar_glossario"
    if any(term in normalized for term in ("métrica", "metrica", "como calcula", "fórmula", "formula")):
        return "explicar_metrica"
    if "estoque" in normalized and any(term in normalized for term in ("baixo", "mínimo", "minimo", "ruptura")):
        return "consultar_estoque_baixo"
    if any(term in normalized for term in ("receber", "inadimpl", "cliente em aberto")) and any(term in normalized for term in ("vencid", "atras")):
        return "consultar_receber_vencidos"
    if any(term in normalized for term in ("pagar", "fornecedor")) and any(term in normalized for term in ("vencid", "atras")):
        return "consultar_pagar_vencidos"
    if any(term in normalized for term in ("faturamento", "ticket", "pedido", "vendas", "venda")):
        return "consultar_resumo_vendas"
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Nao foi possivel inferir a tool da consulta. Informe toolName explicitamente.",
    )


def insert_ai_query_audit(
    db: Any,
    *,
    tenant_id: str,
    user_id: str,
    session_id: str | None,
    question_text: str,
    normalized_intent: str,
    tool_name: str,
    source_schema: str | None,
    source_object: str | None,
    filters_json: Mapping[str, Any],
    row_count: int | None,
    result_summary: str | None,
    status_text: str,
    error_message: str | None,
    started_at_value: str,
    finished_at_value: str,
) -> str:
    audit_id = str(uuid4())
    execute(
        db,
        """
        INSERT INTO olist_ai.ai_query_audit (
          audit_id,
          tenant_id,
          user_id,
          session_id,
          question_text,
          normalized_intent,
          tool_name,
          source_schema,
          source_object,
          filters_json,
          row_count,
          result_summary,
          started_at,
          finished_at,
          status,
          error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS jsonb), ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id,
            tenant_id,
            user_id,
            session_id,
            question_text,
            normalized_intent,
            tool_name,
            source_schema,
            source_object,
            json.dumps(filters_json, ensure_ascii=True),
            row_count,
            result_summary,
            started_at_value,
            finished_at_value,
            status_text,
            error_message,
        ),
    )
    return audit_id


def execute_ai_sales_summary(
    db: Any,
    *,
    tenant_id: str,
    filters: Mapping[str, Any],
    options: Mapping[str, Any],
) -> dict[str, Any]:
    start_date, end_date = normalize_ai_period(filters)
    vendor_name = normalize_text_filter(filters, "vendor_name", "vendorName")
    contact_name = normalize_text_filter(filters, "contact_name", "contactName")
    order_origin_name = normalize_text_filter(filters, "order_origin_name", "orderOriginName")
    vendor_filter = vendor_name or ""
    contact_filter = contact_name or ""
    order_origin_filter = order_origin_name or ""
    summary_row = fetchone(
        db,
        """
        SELECT
          COUNT(DISTINCT order_id) AS orders_count,
          COALESCE(SUM(total_order_amount), 0::numeric) AS gross_sales,
          COALESCE(AVG(total_order_amount), 0::numeric) AS average_ticket
        FROM olist_mart.mv_fact_orders
        WHERE tenant_id = ?
          AND is_billed_order = TRUE
          AND billed_on BETWEEN ? AND ?
          AND (? = '' OR vendor_name ILIKE ?)
          AND (? = '' OR contact_name ILIKE ?)
          AND (? = '' OR order_origin_name ILIKE ?)
        """,
        (
            tenant_id,
            start_date,
            end_date,
            vendor_filter,
            build_ilike_param(vendor_name) or "%",
            contact_filter,
            build_ilike_param(contact_name) or "%",
            order_origin_filter,
            build_ilike_param(order_origin_name) or "%",
        ),
    )
    include_breakdown = bool((options or {}).get("includeBreakdown", True) or (options or {}).get("include_breakdown", True))
    breakdown_rows = fetchall(
        db,
        """
        SELECT
          billed_on,
          COUNT(DISTINCT order_id) AS orders_count,
          COALESCE(SUM(total_order_amount), 0::numeric) AS gross_sales
        FROM olist_mart.mv_fact_orders
        WHERE tenant_id = ?
          AND is_billed_order = TRUE
          AND billed_on BETWEEN ? AND ?
          AND (? = '' OR vendor_name ILIKE ?)
          AND (? = '' OR contact_name ILIKE ?)
          AND (? = '' OR order_origin_name ILIKE ?)
        GROUP BY billed_on
        ORDER BY billed_on DESC
        LIMIT 31
        """,
        (
            tenant_id,
            start_date,
            end_date,
            vendor_filter,
            build_ilike_param(vendor_name) or "%",
            contact_filter,
            build_ilike_param(contact_name) or "%",
            order_origin_filter,
            build_ilike_param(order_origin_name) or "%",
        ),
    ) if include_breakdown else []
    summary_metrics = {
        "grossSales": to_float(row_value(summary_row, "gross_sales") if summary_row else 0),
        "ordersCount": int(row_value(summary_row, "orders_count") or 0) if summary_row else 0,
        "averageTicket": to_float(row_value(summary_row, "average_ticket") if summary_row else 0),
    }
    return {
        "domain": "vendas",
        "toolName": "consultar_resumo_vendas",
        "intentName": "sales_summary",
        "summaryMetrics": summary_metrics,
        "resultTable": [
            {
                "billedOn": str(row_value(item, "billed_on")),
                "ordersCount": int(row_value(item, "orders_count") or 0),
                "grossSales": to_float(row_value(item, "gross_sales")),
            }
            for item in breakdown_rows
        ],
        "appliedFilters": {
            "startDate": start_date,
            "endDate": end_date,
            "vendorName": vendor_name,
            "contactName": contact_name,
            "orderOriginName": order_origin_name,
            "timeBasis": "billing_date",
            "isBilledOrder": True,
        },
        "source": {"schema": "olist_mart", "object": "mv_fact_orders"},
    }


def execute_ai_inventory_below_minimum(
    db: Any,
    *,
    tenant_id: str,
    filters: Mapping[str, Any],
    options: Mapping[str, Any],
) -> dict[str, Any]:
    limit_value = normalize_ai_limit(options, default=20, maximum=200)
    product_name = normalize_text_filter(filters, "product_name", "productName")
    product_code = normalize_text_filter(filters, "product_code", "productCode")
    deposit_name = normalize_text_filter(filters, "deposit_name", "depositName")
    product_name_filter = product_name or ""
    product_code_filter = product_code or ""
    deposit_name_filter = deposit_name or ""
    rows = fetchall(
        db,
        """
        SELECT
          product_id,
          product_code,
          product_name,
          deposit_name,
          available_qty,
          stock_min_qty,
          reserved_qty,
          physical_qty
        FROM olist_mart.mv_fact_inventory
        WHERE tenant_id = ?
          AND is_below_min_stock = TRUE
          AND (? = '' OR product_name ILIKE ?)
          AND (? = '' OR product_code ILIKE ?)
          AND (? = '' OR deposit_name ILIKE ?)
        ORDER BY available_qty ASC, product_name ASC
        LIMIT ?
        """,
        (
            tenant_id,
            product_name_filter,
            build_ilike_param(product_name) or "%",
            product_code_filter,
            build_ilike_param(product_code) or "%",
            deposit_name_filter,
            build_ilike_param(deposit_name) or "%",
            limit_value,
        ),
    )
    return {
        "domain": "estoque",
        "toolName": "consultar_estoque_baixo",
        "intentName": "inventory_below_minimum",
        "summaryMetrics": {"itemsCount": len(rows)},
        "resultTable": [
            {
                "productId": str(row_value(item, "product_id")),
                "productCode": row_value(item, "product_code"),
                "productName": row_value(item, "product_name"),
                "depositName": row_value(item, "deposit_name"),
                "availableQty": to_float(row_value(item, "available_qty")),
                "stockMinQty": to_float(row_value(item, "stock_min_qty")),
                "reservedQty": to_float(row_value(item, "reserved_qty")),
                "physicalQty": to_float(row_value(item, "physical_qty")),
            }
            for item in rows
        ],
        "appliedFilters": {
            "productName": product_name,
            "productCode": product_code,
            "depositName": deposit_name,
            "limit": limit_value,
            "isBelowMinStock": True,
        },
        "source": {"schema": "olist_mart", "object": "mv_fact_inventory"},
    }


def execute_ai_receivables_overdue(
    db: Any,
    *,
    tenant_id: str,
    filters: Mapping[str, Any],
    options: Mapping[str, Any],
) -> dict[str, Any]:
    limit_value = normalize_ai_limit(options, default=20, maximum=200)
    reference_date = normalize_reference_date(filters)
    contact_name = normalize_text_filter(filters, "contact_name", "contactName")
    contact_filter = contact_name or ""
    rows = fetchall(
        db,
        """
        SELECT
          contact_name,
          order_number,
          invoice_number,
          status,
          due_date,
          open_amount,
          amount
        FROM olist_mart.mv_fact_receivables
        WHERE tenant_id = ?
          AND due_date < ?
          AND open_amount > 0
          AND (? = '' OR contact_name ILIKE ?)
        ORDER BY due_date ASC, open_amount DESC
        LIMIT ?
        """,
        (tenant_id, reference_date, contact_filter, build_ilike_param(contact_name) or "%", limit_value),
    )
    summary_row = fetchone(
        db,
        """
        SELECT
          COUNT(*) AS titles_count,
          COALESCE(SUM(open_amount), 0::numeric) AS open_amount_total
        FROM olist_mart.mv_fact_receivables
        WHERE tenant_id = ?
          AND due_date < ?
          AND open_amount > 0
          AND (? = '' OR contact_name ILIKE ?)
        """,
        (tenant_id, reference_date, contact_filter, build_ilike_param(contact_name) or "%"),
    )
    return {
        "domain": "financeiro",
        "toolName": "consultar_receber_vencidos",
        "intentName": "receivables_overdue",
        "summaryMetrics": {
            "titlesCount": int(row_value(summary_row, "titles_count") or 0) if summary_row else 0,
            "openAmountTotal": to_float(row_value(summary_row, "open_amount_total") if summary_row else 0),
        },
        "resultTable": [
            {
                "contactName": row_value(item, "contact_name"),
                "orderNumber": row_value(item, "order_number"),
                "invoiceNumber": row_value(item, "invoice_number"),
                "status": row_value(item, "status"),
                "dueDate": str(row_value(item, "due_date")),
                "openAmount": to_float(row_value(item, "open_amount")),
                "amount": to_float(row_value(item, "amount")),
            }
            for item in rows
        ],
        "appliedFilters": {
            "referenceDate": reference_date,
            "contactName": contact_name,
            "limit": limit_value,
            "openAmountGt": 0,
        },
        "source": {"schema": "olist_mart", "object": "mv_fact_receivables"},
    }


def execute_ai_payables_overdue(
    db: Any,
    *,
    tenant_id: str,
    filters: Mapping[str, Any],
    options: Mapping[str, Any],
) -> dict[str, Any]:
    limit_value = normalize_ai_limit(options, default=20, maximum=200)
    reference_date = normalize_reference_date(filters)
    contact_name = normalize_text_filter(filters, "contact_name", "contactName")
    contact_filter = contact_name or ""
    rows = fetchall(
        db,
        """
        SELECT
          contact_name,
          purchase_order_number,
          expense_category_name,
          status,
          due_date,
          open_amount,
          amount
        FROM olist_mart.mv_fact_payables
        WHERE tenant_id = ?
          AND due_date < ?
          AND open_amount > 0
          AND (? = '' OR contact_name ILIKE ?)
        ORDER BY due_date ASC, open_amount DESC
        LIMIT ?
        """,
        (tenant_id, reference_date, contact_filter, build_ilike_param(contact_name) or "%", limit_value),
    )
    summary_row = fetchone(
        db,
        """
        SELECT
          COUNT(*) AS titles_count,
          COALESCE(SUM(open_amount), 0::numeric) AS open_amount_total
        FROM olist_mart.mv_fact_payables
        WHERE tenant_id = ?
          AND due_date < ?
          AND open_amount > 0
          AND (? = '' OR contact_name ILIKE ?)
        """,
        (tenant_id, reference_date, contact_filter, build_ilike_param(contact_name) or "%"),
    )
    return {
        "domain": "financeiro",
        "toolName": "consultar_pagar_vencidos",
        "intentName": "payables_overdue",
        "summaryMetrics": {
            "titlesCount": int(row_value(summary_row, "titles_count") or 0) if summary_row else 0,
            "openAmountTotal": to_float(row_value(summary_row, "open_amount_total") if summary_row else 0),
        },
        "resultTable": [
            {
                "contactName": row_value(item, "contact_name"),
                "purchaseOrderNumber": row_value(item, "purchase_order_number"),
                "expenseCategoryName": row_value(item, "expense_category_name"),
                "status": row_value(item, "status"),
                "dueDate": str(row_value(item, "due_date")),
                "openAmount": to_float(row_value(item, "open_amount")),
                "amount": to_float(row_value(item, "amount")),
            }
            for item in rows
        ],
        "appliedFilters": {
            "referenceDate": reference_date,
            "contactName": contact_name,
            "limit": limit_value,
            "openAmountGt": 0,
        },
        "source": {"schema": "olist_mart", "object": "mv_fact_payables"},
    }


def execute_ai_metric_explanation(
    db: Any,
    *,
    tenant_id: str,
    question: str,
    filters: Mapping[str, Any],
) -> dict[str, Any]:
    metric_lookup = normalize_text_filter(filters, "metric_code", "metricCode", "term", "name") or question.strip()
    row = fetchone(
        db,
        """
        SELECT
          metric_code,
          metric_name,
          domain,
          definition,
          formula_description,
          sql_rule_summary,
          source_schema,
          source_object,
          time_basis,
          business_notes
        FROM olist_ai.ai_metric_catalog
        WHERE tenant_id = ?
          AND (
            metric_code ILIKE ?
            OR metric_name ILIKE ?
            OR definition ILIKE ?
          )
        ORDER BY
          CASE
            WHEN lower(metric_code) = lower(?) THEN 1
            WHEN lower(metric_name) = lower(?) THEN 2
            ELSE 3
          END,
          metric_name
        LIMIT 1
        """,
        (
            tenant_id,
            build_ilike_param(metric_lookup),
            build_ilike_param(metric_lookup),
            build_ilike_param(metric_lookup),
            metric_lookup,
            metric_lookup,
        ),
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Métrica não encontrada na camada semântica.")
    return {
        "domain": row_value(row, "domain"),
        "toolName": "explicar_metrica",
        "intentName": "metric_explanation",
        "summaryMetrics": {
            "metricCode": row_value(row, "metric_code"),
            "metricName": row_value(row, "metric_name"),
        },
        "resultTable": [
            {
                "metricCode": row_value(row, "metric_code"),
                "metricName": row_value(row, "metric_name"),
                "definition": row_value(row, "definition"),
                "formulaDescription": row_value(row, "formula_description"),
                "sqlRuleSummary": row_value(row, "sql_rule_summary"),
                "timeBasis": row_value(row, "time_basis"),
                "sourceSchema": row_value(row, "source_schema"),
                "sourceObject": row_value(row, "source_object"),
                "businessNotes": row_value(row, "business_notes"),
            }
        ],
        "appliedFilters": {"lookup": metric_lookup},
        "source": {"schema": "olist_ai", "object": "ai_metric_catalog"},
    }


def execute_ai_glossary_lookup(
    db: Any,
    *,
    tenant_id: str,
    question: str,
    filters: Mapping[str, Any],
) -> dict[str, Any]:
    term_lookup = normalize_text_filter(filters, "term", "normalized_term", "normalizedTerm", "name") or question.strip()
    normalized_question = question.strip().lower()
    row = fetchone(
        db,
        """
        SELECT
          term,
          normalized_term,
          aliases,
          domain,
          definition,
          business_notes,
          source_reference
        FROM olist_ai.ai_business_glossary
        WHERE tenant_id = ?
          AND (
            normalized_term ILIKE ?
            OR term ILIKE ?
            OR definition ILIKE ?
            OR aliases::text ILIKE ?
            OR ? ILIKE ('%%' || lower(normalized_term) || '%%')
            OR ? ILIKE ('%%' || lower(term) || '%%')
          )
        ORDER BY
          CASE
            WHEN lower(normalized_term) = lower(?) THEN 1
            WHEN lower(term) = lower(?) THEN 2
            WHEN ? ILIKE ('%%' || lower(normalized_term) || '%%') THEN 3
            WHEN ? ILIKE ('%%' || lower(term) || '%%') THEN 4
            ELSE 5
          END,
          term
        LIMIT 1
        """,
        (
            tenant_id,
            build_ilike_param(term_lookup),
            build_ilike_param(term_lookup),
            build_ilike_param(term_lookup),
            build_ilike_param(term_lookup),
            normalized_question,
            normalized_question,
            term_lookup,
            term_lookup,
            normalized_question,
            normalized_question,
        ),
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Termo não encontrado no glossário semântico.")
    return {
        "domain": row_value(row, "domain"),
        "toolName": "buscar_glossario",
        "intentName": "glossary_lookup",
        "summaryMetrics": {
            "term": row_value(row, "term"),
            "normalizedTerm": row_value(row, "normalized_term"),
        },
        "resultTable": [
            {
                "term": row_value(row, "term"),
                "normalizedTerm": row_value(row, "normalized_term"),
                "aliases": parse_json_list(row_value(row, "aliases")),
                "definition": row_value(row, "definition"),
                "businessNotes": row_value(row, "business_notes"),
                "sourceReference": row_value(row, "source_reference"),
            }
        ],
        "appliedFilters": {"lookup": term_lookup},
        "source": {"schema": "olist_ai", "object": "ai_business_glossary"},
    }


def execute_ai_tool(
    db: Any,
    *,
    tenant_id: str,
    question: str,
    tool_name: str,
    filters: Mapping[str, Any],
    options: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_tool = tool_name.strip().lower()
    if normalized_tool == "consultar_resumo_vendas":
        return execute_ai_sales_summary(db, tenant_id=tenant_id, filters=filters, options=options)
    if normalized_tool == "consultar_estoque_baixo":
        return execute_ai_inventory_below_minimum(db, tenant_id=tenant_id, filters=filters, options=options)
    if normalized_tool == "consultar_receber_vencidos":
        return execute_ai_receivables_overdue(db, tenant_id=tenant_id, filters=filters, options=options)
    if normalized_tool == "consultar_pagar_vencidos":
        return execute_ai_payables_overdue(db, tenant_id=tenant_id, filters=filters, options=options)
    if normalized_tool == "explicar_metrica":
        return execute_ai_metric_explanation(db, tenant_id=tenant_id, question=question, filters=filters)
    if normalized_tool == "buscar_glossario":
        return execute_ai_glossary_lookup(db, tenant_id=tenant_id, question=question, filters=filters)
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Tool de IA ainda não implementada: {normalized_tool}",
    )


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


class ExtractionRunPayload(BaseModel):
    executionType: str = "incremental"


class AiQueryPayload(BaseModel):
    question: str = ""
    tenantId: str | None = None
    toolName: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


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
    allow_origins=[
        "http://localhost:3500",
        "http://127.0.0.1:3500",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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


@app.get("/api/ai/overview")
def ai_overview(
    tenant_id: str | None = Query(default=None),
    current_user: RowData = Depends(get_current_user),
) -> dict[str, Any]:
    actor_id = str(row_value(current_user, "id"))
    with get_db() as db:
        selected_tenant_id, tenants = resolve_ai_tenant_scope(db, actor_id, tenant_id)
        vector_row = fetchone(db, "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') AS enabled")
        counts_row = fetchone(
            db,
            """
            SELECT
              (SELECT COUNT(*) FROM olist_ai.ai_metric_catalog WHERE tenant_id = ?) AS metrics_total,
              (SELECT COUNT(*) FROM olist_ai.ai_business_glossary WHERE tenant_id = ?) AS glossary_total,
              (SELECT COUNT(*) FROM olist_ai.ai_query_templates WHERE tenant_id = ?) AS templates_total,
              (SELECT COUNT(*) FROM olist_ai.ai_prompt_policies WHERE tenant_id = ?) AS policies_total,
              (SELECT COUNT(*) FROM olist_ai.ai_documents WHERE tenant_id = ?) AS documents_total
            """,
            (selected_tenant_id, selected_tenant_id, selected_tenant_id, selected_tenant_id, selected_tenant_id),
        )
        key_metrics = fetchall(
            db,
            """
            SELECT metric_code, metric_name, domain, source_object, time_basis
            FROM olist_ai.ai_metric_catalog
            WHERE tenant_id = ?
              AND status = 'active'
            ORDER BY domain, metric_name
            LIMIT 8
            """,
            (selected_tenant_id,),
        )
    return {
        "tenantId": selected_tenant_id,
        "tenants": [
            {
                "tenantId": str(row_value(item, "tenant_id")),
                "tenantCode": row_value(item, "tenant_code"),
                "tenantName": row_value(item, "tenant_name"),
                "status": row_value(item, "status"),
                "role": row_value(item, "role"),
            }
            for item in tenants
        ],
        "pgvectorEnabled": bool(row_value(vector_row, "enabled")) if vector_row else False,
        "counts": {
            "metrics": int(row_value(counts_row, "metrics_total") or 0) if counts_row else 0,
            "glossary": int(row_value(counts_row, "glossary_total") or 0) if counts_row else 0,
            "templates": int(row_value(counts_row, "templates_total") or 0) if counts_row else 0,
            "policies": int(row_value(counts_row, "policies_total") or 0) if counts_row else 0,
            "documents": int(row_value(counts_row, "documents_total") or 0) if counts_row else 0,
        },
        "keyMetrics": [
            {
                "metricCode": row_value(item, "metric_code"),
                "metricName": row_value(item, "metric_name"),
                "domain": row_value(item, "domain"),
                "sourceObject": row_value(item, "source_object"),
                "timeBasis": row_value(item, "time_basis"),
            }
            for item in key_metrics
        ],
    }


@app.get("/api/ai/metrics")
def ai_metrics(
    tenant_id: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    current_user: RowData = Depends(get_current_user),
) -> list[dict[str, Any]]:
    actor_id = str(row_value(current_user, "id"))
    with get_db() as db:
        selected_tenant_id, _ = resolve_ai_tenant_scope(db, actor_id, tenant_id)
        if domain:
            rows = fetchall(
                db,
                """
                SELECT
                  metric_code,
                  metric_name,
                  domain,
                  definition,
                  formula_description,
                  sql_rule_summary,
                  source_schema,
                  source_object,
                  time_basis,
                  allowed_profiles,
                  status,
                  business_notes
                FROM olist_ai.ai_metric_catalog
                WHERE tenant_id = ?
                  AND domain = ?
                ORDER BY domain, metric_name
                """,
                (selected_tenant_id, domain),
            )
        else:
            rows = fetchall(
                db,
                """
                SELECT
                  metric_code,
                  metric_name,
                  domain,
                  definition,
                  formula_description,
                  sql_rule_summary,
                  source_schema,
                  source_object,
                  time_basis,
                  allowed_profiles,
                  status,
                  business_notes
                FROM olist_ai.ai_metric_catalog
                WHERE tenant_id = ?
                ORDER BY domain, metric_name
                """,
                (selected_tenant_id,),
            )
    return [
        {
            "metricCode": row_value(row, "metric_code"),
            "metricName": row_value(row, "metric_name"),
            "domain": row_value(row, "domain"),
            "definition": row_value(row, "definition"),
            "formulaDescription": row_value(row, "formula_description"),
            "sqlRuleSummary": row_value(row, "sql_rule_summary"),
            "sourceSchema": row_value(row, "source_schema"),
            "sourceObject": row_value(row, "source_object"),
            "timeBasis": row_value(row, "time_basis"),
            "allowedProfiles": parse_json_list(row_value(row, "allowed_profiles")),
            "status": row_value(row, "status"),
            "businessNotes": row_value(row, "business_notes"),
        }
        for row in rows
    ]


@app.get("/api/ai/glossary")
def ai_glossary(
    tenant_id: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    current_user: RowData = Depends(get_current_user),
) -> list[dict[str, Any]]:
    actor_id = str(row_value(current_user, "id"))
    with get_db() as db:
        selected_tenant_id, _ = resolve_ai_tenant_scope(db, actor_id, tenant_id)
        if domain:
            rows = fetchall(
                db,
                """
                SELECT
                  term,
                  normalized_term,
                  aliases,
                  domain,
                  definition,
                  business_notes,
                  source_reference,
                  status
                FROM olist_ai.ai_business_glossary
                WHERE tenant_id = ?
                  AND domain = ?
                ORDER BY domain, term
                """,
                (selected_tenant_id, domain),
            )
        else:
            rows = fetchall(
                db,
                """
                SELECT
                  term,
                  normalized_term,
                  aliases,
                  domain,
                  definition,
                  business_notes,
                  source_reference,
                  status
                FROM olist_ai.ai_business_glossary
                WHERE tenant_id = ?
                ORDER BY domain, term
                """,
                (selected_tenant_id,),
            )
    return [
        {
            "term": row_value(row, "term"),
            "normalizedTerm": row_value(row, "normalized_term"),
            "aliases": parse_json_list(row_value(row, "aliases")),
            "domain": row_value(row, "domain"),
            "definition": row_value(row, "definition"),
            "businessNotes": row_value(row, "business_notes"),
            "sourceReference": row_value(row, "source_reference"),
            "status": row_value(row, "status"),
        }
        for row in rows
    ]


@app.get("/api/ai/templates")
def ai_templates(
    tenant_id: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    current_user: RowData = Depends(get_current_user),
) -> list[dict[str, Any]]:
    actor_id = str(row_value(current_user, "id"))
    with get_db() as db:
        selected_tenant_id, _ = resolve_ai_tenant_scope(db, actor_id, tenant_id)
        if domain:
            rows = fetchall(
                db,
                """
                SELECT
                  tool_name,
                  intent_name,
                  template_description,
                  domain,
                  source_schema,
                  source_object,
                  allowed_filters,
                  required_filters,
                  default_limit,
                  max_limit,
                  response_shape,
                  status
                FROM olist_ai.ai_query_templates
                WHERE tenant_id = ?
                  AND domain = ?
                ORDER BY domain, tool_name
                """,
                (selected_tenant_id, domain),
            )
        else:
            rows = fetchall(
                db,
                """
                SELECT
                  tool_name,
                  intent_name,
                  template_description,
                  domain,
                  source_schema,
                  source_object,
                  allowed_filters,
                  required_filters,
                  default_limit,
                  max_limit,
                  response_shape,
                  status
                FROM olist_ai.ai_query_templates
                WHERE tenant_id = ?
                ORDER BY domain, tool_name
                """,
                (selected_tenant_id,),
            )
    return [
        {
            "toolName": row_value(row, "tool_name"),
            "intentName": row_value(row, "intent_name"),
            "description": row_value(row, "template_description"),
            "domain": row_value(row, "domain"),
            "sourceSchema": row_value(row, "source_schema"),
            "sourceObject": row_value(row, "source_object"),
            "allowedFilters": parse_json_list(row_value(row, "allowed_filters")),
            "requiredFilters": parse_json_list(row_value(row, "required_filters")),
            "defaultLimit": row_value(row, "default_limit"),
            "maxLimit": row_value(row, "max_limit"),
            "responseShape": row_value(row, "response_shape") or {},
            "status": row_value(row, "status"),
        }
        for row in rows
    ]


@app.post("/api/ai/query")
def ai_query(
    payload: AiQueryPayload,
    current_user: RowData = Depends(get_current_user),
) -> dict[str, Any]:
    actor_id = str(row_value(current_user, "id"))
    started_at_dt = utc_now()
    started_at_value = to_db_timestamp(started_at_dt)
    question_text = payload.question.strip()
    filters = dict(payload.filters or {})
    options = dict(payload.options or {})
    explicit_tool_name = str(payload.toolName or "").strip() or None
    tool_name = infer_ai_tool(question_text, explicit_tool_name)

    with get_db() as db:
        selected_tenant_id, _ = resolve_ai_tenant_scope(db, actor_id, payload.tenantId)
        try:
            result = execute_ai_tool(
                db,
                tenant_id=selected_tenant_id,
                question=question_text,
                tool_name=tool_name,
                filters=filters,
                options=options,
            )
            summary_text = build_ai_summary_text(tool_name, result.get("summaryMetrics") or {})
            finished_at_value = to_db_timestamp()
            audit_id = insert_ai_query_audit(
                db,
                tenant_id=selected_tenant_id,
                user_id=actor_id,
                session_id=None,
                question_text=question_text or tool_name,
                normalized_intent=str(result.get("intentName") or tool_name),
                tool_name=tool_name,
                source_schema=str((result.get("source") or {}).get("schema") or ""),
                source_object=str((result.get("source") or {}).get("object") or ""),
                filters_json=result.get("appliedFilters") or filters,
                row_count=len(result.get("resultTable") or []),
                result_summary=summary_text,
                status_text="success",
                error_message=None,
                started_at_value=started_at_value,
                finished_at_value=finished_at_value,
            )
        except HTTPException as error:
            finished_at_value = to_db_timestamp()
            audit_id = insert_ai_query_audit(
                db,
                tenant_id=selected_tenant_id,
                user_id=actor_id,
                session_id=None,
                question_text=question_text or tool_name,
                normalized_intent=tool_name,
                tool_name=tool_name,
                source_schema=None,
                source_object=None,
                filters_json=filters,
                row_count=0,
                result_summary=None,
                status_text="blocked" if error.status_code in {403, 404, 422} else "error",
                error_message=str(error.detail),
                started_at_value=started_at_value,
                finished_at_value=finished_at_value,
            )
            raise HTTPException(
                status_code=error.status_code,
                detail={"message": error.detail, "auditId": audit_id, "toolName": tool_name},
            ) from error

    return {
        "tenantId": selected_tenant_id,
        "toolName": tool_name,
        "domain": result.get("domain"),
        "intentName": result.get("intentName"),
        "summaryText": summary_text,
        "summaryMetrics": result.get("summaryMetrics") or {},
        "resultTable": result.get("resultTable") or [],
        "appliedFilters": result.get("appliedFilters") or filters,
        "source": result.get("source") or {},
        "audit": {
            "auditId": audit_id,
            "status": "success",
            "startedAt": started_at_value,
            "finishedAt": finished_at_value,
        },
    }


@app.get("/api/extraction/overview")
def extraction_overview(current_user: RowData = Depends(get_current_user)) -> dict[str, Any]:
    try:
        payload = extraction_service.get_overview(str(row_value(current_user, "id")))
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    recent_executions = [
        {
            "executionId": str(item.get("execution_id")),
            "executionType": str(item.get("execution_type") or "incremental"),
            "startedAt": normalize_timestamp(item.get("started_at"), fallback="Nao iniciado"),
            "finishedAt": normalize_timestamp(item.get("finished_at"), fallback="Em andamento"),
            "durationSeconds": build_duration_payload(item.get("started_at"), item.get("finished_at"))[0],
            "durationLabel": build_duration_payload(item.get("started_at"), item.get("finished_at"))[1],
            "entityTotal": int(item.get("entity_total") or 0),
            "entitiesSuccess": int(item.get("entities_success") or 0),
            "entitiesCancelled": int(item.get("entities_cancelled") or 0),
            "entitiesError": int(item.get("entities_error") or 0),
            "requestCount": int(item.get("request_count") or 0),
            "successCount": int(item.get("success_count") or 0),
            "errorCount": int(item.get("error_count") or 0),
        }
        for item in payload.get("recentExecutions", [])
    ]

    active_execution = payload.get("activeExecution")
    return {
        "running": bool(payload.get("running")),
        "stopRequested": bool(payload.get("stopRequested")),
        "activeExecutionId": payload.get("activeExecutionId"),
        "tenantId": payload.get("tenantId"),
        "supportedEntities": payload.get("supportedEntities", []),
        "supportedExecutionTypes": ["incremental", "reconciliation"],
        "olist": payload.get("olist", {}),
        "recentExecutions": recent_executions,
        "activeExecution": (
            format_extraction_execution_payload(active_execution)
            if isinstance(active_execution, Mapping)
            else None
        ),
    }


@app.post("/api/extraction/run")
def start_extraction(
    payload: ExtractionRunPayload | None = None,
    current_user: RowData = Depends(get_current_user),
) -> dict[str, Any]:
    actor_email = str(row_value(current_user, "email"))
    actor_id = str(row_value(current_user, "id"))
    execution_type = str(payload.executionType if payload else "incremental").strip().lower()
    if execution_type not in {"incremental", "reconciliation"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O tipo de execução deve ser incremental ou reconciliation.",
        )
    try:
        response = extraction_service.start_execution(
            user_id=actor_id,
            actor_email=actor_email,
            execution_type=execution_type,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    if response.get("status") == "started":
        with get_db() as db:
            append_audit(
                db=db,
                title="Execucao de extracao solicitada",
                description=f"O usuario {actor_email} solicitou a execucao {execution_type} da sincronizacao Olist.",
                tone="accent",
            )
    return response


@app.post("/api/extraction/stop")
def stop_extraction(current_user: RowData = Depends(get_current_user)) -> dict[str, Any]:
    actor_email = str(row_value(current_user, "email"))
    response = extraction_service.request_stop(actor_email=actor_email)
    if response.get("status") == "stopping":
        with get_db() as db:
            append_audit(
                db=db,
                title="Parada da extracao solicitada",
                description=f"O usuario {actor_email} solicitou a interrupcao da sincronizacao Olist em andamento.",
                tone="warning",
            )
    return response


@app.get("/api/extraction/executions/{execution_id}")
def extraction_execution(
    execution_id: str,
    current_user: RowData = Depends(get_current_user),
) -> dict[str, Any]:
    del current_user
    try:
        payload = extraction_service.get_execution(execution_id)
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execucao de extracao nao encontrada.")
    return format_extraction_execution_payload(payload)
