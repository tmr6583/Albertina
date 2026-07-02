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
    args = parser.parse_args()

    try:
        if args.command in {None, "start-incremental"}:
            payload = extraction_service.start_full_sync(user_id=args.user_id, actor_email=args.actor_email)
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
