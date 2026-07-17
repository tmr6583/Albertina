from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"
CERT_FILE = ROOT / "files" / "Certificado_Supabase_Albertina.crt"

load_dotenv(ENV_FILE)
mcp = FastMCP("MCP-Supabase")


class InBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LsIn(InBase):
    sch: str | None = Field(default=None, description="Schema ou null.")
    kind: str = Field(default="all", description="all|table|view|matview|foreign")
    limit: int = Field(default=200, ge=1, le=5000, description="Maximo de itens.")


class ColsIn(InBase):
    sch: str = Field(default="public", description="Schema.")
    obj: str = Field(..., min_length=1, description="Tabela/view.")


class SqlIn(InBase):
    sql: str = Field(..., min_length=1, description="SQL completo.")
    max_rows: int = Field(default=200, ge=0, le=10000, description="Limite de linhas no retorno.")


def _j(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, separators=(",", ":"), default=str)


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _conn_kwargs() -> dict[str, Any]:
    url = _env("ALBERTINA_DATABASE_URL", "DATABASE_URL")
    if url:
        return {"conninfo": url, "autocommit": True, "row_factory": dict_row}

    host = _env("SUPABASE_HOST")
    if not host:
        raise RuntimeError("Defina SUPABASE_HOST ou ALBERTINA_DATABASE_URL.")

    kwargs: dict[str, Any] = {
        "host": host,
        "port": int(_env("SUPABASE_PORT", default="5432")),
        "dbname": _env("SUPABASE_DATABASE", default="postgres"),
        "user": _env("SUPABASE_USER", default="postgres"),
        "password": _env("SUPABASE_PASSWORD"),
        "sslmode": _env("SUPABASE_SSLMODE", default="verify-full"),
        "connect_timeout": int(_env("SUPABASE_CONNECT_TIMEOUT", default="15")),
        "application_name": "MCP-Supabase",
        "autocommit": True,
        "row_factory": dict_row,
    }

    cert = Path(_env("SUPABASE_SSLROOTCERT", default=str(CERT_FILE)))
    if cert.exists():
        kwargs["sslrootcert"] = str(cert)
    elif kwargs["sslmode"] == "verify-full":
        kwargs["sslmode"] = "require"

    return kwargs


def _connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**_conn_kwargs())


@mcp.tool(name="ping")
def ping() -> str:
    """Testa a conexao."""

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select
              current_database() as db,
              current_user as usr,
              current_schema() as sch,
              current_setting('server_version') as ver,
              now() as ts
            """
        )
        row = cur.fetchone()
    return _j({"ok": 1, "db": row["db"], "usr": row["usr"], "sch": row["sch"], "ver": row["ver"], "ts": row["ts"]})


@mcp.tool(name="ls")
def ls(params: LsIn) -> str:
    """Lista objetos do banco."""

    kinds = {
        "all": None,
        "table": "BASE TABLE",
        "view": "VIEW",
        "foreign": "FOREIGN",
    }
    where = [
        "table_schema not in ('information_schema','pg_catalog')",
        "table_schema not like 'pg_toast%%'",
    ]
    args: list[Any] = []

    if params.sch:
        where.append("table_schema = %s")
        args.append(params.sch)

    if params.kind in kinds and kinds[params.kind]:
        where.append("table_type = %s")
        args.append(kinds[params.kind])

    sql = f"""
        select table_schema as s, table_name as n, table_type as t
        from information_schema.tables
        where {' and '.join(where)}
        order by table_schema, table_name
        limit %s
    """
    args.append(params.limit)

    rows: list[dict[str, Any]]
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(args))
        rows = list(cur.fetchall())

        if params.kind == "matview":
            cur.execute(
                """
                select schemaname as s, matviewname as n, 'MATERIALIZED VIEW' as t
                from pg_matviews
                where (%s is null or schemaname = %s)
                order by schemaname, matviewname
                limit %s
                """,
                (params.sch, params.sch, params.limit),
            )
            rows = list(cur.fetchall())

    return _j({"ok": 1, "items": rows})


@mcp.tool(name="cols")
def cols(params: ColsIn) -> str:
    """Lista colunas."""

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select
              ordinal_position as pos,
              column_name as n,
              data_type as t,
              is_nullable as nulls,
              column_default as d
            from information_schema.columns
            where table_schema = %s
              and table_name = %s
            order by ordinal_position
            """,
            (params.sch, params.obj),
        )
        rows = list(cur.fetchall())
    return _j({"ok": 1, "sch": params.sch, "obj": params.obj, "cols": rows})


@mcp.tool(name="sql")
def sql(params: SqlIn) -> str:
    """Executa SQL completo."""

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(params.sql)
        desc = cur.description
        if desc:
            rows = list(cur.fetchall())
            if params.max_rows >= 0:
                rows = rows[: params.max_rows]
            return _j(
                {
                    "ok": 1,
                    "cmd": cur.statusmessage,
                    "cols": [c.name for c in desc],
                    "rows": rows,
                    "n": len(rows),
                }
            )
        return _j({"ok": 1, "cmd": cur.statusmessage, "rows_affected": cur.rowcount})


if __name__ == "__main__":
    mcp.run()
