from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generator
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import ExtractionSettings


POSTGRES_PREFIXES = ("postgres://", "postgresql://")
EXTRACTION_ADVISORY_LOCK_KEY = 48203172001


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
              payload JSONB NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            "ALTER TABLE olist_raw.api_payloads ADD COLUMN IF NOT EXISTS external_key TEXT NOT NULL DEFAULT ''",
            """
            UPDATE olist_raw.api_payloads
            SET external_key = COALESCE(NULLIF(external_key, ''), CONCAT(endpoint_path, '|', COALESCE(olist_object_id::TEXT, 'singleton')))
            WHERE external_key = ''
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_api_payloads_external_key
            ON olist_raw.api_payloads (tenant_id, entity_name, endpoint_path, external_key)
            """,
            "CREATE INDEX IF NOT EXISTS idx_sync_runs_execution_id ON olist_admin.sync_runs (execution_id, started_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_sync_run_logs_execution_id ON olist_admin.sync_run_logs (execution_id, created_at ASC)",
        ]

        trigger_statements = [
            ("olist_admin.tenants", "trg_tenants_updated_at"),
            ("olist_admin.user_tenants", "trg_user_tenants_updated_at"),
            ("olist_admin.sync_runs", "trg_sync_runs_updated_at"),
            ("olist_admin.sync_watermarks", "trg_sync_watermarks_updated_at"),
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
        tenant_id: str,
        entity_name: str,
        endpoint_path: str,
        external_key: str,
        olist_object_id: int | None,
        parent_olist_object_id: int | None,
        source_updated_at: datetime | None,
        sync_run_id: str,
        payload_hash_value: str,
        payload: dict[str, Any] | list[Any] | str | int | float | bool | None,
        connection: Any | None = None,
    ) -> UpsertResult:
        if connection is not None:
            return self._upsert_raw_payload_on_connection(
                connection=connection,
                tenant_id=tenant_id,
                entity_name=entity_name,
                endpoint_path=endpoint_path,
                external_key=external_key,
                olist_object_id=olist_object_id,
                parent_olist_object_id=parent_olist_object_id,
                source_updated_at=source_updated_at,
                sync_run_id=sync_run_id,
                payload_hash_value=payload_hash_value,
                payload=payload,
            )

        with self.begin() as current_connection:
            return self._upsert_raw_payload_on_connection(
                connection=current_connection,
                tenant_id=tenant_id,
                entity_name=entity_name,
                endpoint_path=endpoint_path,
                external_key=external_key,
                olist_object_id=olist_object_id,
                parent_olist_object_id=parent_olist_object_id,
                source_updated_at=source_updated_at,
                sync_run_id=sync_run_id,
                payload_hash_value=payload_hash_value,
                payload=payload,
            )

    def _upsert_raw_payload_on_connection(
        self,
        *,
        connection: Any,
        tenant_id: str,
        entity_name: str,
        endpoint_path: str,
        external_key: str,
        olist_object_id: int | None,
        parent_olist_object_id: int | None,
        source_updated_at: datetime | None,
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
                  CAST(:payload AS JSONB)
                )
                ON CONFLICT (tenant_id, entity_name, endpoint_path, external_key) DO UPDATE
                SET olist_object_id = EXCLUDED.olist_object_id,
                    parent_olist_object_id = EXCLUDED.parent_olist_object_id,
                    source_updated_at = EXCLUDED.source_updated_at,
                    extracted_at = EXCLUDED.extracted_at,
                    sync_run_id = EXCLUDED.sync_run_id,
                    payload_hash = EXCLUDED.payload_hash,
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
                "payload": json.dumps(payload, default=str),
            },
        )

        if existing is None:
            return UpsertResult(inserted=1, updated=0)
        if existing["payload_hash"] != payload_hash_value:
            return UpsertResult(inserted=0, updated=1)
        return UpsertResult(inserted=0, updated=0)

    def fetch_execution_summary(self, execution_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                      execution_id,
                      MIN(started_at) AS started_at,
                      MAX(finished_at) AS finished_at,
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
                      MIN(started_at) AS started_at,
                      MAX(finished_at) AS finished_at,
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
                    SELECT *
                    FROM olist_admin.sync_run_logs
                    WHERE execution_id = :execution_id
                    ORDER BY created_at ASC
                    LIMIT :limit
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
