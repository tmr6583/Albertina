from __future__ import annotations

import argparse
from pathlib import Path

import psycopg


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / "backend" / ".env"
DEFAULT_REDIRECT_URI = "http://localhost:3500/olist/callback"
DEFAULT_API_BASE_URL = "https://api.tiny.com.br/public-api/v3/"
DEFAULT_AUTH_MODE = "OAuth 2 Authorization Code"


def load_env(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def derive_connection_state(
    client_secret: str,
    access_token: str,
    refresh_token: str,
    connect_attempt: object,
) -> tuple[str, str, str]:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Executa reset operacional da Olist preservando o client_secret por padrão. "
            "Também pode apenas restaurar as configuracoes da conexao."
        )
    )
    parser.add_argument(
        "--settings-only",
        action="store_true",
        help="Atualiza apenas public.olist_settings sem limpar tabelas operacionais.",
    )
    parser.add_argument(
        "--wipe-client-secret",
        action="store_true",
        help="Nao preserva o client_secret durante a operacao. Use apenas se quiser reset total da configuracao.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula a operacao e exibe os valores que seriam aplicados.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = load_env(ENV_PATH)
    db_url = env["ALBERTINA_DATABASE_URL"]
    env_client_id = env.get("OLIST_CLIENT_ID", "").strip()
    env_client_secret = env.get("OLIST_CLIENT_SECRET", "").strip()
    env_redirect_uri = env.get("OLIST_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip() or DEFAULT_REDIRECT_URI

    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    client_id,
                    client_secret,
                    redirect_uri,
                    api_base_url,
                    auth_mode,
                    access_token,
                    refresh_token,
                    last_connect_attempt_at
                FROM public.olist_settings
                WHERE id = 'default'
                """
            )
            current = cur.fetchone()

            if current is None:
                raise RuntimeError("public.olist_settings/default nao foi encontrado.")

            current_client_id = str(current[1] or "").strip()
            current_client_secret = str(current[2] or "").strip()
            current_redirect_uri = str(current[3] or "").strip()
            current_api_base_url = str(current[4] or "").strip()
            current_auth_mode = str(current[5] or "").strip()
            current_access_token = str(current[6] or "").strip()
            current_refresh_token = str(current[7] or "").strip()
            current_connect_attempt = current[8]

            target_client_id = env_client_id or current_client_id
            target_client_secret = ""
            if not args.wipe_client_secret:
                target_client_secret = current_client_secret or env_client_secret

            target_redirect_uri = current_redirect_uri or env_redirect_uri
            target_api_base_url = current_api_base_url or DEFAULT_API_BASE_URL
            target_auth_mode = current_auth_mode or DEFAULT_AUTH_MODE

            keep_tokens = args.settings_only
            target_access_token = current_access_token if keep_tokens else ""
            target_refresh_token = current_refresh_token if keep_tokens else ""
            target_connect_attempt = current_connect_attempt if keep_tokens else None

            status_value, token_status, message = derive_connection_state(
                client_secret=target_client_secret,
                access_token=target_access_token,
                refresh_token=target_refresh_token,
                connect_attempt=target_connect_attempt,
            )

            if args.dry_run:
                print("mode=dry-run")
                print(f"settings_only={args.settings_only}")
                print(f"wipe_client_secret={args.wipe_client_secret}")
                print(f"target_client_id={target_client_id}")
                print(f"target_client_secret_len={len(target_client_secret)}")
                print(f"target_status={status_value}")
                print(f"target_token_status={token_status}")
                return 0

            if not args.settings_only:
                cur.execute(
                    """
                    SELECT quote_ident(table_schema) || '.' || quote_ident(table_name)
                    FROM information_schema.tables
                    WHERE table_schema IN ('olist_admin', 'olist_raw', 'olist_core')
                      AND table_type = 'BASE TABLE'
                    ORDER BY table_schema, table_name
                    """
                )
                tables = [row[0] for row in cur.fetchall()]
                if tables:
                    cur.execute("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE")

                cur.execute("SELECT to_regclass('public.connection_logs') IS NOT NULL")
                if cur.fetchone()[0]:
                    cur.execute("TRUNCATE TABLE public.connection_logs")

            cur.execute(
                """
                INSERT INTO public.olist_settings (
                    id,
                    client_id,
                    client_secret,
                    redirect_uri,
                    api_base_url,
                    auth_mode,
                    status,
                    token_status,
                    message,
                    access_token,
                    refresh_token,
                    last_connect_attempt_at,
                    last_token_refresh_at,
                    created_at,
                    updated_at,
                    access_token_expires_at,
                    refresh_token_expires_at,
                    token_type,
                    scope,
                    oauth_state,
                    oauth_state_expires_at,
                    last_callback_at
                )
                VALUES (
                    'default',
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NULL,
                    NOW(),
                    NOW(),
                    NULL,
                    NULL,
                    'Bearer',
                    'openid',
                    NULL,
                    NULL,
                    NULL
                )
                ON CONFLICT (id) DO UPDATE
                SET client_id = EXCLUDED.client_id,
                    client_secret = EXCLUDED.client_secret,
                    redirect_uri = EXCLUDED.redirect_uri,
                    api_base_url = EXCLUDED.api_base_url,
                    auth_mode = EXCLUDED.auth_mode,
                    status = EXCLUDED.status,
                    token_status = EXCLUDED.token_status,
                    message = EXCLUDED.message,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    last_connect_attempt_at = EXCLUDED.last_connect_attempt_at,
                    last_token_refresh_at = EXCLUDED.last_token_refresh_at,
                    updated_at = NOW(),
                    access_token_expires_at = EXCLUDED.access_token_expires_at,
                    refresh_token_expires_at = EXCLUDED.refresh_token_expires_at,
                    token_type = EXCLUDED.token_type,
                    scope = EXCLUDED.scope,
                    oauth_state = EXCLUDED.oauth_state,
                    oauth_state_expires_at = EXCLUDED.oauth_state_expires_at,
                    last_callback_at = EXCLUDED.last_callback_at
                """,
                (
                    target_client_id,
                    target_client_secret,
                    target_redirect_uri,
                    target_api_base_url,
                    target_auth_mode,
                    status_value,
                    token_status,
                    message,
                    target_access_token or None,
                    target_refresh_token or None,
                    target_connect_attempt,
                ),
            )

            if not args.settings_only:
                cur.execute(
                    """
                    SELECT quote_ident(schemaname) || '.' || quote_ident(matviewname)
                    FROM pg_matviews
                    WHERE schemaname = 'olist_mart'
                    ORDER BY matviewname
                    """
                )
                for row in cur.fetchall():
                    cur.execute(f"REFRESH MATERIALIZED VIEW {row[0]}")

            print(f"mode={'settings-only' if args.settings_only else 'full-reset'}")
            print(f"client_secret_len={len(target_client_secret)}")
            print(f"status={status_value}")
            print(f"token_status={token_status}")
            print(f"wipe_client_secret={args.wipe_client_secret}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
