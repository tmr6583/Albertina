from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.olist_extraction.config import build_settings
from backend.olist_extraction.load import to_sqlalchemy_url


def main() -> None:
    settings = build_settings()
    engine = create_engine(to_sqlalchemy_url(settings.database_url), future=True)

    with engine.connect() as connection:
        active_execution_id = connection.execute(
            text(
                """
                SELECT execution_id::text
                FROM olist_admin.sync_runs
                WHERE status = 'running'
                  AND execution_id IS NOT NULL
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
        ).scalar()

        print("ACTIVE_EXECUTION_ID:", active_execution_id)
        if not active_execution_id:
            return

        runs = connection.execute(
            text(
                """
                SELECT
                  entity_name,
                  sync_mode,
                  status,
                  request_count,
                  success_count,
                  error_count,
                  to_char(started_at, 'DD/MM/YYYY HH24:MI:SS') AS started_at,
                  to_char(updated_at, 'DD/MM/YYYY HH24:MI:SS') AS updated_at,
                  details->>'currentStep' AS current_step,
                  details->>'currentEndpointPath' AS current_endpoint,
                  details->>'heartbeatAt' AS heartbeat_at,
                  details->>'sourceContextsProcessed' AS source_processed,
                  details->>'sourceContextsTotal' AS source_total
                FROM olist_admin.sync_runs
                WHERE execution_id::text = :execution_id
                ORDER BY started_at DESC
                LIMIT 12
                """
            ),
            {"execution_id": active_execution_id},
        ).mappings().all()

        error_logs = connection.execute(
            text(
                """
                SELECT
                  to_char(created_at, 'DD/MM/YYYY HH24:MI:SS') AS created_at,
                  entity_name,
                  level,
                  stage,
                  message,
                  left(COALESCE(stack_trace, ''), 900) AS stack_trace_preview
                FROM olist_admin.sync_run_logs
                WHERE execution_id::text = :execution_id
                  AND (
                    error_count > 0
                    OR UPPER(level) = 'ERROR'
                    OR stack_trace IS NOT NULL
                  )
                ORDER BY created_at DESC
                LIMIT 12
                """
            ),
            {"execution_id": active_execution_id},
        ).mappings().all()

        latest_logs = connection.execute(
            text(
                """
                SELECT
                  to_char(created_at, 'DD/MM/YYYY HH24:MI:SS') AS created_at,
                  entity_name,
                  level,
                  stage,
                  message
                FROM olist_admin.sync_run_logs
                WHERE execution_id::text = :execution_id
                ORDER BY created_at DESC
                LIMIT 10
                """
            ),
            {"execution_id": active_execution_id},
        ).mappings().all()

    print("RUNS:", json.dumps([dict(row) for row in runs], ensure_ascii=False, indent=2))
    print("ERROR_LOGS:", json.dumps([dict(row) for row in error_logs], ensure_ascii=False, indent=2))
    print("LATEST_LOGS:", json.dumps([dict(row) for row in latest_logs], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

