from __future__ import annotations

import json
from pathlib import Path

from backend.olist_extraction.config import build_settings
from backend.olist_extraction.load import ExtractionRepository


OUTPUT_PATH = Path(r"c:\GitHubLocal\Albertina\.active_extraction_status.json")


def main() -> int:
    repository = ExtractionRepository(build_settings())
    execution_id = repository.fetch_active_execution_id()
    payload: dict[str, object] = {"activeExecutionId": execution_id}
    if execution_id:
        payload["summary"] = repository.fetch_execution_summary(execution_id)
        payload["runs"] = repository.fetch_execution_runs(execution_id)
        payload["logs"] = repository.fetch_execution_logs(execution_id, limit=50)
    else:
        recent = repository.fetch_recent_executions(limit=3)
        payload["recentExecutions"] = recent

    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
