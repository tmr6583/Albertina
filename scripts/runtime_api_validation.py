from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


BASE_URL = "http://127.0.0.1:8000/api"
OUTPUT_PATH = Path(r"c:\GitHubLocal\Albertina\.runtime_api_validation.json")


@dataclass
class ApiResponse:
    status: int
    data: object


def request_json(
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, object] | None = None,
) -> ApiResponse:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return ApiResponse(status=response.getcode(), data=json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {"detail": exc.reason}
        except json.JSONDecodeError:
            data = {"detail": raw or exc.reason}
        return ApiResponse(status=exc.code, data=data)


def require_ok(response: ApiResponse, context: str) -> object:
    if 200 <= response.status < 300:
        return response.data
    raise RuntimeError(f"{context} falhou com HTTP {response.status}: {response.data}")


def main() -> int:
    results: dict[str, object] = {"baseUrl": BASE_URL, "checks": []}

    def add_check(name: str, status: str, detail: object) -> None:
        results["checks"].append({"name": name, "status": status, "detail": detail})

    try:
        health = require_ok(request_json("/health"), "health")
        add_check("health", "ok", health)

        login = require_ok(
            request_json(
                "/auth/login",
                method="POST",
                payload={"email": "admin@empresa.com", "password": "Betin@01012023"},
            ),
            "login",
        )
        token = str(login["token"])
        add_check("login", "ok", {"email": login["user"]["email"]})

        me = require_ok(request_json("/auth/me", token=token), "auth.me")
        add_check("auth.me", "ok", {"email": me["email"]})

        users_before = require_ok(request_json("/users", token=token), "users.list.before")
        add_check("users.list.before", "ok", {"count": len(users_before)})

        unique = uuid4().hex[:8]
        email = f"teste.{unique}@empresa.com"
        created = require_ok(
            request_json(
                "/users",
                method="POST",
                token=token,
                payload={"email": email, "password": "Senha@123", "status": "Ativo"},
            ),
            "users.create",
        )
        user_id = str(created["id"])
        add_check("users.create", "ok", {"id": user_id, "email": created["email"]})

        updated_password = require_ok(
            request_json(
                f"/users/{user_id}/password",
                method="PATCH",
                token=token,
                payload={"password": "NovaSenha@123", "confirmPassword": "NovaSenha@123"},
            ),
            "users.password",
        )
        add_check("users.password", "ok", updated_password)

        inactive = require_ok(
            request_json(
                f"/users/{user_id}/status",
                method="PATCH",
                token=token,
                payload={"status": "Inativo"},
            ),
            "users.inactive",
        )
        add_check("users.inactive", "ok", {"status": inactive["status"]})

        active = require_ok(
            request_json(
                f"/users/{user_id}/status",
                method="PATCH",
                token=token,
                payload={"status": "Ativo"},
            ),
            "users.active",
        )
        add_check("users.active", "ok", {"status": active["status"]})

        deleted = require_ok(
            request_json(f"/users/{user_id}", method="DELETE", token=token),
            "users.delete",
        )
        add_check("users.delete", "ok", deleted)

        audit = require_ok(request_json("/audit", token=token), "audit.list")
        add_check("audit.list", "ok", {"count": len(audit)})

        connections = require_ok(request_json("/connections/overview", token=token), "connections.overview")
        add_check(
            "connections.overview",
            "ok",
            {
                "status": connections["olist"]["status"],
                "tokenStatus": connections["olist"]["tokenStatus"],
            },
        )

        extraction_overview = require_ok(
            request_json("/extraction/overview", token=token),
            "extraction.overview",
        )
        add_check(
            "extraction.overview",
            "ok",
            {
                "running": extraction_overview["running"],
                "recentExecutions": len(extraction_overview["recentExecutions"]),
            },
        )

        recent_executions = extraction_overview["recentExecutions"]
        if recent_executions:
            execution_id = str(recent_executions[0]["executionId"])
            execution = require_ok(
                request_json(f"/extraction/executions/{execution_id}", token=token),
                "extraction.execution",
            )
            add_check(
                "extraction.execution",
                "ok",
                {
                    "executionId": execution_id,
                    "logCount": len(execution["logs"]),
                    "errorCount": execution["errorCount"],
                },
            )
        else:
            add_check("extraction.execution", "skipped", {"reason": "Nenhuma execução recente."})

        api_test = request_json("/connections/olist/api-test", token=token)
        if 200 <= api_test.status < 300:
            add_check("connections.olist.api-test", "ok", {"status": api_test.data["status"]})
        else:
            add_check("connections.olist.api-test", "error", api_test.data)

        logout = require_ok(request_json("/auth/logout", method="POST", token=token), "auth.logout")
        add_check("auth.logout", "ok", logout)
        results["status"] = "ok"
    except Exception as exc:  # pragma: no cover - runtime helper
        results["status"] = "error"
        results["error"] = str(exc)

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=True, indent=2), encoding="utf-8")
    print(str(OUTPUT_PATH))
    return 0 if results.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
