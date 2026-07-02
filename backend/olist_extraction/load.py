from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Generator
from uuid import uuid4

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import ExtractionSettings


POSTGRES_PREFIXES = ("postgres://", "postgresql://")
EXTRACTION_ADVISORY_LOCK_KEY = 48203172001
GLOBAL_EXECUTION_CONTROL_KEY = "global"
OLIST_TOKEN_URL = "https://accounts.tiny.com.br/realms/tiny/protocol/openid-connect/token"
ACCESS_TOKEN_FALLBACK_SECONDS = 4 * 60 * 60
REFRESH_TOKEN_FALLBACK_SECONDS = 24 * 60 * 60


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sql_now() -> datetime:
    return utc_now()


def to_sqlalchemy_url(database_url: str) -> str:
    if database_url.startswith("postgresql+"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    return database_url


@dataclass
class UpsertResult:
    inserted: int = 0
    updated: int = 0


class ExtractionRepository:
    def __init__(self, settings: ExtractionSettings):
        if not settings.database_url.lower().startswith(POSTGRES_PREFIXES):
            raise RuntimeError("A extração Olist exige PostgreSQL/Supabase configurado em ALBERTINA_DATABASE_URL.")
        self.settings = settings
        self.engine: Engine = create_engine(
            to_sqlalchemy_url(settings.database_url),
            future=True,
            pool_pre_ping=True,
        )

    @contextmanager
    def begin(self) -> Generator[Any, None, None]:
        with self.engine.begin() as connection:
            yield connection

    def ensure_supporting_schema(self) -> None:
        statements = [
            "CREATE EXTENSION IF NOT EXISTS pgcrypto",
            "CREATE SCHEMA IF NOT EXISTS olist_admin",
            "CREATE SCHEMA IF NOT EXISTS olist_raw",
            """
            CREATE OR REPLACE FUNCTION olist_admin.set_row_updated_at()
            RETURNS TRIGGER
            LANGUAGE plpgsql
            AS $$
            BEGIN
              NEW.updated_at = NOW();
              RETURN NEW;
            END;
            $$;
            """,
            """
            CREATE OR REPLACE FUNCTION olist_admin.current_app_user_id()
            RETURNS TEXT
            LANGUAGE sql
            STABLE
            AS $$
              SELECT NULLIF(current_setting('app.current_user_id', true), '');
            $$;
            """,
            """
            CREATE OR REPLACE FUNCTION olist_admin.can_read_tenant(target_tenant_id UUID)
            RETURNS BOOLEAN
            LANGUAGE sql
            STABLE
            AS $$
              SELECT EXISTS (
                SELECT 1
                FROM olist_admin.user_tenants ut
                WHERE ut.tenant_id = target_tenant_id
                  AND ut.user_id = olist_admin.current_app_user_id()
              );
            $$;
            """,
            """
            CREATE OR REPLACE FUNCTION olist_admin.can_write_tenant(target_tenant_id UUID)
            RETURNS BOOLEAN
            LANGUAGE sql
            STABLE
            AS $$
              SELECT EXISTS (
                SELECT 1
                FROM olist_admin.user_tenants ut
                WHERE ut.tenant_id = target_tenant_id
                  AND ut.user_id = olist_admin.current_app_user_id()
                  AND ut.role IN ('owner', 'admin', 'operator')
              );
            $$;
            """,
            """
            CREATE TABLE IF NOT EXISTS olist_admin.tenants (
              tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              tenant_code TEXT NOT NULL UNIQUE,
              tenant_name TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'active',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS olist_admin.user_tenants (
              user_id TEXT NOT NULL,
              tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
              role TEXT NOT NULL DEFAULT 'admin',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              PRIMARY KEY (user_id, tenant_id),
              CONSTRAINT user_tenants_user_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
              CONSTRAINT user_tenants_role_check CHECK (role IN ('owner', 'admin', 'operator', 'reader'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS olist_admin.sync_runs (
              sync_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              execution_id UUID NULL,
              execution_type TEXT NOT NULL DEFAULT 'incremental',
              tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
              entity_name TEXT NOT NULL,
              endpoint_path TEXT NOT NULL,
              http_method TEXT NOT NULL DEFAULT 'GET',
              sync_mode TEXT NOT NULL,
              status TEXT NOT NULL,
              started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              finished_at TIMESTAMPTZ NULL,
              request_count INTEGER NOT NULL DEFAULT 0,
              success_count INTEGER NOT NULL DEFAULT 0,
              error_count INTEGER NOT NULL DEFAULT 0,
              watermark_from TIMESTAMPTZ NULL,
              watermark_to TIMESTAMPTZ NULL,
              details JSONB NOT NULL DEFAULT '{}'::JSONB,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            "ALTER TABLE olist_admin.sync_runs ADD COLUMN IF NOT EXISTS execution_id UUID NULL",
            "ALTER TABLE olist_admin.sync_runs ADD COLUMN IF NOT EXISTS execution_type TEXT NOT NULL DEFAULT 'incremental'",
            "ALTER TABLE olist_admin.sync_runs DROP CONSTRAINT IF EXISTS sync_runs_mode_check",
            (
                "ALTER TABLE olist_admin.sync_runs "
                "ADD CONSTRAINT sync_runs_mode_check "
                "CHECK (sync_mode IN ('full', 'incremental', 'snapshot', 'reconciliation', 'cooldown'))"
            ),
            """
            CREATE TABLE IF NOT EXISTS olist_admin.sync_watermarks (
              tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
              entity_name TEXT NOT NULL,
              endpoint_path TEXT NOT NULL,
              last_success_at TIMESTAMPTZ NULL,
              last_cursor JSONB NOT NULL DEFAULT '{}'::JSONB,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              PRIMARY KEY (tenant_id, entity_name, endpoint_path)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS olist_admin.sync_run_logs (
              log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              execution_id UUID NOT NULL,
              sync_run_id UUID NULL REFERENCES olist_admin.sync_runs(sync_run_id) ON DELETE CASCADE,
              tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
              entity_name TEXT NOT NULL,
              level TEXT NOT NULL,
              stage TEXT NOT NULL,
              message TEXT NOT NULL,
              extracted_count INTEGER NOT NULL DEFAULT 0,
              inserted_count INTEGER NOT NULL DEFAULT 0,
              updated_count INTEGER NOT NULL DEFAULT 0,
              error_count INTEGER NOT NULL DEFAULT 0,
              stack_trace TEXT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS olist_admin.execution_control (
              control_key TEXT PRIMARY KEY,
              active_execution_id UUID NULL,
              execution_type TEXT NULL,
              state TEXT NOT NULL DEFAULT 'idle',
              worker_id TEXT NULL,
              worker_pid INTEGER NULL,
              lease_expires_at TIMESTAMPTZ NULL,
              heartbeat_at TIMESTAMPTZ NULL,
              stop_requested_at TIMESTAMPTZ NULL,
              metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            INSERT INTO olist_admin.execution_control (control_key, state, metadata)
            VALUES ('global', 'idle', '{}'::JSONB)
            ON CONFLICT (control_key) DO NOTHING
            """,
            """
            CREATE TABLE IF NOT EXISTS olist_raw.api_payloads (
              raw_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
              entity_name TEXT NOT NULL,
              endpoint_path TEXT NOT NULL,
              external_key TEXT NOT NULL DEFAULT '',
              http_method TEXT NOT NULL,
              olist_object_id BIGINT NULL,
              parent_olist_object_id BIGINT NULL,
              source_updated_at TIMESTAMPTZ NULL,
              extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              sync_run_id UUID NULL REFERENCES olist_admin.sync_runs(sync_run_id) ON DELETE SET NULL,
              payload_hash TEXT NULL,
              source_status TEXT NULL,
              is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
              deleted_at TIMESTAMPTZ NULL,
              last_seen_at TIMESTAMPTZ NULL,
              last_seen_execution_id UUID NULL,
              payload JSONB NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            "ALTER TABLE olist_raw.api_payloads ADD COLUMN IF NOT EXISTS external_key TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE olist_raw.api_payloads ADD COLUMN IF NOT EXISTS source_status TEXT NULL",
            "ALTER TABLE olist_raw.api_payloads ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE olist_raw.api_payloads ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL",
            "ALTER TABLE olist_raw.api_payloads ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ NULL",
            "ALTER TABLE olist_raw.api_payloads ADD COLUMN IF NOT EXISTS last_seen_execution_id UUID NULL",
            """
            UPDATE olist_raw.api_payloads
            SET external_key = COALESCE(NULLIF(external_key, ''), CONCAT(endpoint_path, '|', COALESCE(olist_object_id::TEXT, 'singleton')))
            WHERE external_key = ''
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_api_payloads_external_key
            ON olist_raw.api_payloads (tenant_id, entity_name, endpoint_path, external_key)
            """,
            "CREATE INDEX IF NOT EXISTS idx_api_payloads_entity_seen ON olist_raw.api_payloads (tenant_id, entity_name, last_seen_execution_id)",
            "CREATE INDEX IF NOT EXISTS idx_api_payloads_deleted ON olist_raw.api_payloads (tenant_id, entity_name, is_deleted)",
            "CREATE INDEX IF NOT EXISTS idx_sync_runs_execution_id ON olist_admin.sync_runs (execution_id, started_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_sync_run_logs_execution_id ON olist_admin.sync_run_logs (execution_id, created_at ASC)",
        ]

        trigger_statements = [
            ("olist_admin.tenants", "trg_tenants_updated_at"),
            ("olist_admin.user_tenants", "trg_user_tenants_updated_at"),
            ("olist_admin.sync_runs", "trg_sync_runs_updated_at"),
            ("olist_admin.sync_watermarks", "trg_sync_watermarks_updated_at"),
            ("olist_admin.execution_control", "trg_execution_control_updated_at"),
        ]

        policy_tables = (
            "olist_admin.tenants",
            "olist_admin.user_tenants",
            "olist_admin.sync_runs",
            "olist_admin.sync_watermarks",
            "olist_admin.sync_run_logs",
            "olist_raw.api_payloads",
        )

        with self.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

            for table_name, trigger_name in trigger_statements:
                connection.execute(text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}"))
                connection.execute(
                    text(
                        f"""
                        CREATE TRIGGER {trigger_name}
                        BEFORE UPDATE ON {table_name}
                        FOR EACH ROW
                        EXECUTE FUNCTION olist_admin.set_row_updated_at()
                        """
                    )
                )

            for table_name in policy_tables:
                connection.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))

            policy_specs = [
                ("olist_admin.tenants", "tenant_id"),
                ("olist_admin.user_tenants", "tenant_id"),
                ("olist_admin.sync_runs", "tenant_id"),
                ("olist_admin.sync_watermarks", "tenant_id"),
                ("olist_admin.sync_run_logs", "tenant_id"),
                ("olist_raw.api_payloads", "tenant_id"),
            ]
            for table_name, column_name in policy_specs:
                policy_prefix = table_name.split(".")[-1]
                connection.execute(text(f"DROP POLICY IF EXISTS {policy_prefix}_select_policy ON {table_name}"))
                connection.execute(
                    text(
                        f"""
                        CREATE POLICY {policy_prefix}_select_policy
                        ON {table_name}
                        FOR SELECT
                        USING (olist_admin.can_read_tenant({column_name}))
                        """
                    )
                )
                connection.execute(text(f"DROP POLICY IF EXISTS {policy_prefix}_write_policy ON {table_name}"))
                connection.execute(
                    text(
                        f"""
                        CREATE POLICY {policy_prefix}_write_policy
                        ON {table_name}
                        FOR ALL
                        USING (olist_admin.can_write_tenant({column_name}))
                        WITH CHECK (olist_admin.can_write_tenant({column_name}))
                        """
                    )
                )

    def ensure_default_tenant(self, user_id: str | None = None) -> str:
        with self.begin() as connection:
            tenant_row = connection.execute(
                text(
                    """
                    INSERT INTO olist_admin.tenants (tenant_code, tenant_name)
                    VALUES (:tenant_code, :tenant_name)
                    ON CONFLICT (tenant_code) DO UPDATE
                    SET tenant_name = EXCLUDED.tenant_name
                    RETURNING tenant_id
                    """
                ),
                {
                    "tenant_code": self.settings.default_tenant_code,
                    "tenant_name": self.settings.default_tenant_name,
                },
            ).mappings().one()
            tenant_id = str(tenant_row["tenant_id"])

            if user_id:
                connection.execute(
                    text(
                        """
                        INSERT INTO olist_admin.user_tenants (user_id, tenant_id, role)
                        VALUES (:user_id, :tenant_id, 'admin')
                        ON CONFLICT (user_id, tenant_id) DO NOTHING
                        """
                    ),
                    {"user_id": user_id, "tenant_id": tenant_id},
                )
            return tenant_id

    def claim_execution_slot(
        self,
        *,
        execution_id: str,
        execution_type: str,
        lease_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = json.dumps(metadata or {})
        with self.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO olist_admin.execution_control (control_key, state, metadata)
                    VALUES (:control_key, 'idle', '{}'::JSONB)
                    ON CONFLICT (control_key) DO NOTHING
                    """
                ),
                {"control_key": GLOBAL_EXECUTION_CONTROL_KEY},
            )
            claimed = connection.execute(
                text(
                    """
                    UPDATE olist_admin.execution_control
                    SET active_execution_id = CAST(:execution_id AS UUID),
                        execution_type = :execution_type,
                        state = 'starting',
                        worker_id = NULL,
                        worker_pid = NULL,
                        lease_expires_at = NOW() + make_interval(secs => :lease_seconds),
                        heartbeat_at = NOW(),
                        stop_requested_at = NULL,
                        metadata = CAST(:metadata AS JSONB)
                    WHERE control_key = :control_key
                      AND (
                        active_execution_id IS NULL
                        OR state = 'idle'
                        OR lease_expires_at IS NULL
                        OR lease_expires_at < NOW()
                      )
                    RETURNING active_execution_id, execution_type, state
                    """
                ),
                {
                    "control_key": GLOBAL_EXECUTION_CONTROL_KEY,
                    "execution_id": execution_id,
                    "execution_type": execution_type,
                    "lease_seconds": lease_seconds,
                    "metadata": payload,
                },
            ).mappings().first()
            if claimed:
                return {"claimed": True, "execution_id": str(claimed["active_execution_id"])}
            current = connection.execute(
                text(
                    """
                    SELECT active_execution_id,
                           execution_type,
                           state,
                           lease_expires_at,
                           heartbeat_at,
                           stop_requested_at,
                           metadata
                    FROM olist_admin.execution_control
                    WHERE control_key = :control_key
                    """
                ),
                {"control_key": GLOBAL_EXECUTION_CONTROL_KEY},
            ).mappings().one()
            return {
                "claimed": False,
                "execution_id": str(current["active_execution_id"]) if current.get("active_execution_id") else None,
                "execution_type": current.get("execution_type"),
                "state": current.get("state"),
                "lease_expires_at": current.get("lease_expires_at"),
                "heartbeat_at": current.get("heartbeat_at"),
                "stop_requested_at": current.get("stop_requested_at"),
                "metadata": dict(current.get("metadata") or {}),
            }

    def adopt_execution_slot(
        self,
        *,
        execution_id: str,
        worker_id: str,
        worker_pid: int,
        lease_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        payload = json.dumps(metadata or {})
        with self.begin() as connection:
            row = connection.execute(
                text(
                    """
                    UPDATE olist_admin.execution_control
                    SET state = 'running',
                        worker_id = :worker_id,
                        worker_pid = :worker_pid,
                        lease_expires_at = NOW() + make_interval(secs => :lease_seconds),
                        heartbeat_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::JSONB) || CAST(:metadata AS JSONB)
                    WHERE control_key = :control_key
                      AND active_execution_id = CAST(:execution_id AS UUID)
                    RETURNING control_key
                    """
                ),
                {
                    "control_key": GLOBAL_EXECUTION_CONTROL_KEY,
                    "execution_id": execution_id,
                    "worker_id": worker_id,
                    "worker_pid": worker_pid,
                    "lease_seconds": lease_seconds,
                    "metadata": payload,
                },
            ).mappings().first()
            return row is not None

    def renew_execution_slot(
        self,
        *,
        execution_id: str,
        worker_id: str,
        lease_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        payload = json.dumps(metadata or {})
        with self.begin() as connection:
            row = connection.execute(
                text(
                    """
                    UPDATE olist_admin.execution_control
                    SET state = CASE WHEN stop_requested_at IS NULL THEN 'running' ELSE 'stopping' END,
                        lease_expires_at = NOW() + make_interval(secs => :lease_seconds),
                        heartbeat_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::JSONB) || CAST(:metadata AS JSONB)
                    WHERE control_key = :control_key
                      AND active_execution_id = CAST(:execution_id AS UUID)
                      AND worker_id = :worker_id
                    RETURNING control_key
                    """
                ),
                {
                    "control_key": GLOBAL_EXECUTION_CONTROL_KEY,
                    "execution_id": execution_id,
                    "worker_id": worker_id,
                    "lease_seconds": lease_seconds,
                    "metadata": payload,
                },
            ).mappings().first()
            return row is not None

    def clear_execution_slot(
        self,
        *,
        execution_id: str,
        worker_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = json.dumps(metadata or {})
        with self.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE olist_admin.execution_control
                    SET active_execution_id = NULL,
                        execution_type = NULL,
                        state = 'idle',
                        worker_id = NULL,
                        worker_pid = NULL,
                        lease_expires_at = NULL,
                        heartbeat_at = NULL,
                        stop_requested_at = NULL,
                        metadata = CAST(:metadata AS JSONB)
                    WHERE control_key = :control_key
                      AND active_execution_id = CAST(:execution_id AS UUID)
                      AND (:worker_id IS NULL OR worker_id = :worker_id)
                    """
                ),
                {
                    "control_key": GLOBAL_EXECUTION_CONTROL_KEY,
                    "execution_id": execution_id,
                    "worker_id": worker_id,
                    "metadata": payload,
                },
            )

    def fetch_execution_control(self) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT control_key,
                           active_execution_id,
                           execution_type,
                           state,
                           worker_id,
                           worker_pid,
                           lease_expires_at,
                           heartbeat_at,
                           stop_requested_at,
                           metadata
                    FROM olist_admin.execution_control
                    WHERE control_key = :control_key
                    """
                ),
                {"control_key": GLOBAL_EXECUTION_CONTROL_KEY},
            ).mappings().first()
            if row is None:
                return None
            payload = dict(row)
            if payload.get("active_execution_id") is not None:
                payload["active_execution_id"] = str(payload["active_execution_id"])
            payload["metadata"] = dict(payload.get("metadata") or {})
            return payload

    def request_execution_stop(self) -> dict[str, Any] | None:
        with self.begin() as connection:
            row = connection.execute(
                text(
                    """
                    UPDATE olist_admin.execution_control
                    SET stop_requested_at = COALESCE(stop_requested_at, NOW()),
                        state = CASE WHEN active_execution_id IS NULL THEN 'idle' ELSE 'stopping' END
                    WHERE control_key = :control_key
                      AND active_execution_id IS NOT NULL
                    RETURNING active_execution_id, state, stop_requested_at
                    """
                ),
                {"control_key": GLOBAL_EXECUTION_CONTROL_KEY},
            ).mappings().first()
            if row is None:
                return None
            return {
                "active_execution_id": str(row["active_execution_id"]),
                "state": row["state"],
                "stop_requested_at": row["stop_requested_at"],
            }

    def is_stop_requested(self, execution_id: str) -> bool:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT stop_requested_at
                    FROM olist_admin.execution_control
                    WHERE control_key = :control_key
                      AND active_execution_id = CAST(:execution_id AS UUID)
                    """
                ),
                {
                    "control_key": GLOBAL_EXECUTION_CONTROL_KEY,
                    "execution_id": execution_id,
                },
            ).mappings().first()
            return bool(row and row.get("stop_requested_at") is not None)

    def recover_expired_execution(self, note: str) -> str | None:
        with self.begin() as connection:
            control_row = connection.execute(
                text(
                    """
                    SELECT active_execution_id
                    FROM olist_admin.execution_control
                    WHERE control_key = :control_key
                      AND active_execution_id IS NOT NULL
                      AND lease_expires_at IS NOT NULL
                      AND lease_expires_at < NOW()
                    FOR UPDATE
                    """
                ),
                {"control_key": GLOBAL_EXECUTION_CONTROL_KEY},
            ).mappings().first()
            if control_row is None:
                return None
            execution_id = str(control_row["active_execution_id"])
            connection.execute(
                text(
                    """
                    UPDATE olist_admin.sync_runs
                    SET status = 'cancelled',
                        error_count = error_count + 1,
                        finished_at = NOW(),
                        details = COALESCE(details, '{}'::JSONB) || CAST(:note AS JSONB)
                    WHERE status = 'running'
                      AND execution_id = CAST(:execution_id AS UUID)
                    """
                ),
                {
                    "execution_id": execution_id,
                    "note": json.dumps({"recoveryNote": note}),
                },
            )
            connection.execute(
                text(
                    """
                    UPDATE olist_admin.execution_control
                    SET active_execution_id = NULL,
                        execution_type = NULL,
                        state = 'idle',
                        worker_id = NULL,
                        worker_pid = NULL,
                        lease_expires_at = NULL,
                        heartbeat_at = NULL,
                        stop_requested_at = NULL,
                        metadata = '{}'::JSONB
                    WHERE control_key = :control_key
                    """
                ),
                {"control_key": GLOBAL_EXECUTION_CONTROL_KEY},
            )
            return execution_id

    def try_acquire_execution_lock(self) -> Any | None:
        raw_connection = self.engine.raw_connection()
        try:
            cursor = raw_connection.cursor()
            cursor.execute("SELECT pg_try_advisory_lock(%s)", (EXTRACTION_ADVISORY_LOCK_KEY,))
            locked = bool(cursor.fetchone()[0])
            cursor.close()
            if not locked:
                raw_connection.close()
                return None
            return raw_connection
        except Exception:
            raw_connection.close()
            raise

    def release_execution_lock(self, raw_connection: Any | None) -> None:
        if raw_connection is None:
            return
        try:
            cursor = raw_connection.cursor()
            cursor.execute("SELECT pg_advisory_unlock(%s)", (EXTRACTION_ADVISORY_LOCK_KEY,))
            cursor.close()
        finally:
            raw_connection.close()

    def create_sync_run(
        self,
        *,
        execution_id: str,
        execution_type: str,
        tenant_id: str,
        entity_name: str,
        endpoint_path: str,
        sync_mode: str,
        watermark_from: datetime | None,
        details: dict[str, Any],
    ) -> str:
        with self.begin() as connection:
            row = connection.execute(
                text(
                    """
                    INSERT INTO olist_admin.sync_runs (
                      execution_id,
                      execution_type,
                      tenant_id,
                      entity_name,
                      endpoint_path,
                      sync_mode,
                      status,
                      watermark_from,
                      details
                    )
                    VALUES (
                      :execution_id,
                      :execution_type,
                      :tenant_id,
                      :entity_name,
                      :endpoint_path,
                      :sync_mode,
                      'running',
                      :watermark_from,
                      CAST(:details AS JSONB)
                    )
                    RETURNING sync_run_id
                    """
                ),
                {
                    "execution_id": execution_id,
                    "execution_type": execution_type,
                    "tenant_id": tenant_id,
                    "entity_name": entity_name,
                    "endpoint_path": endpoint_path,
                    "sync_mode": sync_mode,
                    "watermark_from": watermark_from,
                    "details": json.dumps(details),
                },
            ).mappings().one()
            return str(row["sync_run_id"])

    def finish_sync_run(
        self,
        *,
        sync_run_id: str,
        status: str,
        request_count: int,
        success_count: int,
        error_count: int,
        watermark_to: datetime | None,
        details: dict[str, Any],
    ) -> None:
        with self.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE olist_admin.sync_runs
                    SET status = :status,
                        request_count = :request_count,
                        success_count = :success_count,
                        error_count = :error_count,
                        watermark_to = :watermark_to,
                        details = CAST(:details AS JSONB),
                        finished_at = NOW()
                    WHERE sync_run_id = :sync_run_id
                    """
                ),
                {
                    "sync_run_id": sync_run_id,
                    "status": status,
                    "request_count": request_count,
                    "success_count": success_count,
                    "error_count": error_count,
                    "watermark_to": watermark_to,
                    "details": json.dumps(details),
                },
            )

    def update_sync_run_progress(
        self,
        *,
        sync_run_id: str,
        request_count: int,
        success_count: int,
        error_count: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        with self.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE olist_admin.sync_runs
                    SET request_count = :request_count,
                        success_count = :success_count,
                        error_count = :error_count,
                        details = COALESCE(details, '{}'::jsonb) || CAST(:details AS JSONB)
                    WHERE sync_run_id = :sync_run_id
                      AND status = 'running'
                    """
                ),
                {
                    "sync_run_id": sync_run_id,
                    "request_count": request_count,
                    "success_count": success_count,
                    "error_count": error_count,
                    "details": json.dumps(merged_details),
                },
            )

    def append_run_log(
        self,
        *,
        execution_id: str,
        sync_run_id: str | None,
        tenant_id: str,
        entity_name: str,
        level: str,
        stage: str,
        message: str,
        extracted_count: int = 0,
        inserted_count: int = 0,
        updated_count: int = 0,
        error_count: int = 0,
        stack_trace: str | None = None,
    ) -> None:
        with self.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO olist_admin.sync_run_logs (
                      execution_id,
                      sync_run_id,
                      tenant_id,
                      entity_name,
                      level,
                      stage,
                      message,
                      extracted_count,
                      inserted_count,
                      updated_count,
                      error_count,
                      stack_trace
                    )
                    VALUES (
                      :execution_id,
                      :sync_run_id,
                      :tenant_id,
                      :entity_name,
                      :level,
                      :stage,
                      :message,
                      :extracted_count,
                      :inserted_count,
                      :updated_count,
                      :error_count,
                      :stack_trace
                    )
                    """
                ),
                {
                    "execution_id": execution_id,
                    "sync_run_id": sync_run_id,
                    "tenant_id": tenant_id,
                    "entity_name": entity_name,
                    "level": level,
                    "stage": stage,
                    "message": message,
                    "extracted_count": extracted_count,
                    "inserted_count": inserted_count,
                    "updated_count": updated_count,
                    "error_count": error_count,
                    "stack_trace": stack_trace,
                },
            )

    def append_audit(self, title: str, description: str, tone: str = "neutral") -> None:
        with self.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO public.audits (id, title, description, tone, created_at)
                    VALUES (:id, :title, :description, :tone, :created_at)
                    """
                ),
                {
                    "id": str(uuid4()),
                    "title": title,
                    "description": description,
                    "tone": tone,
                    "created_at": sql_now(),
                },
            )

    def get_watermark(self, tenant_id: str, entity_name: str, endpoint_path: str) -> datetime | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT last_success_at
                    FROM olist_admin.sync_watermarks
                    WHERE tenant_id = :tenant_id
                      AND entity_name = :entity_name
                      AND endpoint_path = :endpoint_path
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "entity_name": entity_name,
                    "endpoint_path": endpoint_path,
                },
            ).mappings().first()
            return row["last_success_at"] if row else None

    def save_watermark(self, tenant_id: str, entity_name: str, endpoint_path: str, last_success_at: datetime) -> None:
        with self.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO olist_admin.sync_watermarks (tenant_id, entity_name, endpoint_path, last_success_at)
                    VALUES (:tenant_id, :entity_name, :endpoint_path, :last_success_at)
                    ON CONFLICT (tenant_id, entity_name, endpoint_path) DO UPDATE
                    SET last_success_at = EXCLUDED.last_success_at,
                        updated_at = NOW()
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "entity_name": entity_name,
                    "endpoint_path": endpoint_path,
                    "last_success_at": last_success_at,
                },
            )

    def upsert_raw_payload(
        self,
        *,
        execution_id: str,
        tenant_id: str,
        entity_name: str,
        endpoint_path: str,
        external_key: str,
        olist_object_id: int | None,
        parent_olist_object_id: int | None,
        source_updated_at: datetime | None,
        source_status: str | None,
        sync_run_id: str,
        payload_hash_value: str,
        payload: dict[str, Any] | list[Any] | str | int | float | bool | None,
        connection: Any | None = None,
    ) -> UpsertResult:
        if connection is not None:
            return self._upsert_raw_payload_on_connection(
                connection=connection,
                execution_id=execution_id,
                tenant_id=tenant_id,
                entity_name=entity_name,
                endpoint_path=endpoint_path,
                external_key=external_key,
                olist_object_id=olist_object_id,
                parent_olist_object_id=parent_olist_object_id,
                source_updated_at=source_updated_at,
                source_status=source_status,
                sync_run_id=sync_run_id,
                payload_hash_value=payload_hash_value,
                payload=payload,
            )

        with self.begin() as current_connection:
            return self._upsert_raw_payload_on_connection(
                connection=current_connection,
                execution_id=execution_id,
                tenant_id=tenant_id,
                entity_name=entity_name,
                endpoint_path=endpoint_path,
                external_key=external_key,
                olist_object_id=olist_object_id,
                parent_olist_object_id=parent_olist_object_id,
                source_updated_at=source_updated_at,
                source_status=source_status,
                sync_run_id=sync_run_id,
                payload_hash_value=payload_hash_value,
                payload=payload,
            )

    def _upsert_raw_payload_on_connection(
        self,
        *,
        connection: Any,
        execution_id: str,
        tenant_id: str,
        entity_name: str,
        endpoint_path: str,
        external_key: str,
        olist_object_id: int | None,
        parent_olist_object_id: int | None,
        source_updated_at: datetime | None,
        source_status: str | None,
        sync_run_id: str,
        payload_hash_value: str,
        payload: dict[str, Any] | list[Any] | str | int | float | bool | None,
    ) -> UpsertResult:
        existing = connection.execute(
            text(
                """
                SELECT payload_hash
                FROM olist_raw.api_payloads
                WHERE tenant_id = :tenant_id
                  AND entity_name = :entity_name
                  AND endpoint_path = :endpoint_path
                  AND external_key = :external_key
                """
            ),
            {
                "tenant_id": tenant_id,
                "entity_name": entity_name,
                "endpoint_path": endpoint_path,
                "external_key": external_key,
            },
        ).mappings().first()

        connection.execute(
            text(
                """
                INSERT INTO olist_raw.api_payloads (
                  tenant_id,
                  entity_name,
                  endpoint_path,
                  external_key,
                  http_method,
                  olist_object_id,
                  parent_olist_object_id,
                  source_updated_at,
                  extracted_at,
                  sync_run_id,
                  payload_hash,
                  source_status,
                  is_deleted,
                  deleted_at,
                  last_seen_at,
                  last_seen_execution_id,
                  payload
                )
                VALUES (
                  :tenant_id,
                  :entity_name,
                  :endpoint_path,
                  :external_key,
                  'GET',
                  :olist_object_id,
                  :parent_olist_object_id,
                  :source_updated_at,
                  NOW(),
                  :sync_run_id,
                  :payload_hash,
                  :source_status,
                  FALSE,
                  NULL,
                  NOW(),
                  :last_seen_execution_id,
                  CAST(:payload AS JSONB)
                )
                ON CONFLICT (tenant_id, entity_name, endpoint_path, external_key) DO UPDATE
                SET olist_object_id = EXCLUDED.olist_object_id,
                    parent_olist_object_id = EXCLUDED.parent_olist_object_id,
                    source_updated_at = EXCLUDED.source_updated_at,
                    extracted_at = EXCLUDED.extracted_at,
                    sync_run_id = EXCLUDED.sync_run_id,
                    payload_hash = EXCLUDED.payload_hash,
                    source_status = EXCLUDED.source_status,
                    is_deleted = FALSE,
                    deleted_at = NULL,
                    last_seen_at = EXCLUDED.last_seen_at,
                    last_seen_execution_id = EXCLUDED.last_seen_execution_id,
                    payload = EXCLUDED.payload
                """
            ),
            {
                "tenant_id": tenant_id,
                "entity_name": entity_name,
                "endpoint_path": endpoint_path,
                "external_key": external_key,
                "olist_object_id": olist_object_id,
                "parent_olist_object_id": parent_olist_object_id,
                "source_updated_at": source_updated_at,
                "sync_run_id": sync_run_id,
                "payload_hash": payload_hash_value,
                "source_status": source_status,
                "last_seen_execution_id": execution_id,
                "payload": json.dumps(payload, default=str),
            },
        )

        if existing is None:
            return UpsertResult(inserted=1, updated=0)
        if existing["payload_hash"] != payload_hash_value:
            return UpsertResult(inserted=0, updated=1)
        return UpsertResult(inserted=0, updated=0)

    def reconcile_entity_deletions(self, *, execution_id: str, tenant_id: str, entity_name: str) -> int:
        with self.begin() as connection:
            row = connection.execute(
                text(
                    """
                    WITH reconciled AS (
                      UPDATE olist_raw.api_payloads
                      SET is_deleted = TRUE,
                          deleted_at = NOW()
                      WHERE tenant_id = :tenant_id
                        AND entity_name = :entity_name
                        AND COALESCE(last_seen_execution_id::TEXT, '') <> :execution_id
                        AND is_deleted = FALSE
                      RETURNING raw_id
                    )
                    SELECT COUNT(*) AS total
                    FROM reconciled
                    """
                ),
                {
                    "execution_id": execution_id,
                    "tenant_id": tenant_id,
                    "entity_name": entity_name,
                },
            ).mappings().one()
            return int(row["total"] or 0)

    def fetch_execution_summary(self, execution_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                      execution_id,
                      MAX(execution_type) AS execution_type,
                      MIN(started_at) AS started_at,
                      CASE
                        WHEN COUNT(*) FILTER (WHERE status = 'running') > 0 THEN NULL
                        ELSE MAX(finished_at)
                      END AS finished_at,
                      SUM(request_count) AS request_count,
                      SUM(success_count) AS success_count,
                      SUM(error_count) AS error_count,
                      COUNT(*) AS entity_total,
                      COUNT(*) FILTER (WHERE status = 'success') AS entities_success,
                      COUNT(*) FILTER (WHERE status = 'cancelled') AS entities_cancelled,
                      COUNT(*) FILTER (WHERE status = 'error') AS entities_error,
                      COUNT(*) FILTER (WHERE status = 'running') AS entities_running
                    FROM olist_admin.sync_runs
                    WHERE execution_id = :execution_id
                    GROUP BY execution_id
                    """
                ),
                {"execution_id": execution_id},
            ).mappings().first()
            return dict(row) if row else None

    def fetch_recent_executions(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                      execution_id,
                      MAX(execution_type) AS execution_type,
                      MIN(started_at) AS started_at,
                      CASE
                        WHEN COUNT(*) FILTER (WHERE status = 'running') > 0 THEN NULL
                        ELSE MAX(finished_at)
                      END AS finished_at,
                      COUNT(*) AS entity_total,
                      COUNT(*) FILTER (WHERE status = 'success') AS entities_success,
                      COUNT(*) FILTER (WHERE status = 'cancelled') AS entities_cancelled,
                      COUNT(*) FILTER (WHERE status = 'error') AS entities_error,
                      SUM(request_count) AS request_count,
                      SUM(success_count) AS success_count,
                      SUM(error_count) AS error_count
                    FROM olist_admin.sync_runs
                    WHERE execution_id IS NOT NULL
                    GROUP BY execution_id
                    ORDER BY MIN(started_at) DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
            return [dict(row) for row in rows]

    def fetch_active_execution_id(self) -> str | None:
        control_row = self.fetch_execution_control()
        if control_row and control_row.get("active_execution_id"):
            return str(control_row["active_execution_id"])
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT execution_id
                    FROM olist_admin.sync_runs
                    WHERE status = 'running'
                      AND execution_id IS NOT NULL
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                )
            ).mappings().first()
            return str(row["execution_id"]) if row and row.get("execution_id") else None

    def recover_orphan_running_executions(self, note: str) -> list[str]:
        with self.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    UPDATE olist_admin.sync_runs
                    SET status = 'cancelled',
                        error_count = error_count + 1,
                        finished_at = NOW(),
                        details = details || CAST(:note AS JSONB)
                    WHERE status = 'running'
                      AND execution_id IS NOT NULL
                    RETURNING execution_id
                    """
                ),
                {"note": json.dumps({"recoveryNote": note})},
            ).mappings().all()
            return [str(row["execution_id"]) for row in rows if row.get("execution_id")]

    def fetch_execution_logs(self, execution_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    WITH latest_logs AS (
                      SELECT *
                      FROM olist_admin.sync_run_logs
                      WHERE execution_id = :execution_id
                      ORDER BY created_at DESC
                      LIMIT :limit
                    ),
                    error_logs AS (
                      SELECT *
                      FROM olist_admin.sync_run_logs
                      WHERE execution_id = :execution_id
                        AND (
                          error_count > 0
                          OR UPPER(level) = 'ERROR'
                          OR stack_trace IS NOT NULL
                        )
                    )
                    SELECT *
                    FROM (
                      SELECT * FROM latest_logs
                      UNION
                      SELECT * FROM error_logs
                    ) AS combined_logs
                    ORDER BY created_at ASC
                    """
                ),
                {"execution_id": execution_id, "limit": limit},
            ).mappings().all()
            return [dict(row) for row in rows]

    def fetch_execution_runs(self, execution_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT *
                    FROM olist_admin.sync_runs
                    WHERE execution_id = :execution_id
                    ORDER BY started_at ASC, entity_name ASC
                    """
                ),
                {"execution_id": execution_id},
            ).mappings().all()
            return [dict(row) for row in rows]

    def fetch_olist_settings(self) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT *
                    FROM public.olist_settings
                    WHERE id = 'default'
                    """
                )
            ).mappings().first()
            return dict(row) if row else None

    def renew_olist_access_token(self) -> dict[str, Any]:
        settings = self.fetch_olist_settings() or {}
        client_id = str(settings.get("client_id") or "").strip()
        client_secret = str(settings.get("client_secret") or "").strip()
        refresh_token = str(settings.get("refresh_token") or "").strip()

        if not client_id or not client_secret:
            raise RuntimeError("Client ID e Client Secret da Olist não estão configurados para renovar o token.")
        if not refresh_token:
            raise RuntimeError("Não existe refresh token persistido para renovar a sessão OAuth da Olist.")

        try:
            response = requests.post(
                OLIST_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                },
                headers={"Accept": "application/json"},
                timeout=max(self.settings.timeout_seconds, 30),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = self._extract_olist_http_error(exc)
            raise RuntimeError(f"Falha ao renovar o token OAuth da Olist: {detail}") from exc

        try:
            token_payload = response.json()
        except ValueError as exc:
            raise RuntimeError("A Olist retornou uma resposta inválida ao renovar o token OAuth.") from exc

        access_token = str(token_payload.get("access_token") or "").strip()
        if not access_token:
            raise RuntimeError("A Olist não retornou um access_token ao renovar a sessão OAuth.")

        new_refresh_token = str(token_payload.get("refresh_token") or refresh_token).strip()
        now = utc_now()
        access_token_expires_at = now + timedelta(
            seconds=self._as_int(token_payload.get("expires_in"), ACCESS_TOKEN_FALLBACK_SECONDS)
        )
        refresh_token_expires_at = now + timedelta(
            seconds=self._as_int(token_payload.get("refresh_expires_in"), REFRESH_TOKEN_FALLBACK_SECONDS)
        )

        with self.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE public.olist_settings
                    SET access_token = :access_token,
                        refresh_token = :refresh_token,
                        access_token_expires_at = :access_token_expires_at,
                        refresh_token_expires_at = :refresh_token_expires_at,
                        token_type = :token_type,
                        scope = :scope,
                        status = :status,
                        token_status = :token_status,
                        message = :message,
                        last_token_refresh_at = NOW(),
                        updated_at = NOW()
                    WHERE id = 'default'
                    """
                ),
                {
                    "access_token": access_token,
                    "refresh_token": new_refresh_token,
                    "access_token_expires_at": access_token_expires_at,
                    "refresh_token_expires_at": refresh_token_expires_at,
                    "token_type": str(token_payload.get("token_type") or settings.get("token_type") or "Bearer"),
                    "scope": str(token_payload.get("scope") or settings.get("scope") or "openid"),
                    "status": "Conectada",
                    "token_status": "Token ativo",
                    "message": "Token renovado automaticamente durante a extração Olist.",
                },
            )

        refreshed = self.fetch_olist_settings()
        if refreshed is None:
            raise RuntimeError("Falha ao recarregar a configuração Olist após renovar o token.")
        return refreshed

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        try:
            return int(value or default)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _extract_olist_http_error(exc: requests.RequestException) -> str:
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                for key in ("error_description", "mensagem", "message", "error"):
                    value = payload.get(key)
                    if value:
                        return str(value)
            if response.text:
                return response.text
            return f"HTTP {response.status_code}"
        return str(exc)
