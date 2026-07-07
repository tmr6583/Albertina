from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from backend.olist_extraction.config import build_settings
from backend.olist_extraction.load import ExtractionRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspeciona payloads RAW da Olist por entidade.")
    parser.add_argument("entity_name", help="Nome da entidade no RAW.")
    parser.add_argument("--limit", type=int, default=3, help="Quantidade maxima de amostras.")
    parser.add_argument("--endpoint-contains", default="", help="Filtra por trecho do endpoint.")
    parser.add_argument("--endpoint-equals", default="", help="Filtra por endpoint exato.")
    parser.add_argument("--list-endpoints", action="store_true", help="Lista os endpoints distintos da entidade.")
    args = parser.parse_args()

    repository = ExtractionRepository(build_settings())
    if args.list_endpoints:
        query = text(
            """
            SELECT endpoint_path, COUNT(*) AS total
            FROM olist_raw.api_payloads
            WHERE entity_name = :entity_name
            GROUP BY endpoint_path
            ORDER BY endpoint_path
            """
        )
        with repository.engine.connect() as connection:
            rows = connection.execute(query, {"entity_name": args.entity_name}).mappings().all()
        for row in rows:
            print(f"{row['endpoint_path']} | total={row['total']}")
        return 0

    query = text(
        """
        SELECT entity_name, endpoint_path, external_key, olist_object_id, payload
        FROM olist_raw.api_payloads
        WHERE entity_name = :entity_name
          AND (:endpoint_equals = '' OR endpoint_path = :endpoint_equals)
          AND (:endpoint_contains = '' OR endpoint_path ILIKE :endpoint_filter)
        ORDER BY created_at DESC
        LIMIT :limit
        """
    )

    with repository.engine.connect() as connection:
        rows = connection.execute(
            query,
            {
                "entity_name": args.entity_name,
                "limit": args.limit,
                "endpoint_equals": args.endpoint_equals,
                "endpoint_contains": args.endpoint_contains,
                "endpoint_filter": f"%{args.endpoint_contains}%",
            },
        ).mappings().all()

    for index, row in enumerate(rows, start=1):
        payload = row["payload"]
        keys = sorted(payload.keys()) if isinstance(payload, dict) else []
        print(f"--- sample {index} ---")
        print(f"entity_name={row['entity_name']}")
        print(f"endpoint_path={row['endpoint_path']}")
        print(f"external_key={row['external_key']}")
        print(f"olist_object_id={row['olist_object_id']}")
        print(f"top_level_keys={keys}")
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str)[:4000])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
