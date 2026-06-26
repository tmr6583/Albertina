from __future__ import annotations

import argparse
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg


POSTGRES_PREFIXES = ("postgres://", "postgresql://")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "supabase" / "migrations"
MIGRATIONS_TABLE = "public.albertina_schema_migrations"


@dataclass(frozen=True)
class MigrationFile:
    version: str
    name: str
    path: Path

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def get_database_url() -> str:
    database_url = os.getenv("ALBERTINA_DATABASE_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "Defina ALBERTINA_DATABASE_URL ou DATABASE_URL apontando para o PostgreSQL/Supabase."
        )
    if not database_url.lower().startswith(POSTGRES_PREFIXES):
        raise RuntimeError("O bootstrap suporta apenas PostgreSQL/Supabase.")
    return database_url


def discover_migrations() -> list[MigrationFile]:
    migrations: list[MigrationFile] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version, _, suffix = path.name.partition("_")
        migrations.append(MigrationFile(version=version, name=suffix or path.stem, path=path))
    return migrations


def ensure_migrations_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
              version TEXT PRIMARY KEY,
              filename TEXT NOT NULL,
              checksum TEXT NOT NULL,
              applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    conn.commit()


def fetch_applied_migrations(conn: psycopg.Connection) -> dict[str, tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(f"SELECT version, filename, checksum FROM {MIGRATIONS_TABLE} ORDER BY version")
        return {row[0]: (row[1], row[2]) for row in cur.fetchall()}


def apply_migration(conn: psycopg.Connection, migration: MigrationFile, dry_run: bool) -> None:
    sql = migration.path.read_text(encoding="utf-8")
    if dry_run:
        print(f"[DRY-RUN] Aplicaria {migration.filename}")
        return

    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            f"""
            INSERT INTO {MIGRATIONS_TABLE} (version, filename, checksum)
            VALUES (%s, %s, %s)
            ON CONFLICT (version) DO UPDATE
            SET filename = EXCLUDED.filename,
                checksum = EXCLUDED.checksum,
                applied_at = NOW()
            """,
            (migration.version, migration.filename, migration.checksum),
        )
    conn.commit()
    print(f"[OK] {migration.filename}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aplica as migrations SQL da Albertina no Supabase/PostgreSQL em ordem."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lista as migrations pendentes sem aplicar.",
    )
    args = parser.parse_args()

    try:
        database_url = get_database_url()
        migrations = discover_migrations()
        if not migrations:
            raise RuntimeError("Nenhuma migration foi encontrada em supabase/migrations.")

        with psycopg.connect(database_url, autocommit=False) as conn:
            ensure_migrations_table(conn)
            applied = fetch_applied_migrations(conn)

            pending = []
            for migration in migrations:
                applied_entry = applied.get(migration.version)
                if applied_entry is None:
                    pending.append(migration)
                    continue

                applied_filename, applied_checksum = applied_entry
                if applied_filename != migration.filename or applied_checksum != migration.checksum:
                    raise RuntimeError(
                        "Migration divergente detectada para a versao "
                        f"{migration.version}: banco={applied_filename}, arquivo_atual={migration.filename}."
                    )

            if not pending:
                print("Nenhuma migration pendente.")
                return 0

            print(f"Migrations pendentes: {len(pending)}")
            for migration in pending:
                apply_migration(conn, migration, args.dry_run)

        print("Bootstrap concluido.")
        return 0
    except Exception as exc:  # pragma: no cover - handoff operacional
        print(f"Erro no bootstrap: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
