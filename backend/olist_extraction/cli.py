from __future__ import annotations

import argparse
import json
import sys

from .service import extraction_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Executa a extração completa da API Olist para o Supabase.")
    parser.add_argument("--user-id", required=True, help="ID do usuário Albertina que dispara a execução.")
    parser.add_argument("--actor-email", required=True, help="E-mail do usuário que dispara a execução.")
    args = parser.parse_args()

    try:
        payload = extraction_service.start_full_sync(user_id=args.user_id, actor_email=args.actor_email)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
