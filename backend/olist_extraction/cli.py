from __future__ import annotations

import argparse
import json
import sys

from .service import extraction_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Executa a extração completa da API Olist para o Supabase.")
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start-incremental", help="Inicia a execução incremental padrão.")
    start_parser.add_argument("--user-id", required=True, help="ID do usuário Albertina que dispara a execução.")
    start_parser.add_argument("--actor-email", required=True, help="E-mail do usuário que dispara a execução.")

    worker_parser = subparsers.add_parser("run-worker", help="Executa um worker dedicado de extração.")
    worker_parser.add_argument("--execution-id", required=True, help="ID global da execução.")
    worker_parser.add_argument("--user-id", required=True, help="ID do usuário Albertina que dispara a execução.")
    worker_parser.add_argument("--actor-email", required=True, help="E-mail do usuário que dispara a execução.")
    worker_parser.add_argument("--execution-type", required=True, choices=("incremental", "reconciliation"))
    worker_parser.add_argument(
        "--workflow-names-json",
        required=True,
        help="Lista JSON com as entidades selecionadas para a execução.",
    )
    sync_parser = subparsers.add_parser("sync-core", help="Promove os payloads RAW para CORE e atualiza a MART.")
    sync_parser.add_argument("--user-id", required=False, help="ID do usuário Albertina associado ao tenant padrão.")
    sync_parser.add_argument(
        "--entity-names-json",
        required=False,
        default="[]",
        help="Lista JSON opcional com as entidades a sincronizar. Vazio = todas.",
    )
    sync_parser.add_argument(
        "--skip-marts",
        action="store_true",
        help="Executa apenas a promoção RAW para CORE sem refresh da MART.",
    )
    args = parser.parse_args()

    try:
        if args.command in {None, "start-incremental"}:
            payload = extraction_service.start_full_sync(user_id=args.user_id, actor_email=args.actor_email)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if args.command == "sync-core":
            entity_names = json.loads(args.entity_names_json) if args.entity_names_json else []
            payload = extraction_service.run_core_sync(
                user_id=args.user_id,
                entity_names=entity_names or None,
                refresh_marts=not args.skip_marts,
            )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        workflow_names = json.loads(args.workflow_names_json)
        extraction_service.run_worker_execution(
            execution_id=args.execution_id,
            user_id=args.user_id,
            actor_email=args.actor_email,
            execution_type=args.execution_type,
            workflow_names=workflow_names,
        )
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
