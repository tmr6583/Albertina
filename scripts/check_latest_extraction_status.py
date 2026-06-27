from __future__ import annotations

import json
from pathlib import Path

import requests


BASE_URL = "http://127.0.0.1:8000/api"
OUTPUT_PATH = Path(r"c:\GitHubLocal\Albertina\.latest_extraction_status.json")


def main() -> int:
    session = requests.Session()
    login = session.post(
        f"{BASE_URL}/auth/login",
        json={"email": "admin@empresa.com", "password": "Betin@01012023"},
        timeout=30,
    )
    login.raise_for_status()
    token = login.json()["token"]
    session.headers.update({"Authorization": f"Bearer {token}"})

    overview = session.get(f"{BASE_URL}/extraction/overview", timeout=30)
    overview.raise_for_status()
    overview_payload = overview.json()

    output: dict[str, object] = {"overview": overview_payload}
    recent_executions = overview_payload.get("recentExecutions") or []
    active_execution_id = overview_payload.get("activeExecutionId")
    target_execution_id = active_execution_id or (recent_executions[0]["executionId"] if recent_executions else None)
    if target_execution_id:
        execution = session.get(f"{BASE_URL}/extraction/executions/{target_execution_id}", timeout=30)
        execution.raise_for_status()
        output["execution"] = execution.json()

    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(OUTPUT_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
