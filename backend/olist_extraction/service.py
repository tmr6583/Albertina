from __future__ import annotations

import json
import os
import threading
import urllib.request
from datetime import datetime
from typing import Any
from uuid import uuid4

from .catalog import WORKFLOWS, list_non_incremental_workflows
from .config import build_settings
from .extract import WorkflowRunner
from .load import ExtractionRepository, utc_now
from .transform import parse_olist_datetime


# #region debug-point extraction-ui-stall-reporting
def _debug_report(hypothesis_id: str, location: str, msg: str, data: dict[str, Any] | None = None) -> None:
    try:
        debug_server_url = "http://127.0.0.1:7777/event"
        debug_session_id = "extraction-ui-stall"
        debug_env_path = os.path.join(".dbg", "extraction-ui-stall.env")
        if os.path.exists(debug_env_path):
            with open(debug_env_path, "r", encoding="utf-8") as debug_env_file:
                for raw_line in debug_env_file:
                    line = raw_line.strip()
                    if line.startswith("DEBUG_SERVER_URL="):
                        debug_server_url = line.split("=", 1)[1].strip() or debug_server_url
                    elif line.startswith("DEBUG_SESSION_ID="):
                        debug_session_id = line.split("=", 1)[1].strip() or debug_session_id
        payload = {
            "sessionId": debug_session_id,
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "msg": msg,
            "data": data or {},
            "ts": int(utc_now().timestamp() * 1000),
        }
        request = urllib.request.Request(
            debug_server_url,
            data=json.dumps(payload, default=str).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(request, timeout=2).read()
    except Exception:
        pass


# #endregion


class ExtractionService:
    def __init__(self) -> None:
        self.settings = build_settings()
        self.repository: ExtractionRepository | None = None
        self._lock = threading.Lock()
        self._schema_lock = threading.Lock()
        self._running_execution_id: str | None = None
        self._execution_lock_connection: Any | None = None
        self._schema_ready = False
        self._stop_event = threading.Event()

    def _get_repository(self) -> ExtractionRepository:
        if self.repository is None:
            self.repository = ExtractionRepository(self.settings)
        return self.repository

    def ensure_ready(self, user_id: str | None = None) -> str:
        repository = self._get_repository()
        if not self._schema_ready:
            with self._schema_lock:
                if not self._schema_ready:
                    repository.ensure_supporting_schema()
                    self._schema_ready = True
        return repository.ensure_default_tenant(user_id)

    def _recover_orphan_execution_if_safe(self, repository: ExtractionRepository) -> str | None:
        active_execution_id = repository.fetch_active_execution_id()
        if active_execution_id is None or self._running_execution_id is not None:
            return active_execution_id

        execution_lock_connection = repository.try_acquire_execution_lock()
        if execution_lock_connection is None:
            return active_execution_id

        try:
            recovered_execution_ids = repository.recover_orphan_running_executions(
                "Execucao marcada como running foi recuperada automaticamente no overview porque nao havia worker ativo mantendo o advisory lock."
            )
        finally:
            repository.release_execution_lock(execution_lock_connection)

        if recovered_execution_ids:
            repository.append_audit(
                "Execucao orfa recuperada",
                "A aplicacao detectou uma execucao marcada como running sem worker ativo e a cancelou automaticamente.",
                "warning",
            )
            return None
        return active_execution_id

    def get_overview(self, user_id: str | None = None) -> dict[str, Any]:
        repository = self._get_repository()
        tenant_id = self.ensure_ready(user_id)
        settings = repository.fetch_olist_settings() or {}
        recent_executions = repository.fetch_recent_executions(limit=10)
        active_execution_id = self._running_execution_id or self._recover_orphan_execution_if_safe(repository)
        active_execution = None
        if active_execution_id:
            active_execution = self.get_execution(active_execution_id)
        # #region debug-point A:overview-state
        _debug_report(
            "A",
            "backend/olist_extraction/service.py:get_overview",
            "[DEBUG] overview calculated",
            {
                "tenantId": tenant_id,
                "runningExecutionId": self._running_execution_id,
                "activeExecutionId": active_execution_id,
                "hasActiveExecution": active_execution is not None,
                "recentExecutionsCount": len(recent_executions),
                "stopRequested": self._stop_event.is_set(),
            },
        )
        # #endregion
        return {
            "tenantId": tenant_id,
            "running": active_execution_id is not None,
            "activeExecutionId": active_execution_id,
            "activeExecution": active_execution,
            "stopRequested": self._stop_event.is_set(),
            "supportedEntities": [workflow.entity_name for workflow in WORKFLOWS],
            "olist": {
                "status": settings.get("status"),
                "tokenStatus": settings.get("token_status"),
                "accessTokenExpiresAt": settings.get("access_token_expires_at"),
                "lastTokenRefreshAt": settings.get("last_token_refresh_at"),
            },
            "recentExecutions": recent_executions,
        }

    def start_execution(self, *, user_id: str, actor_email: str, execution_type: str) -> dict[str, Any]:
        repository = self._get_repository()
        tenant_id = self.ensure_ready(user_id)
        if execution_type == "incremental":
            non_incremental_entities = [workflow.entity_name for workflow in list_non_incremental_workflows()]
            if non_incremental_entities:
                raise RuntimeError(
                    "A execução incremental não pode iniciar enquanto existirem entidades sem estratégia incremental configurada: "
                    + ", ".join(non_incremental_entities)
                    + "."
                )
        settings = repository.fetch_olist_settings() or {}
        access_token = str(settings.get("access_token") or "").strip()
        refresh_token = str(settings.get("refresh_token") or "").strip()
        if not access_token:
            if not refresh_token:
                raise RuntimeError("Conclua a conexão OAuth da Olist antes de executar a extração.")
            settings = repository.renew_olist_access_token()
            access_token = str(settings.get("access_token") or "").strip()

        expires_at = parse_olist_datetime(settings.get("access_token_expires_at"))
        if expires_at is not None and expires_at <= utc_now():
            if not refresh_token:
                raise RuntimeError("O access token da Olist expirou. Renove o token antes de iniciar a extração.")
            settings = repository.renew_olist_access_token()
            access_token = str(settings.get("access_token") or "").strip()

        with self._lock:
            if self._running_execution_id is not None:
                # #region debug-point B:start-already-running
                _debug_report(
                    "B",
                    "backend/olist_extraction/service.py:start_execution",
                    "[DEBUG] start ignored because local execution already running",
                    {
                        "executionType": execution_type,
                        "runningExecutionId": self._running_execution_id,
                    },
                )
                # #endregion
                return {
                    "status": "running",
                    "executionId": self._running_execution_id,
                    "detail": "Já existe uma extração em andamento.",
                }

            execution_lock_connection = repository.try_acquire_execution_lock()
            if execution_lock_connection is None:
                active_execution_id = repository.fetch_active_execution_id()
                # #region debug-point B:start-locked
                _debug_report(
                    "B",
                    "backend/olist_extraction/service.py:start_execution",
                    "[DEBUG] start blocked by advisory lock",
                    {
                        "executionType": execution_type,
                        "activeExecutionId": active_execution_id,
                    },
                )
                # #endregion
                return {
                    "status": "running",
                    "executionId": active_execution_id,
                    "detail": "Já existe uma extração em andamento em outra instância da aplicação.",
                }

            recovered_execution_ids = repository.recover_orphan_running_executions(
                "Execucao anterior recuperada automaticamente porque o processo anterior não estava mais ativo."
            )

            execution_id = str(uuid4())
            self._running_execution_id = execution_id
            self._execution_lock_connection = execution_lock_connection
            self._stop_event.clear()
            # #region debug-point B:start-accepted
            _debug_report(
                "B",
                "backend/olist_extraction/service.py:start_execution",
                "[DEBUG] start accepted and background thread prepared",
                {
                    "executionType": execution_type,
                    "executionId": execution_id,
                    "tenantId": tenant_id,
                },
            )
            # #endregion

        repository.append_audit(
            "Extração iniciada",
            (
                f"O usuário {actor_email} iniciou a execução {execution_type} da sincronização "
                "da API Olist para o Supabase."
            ),
            "accent",
        )
        if recovered_execution_ids:
            repository.append_audit(
                "Execuções órfãs recuperadas",
                (
                    "Foram encerradas automaticamente execuções órfãs antes de iniciar uma nova sincronização: "
                    + ", ".join(recovered_execution_ids)
                ),
                "warning",
            )

        thread = threading.Thread(
            target=self._run_background,
            kwargs={
                "execution_id": execution_id,
                "tenant_id": tenant_id,
                "access_token": access_token,
                "actor_email": actor_email,
                "execution_type": execution_type,
            },
            daemon=True,
        )
        thread.start()
        return {
            "status": "started",
            "executionId": execution_id,
            "detail": f"A execução {execution_type} foi iniciada.",
        }

    def start_full_sync(self, *, user_id: str, actor_email: str) -> dict[str, Any]:
        return self.start_execution(user_id=user_id, actor_email=actor_email, execution_type="incremental")

    def request_stop(self, *, actor_email: str) -> dict[str, Any]:
        del actor_email
        repository = self._get_repository()
        with self._lock:
            active_execution_id = self._running_execution_id or repository.fetch_active_execution_id()
            if active_execution_id is None:
                return {
                    "status": "idle",
                    "detail": "Nenhuma extração está em andamento.",
                }
            if self._running_execution_id is None:
                return {
                    "status": "running",
                    "executionId": active_execution_id,
                    "detail": "Há uma extração em andamento em outra instância. Solicite a parada na instância executora.",
                }
            if self._stop_event.is_set():
                return {
                    "status": "stopping",
                    "executionId": self._running_execution_id,
                    "detail": "A interrupção da extração já foi solicitada.",
                }
            execution_id = self._running_execution_id
            self._stop_event.set()
        return {
            "status": "stopping",
            "executionId": execution_id,
            "detail": "A interrupção da extração foi solicitada e será aplicada com segurança.",
        }

    def get_execution(self, execution_id: str) -> dict[str, Any] | None:
        repository = self._get_repository()
        summary = repository.fetch_execution_summary(execution_id)
        if summary is None:
            return None
        summary["runs"] = repository.fetch_execution_runs(execution_id)
        summary["logs"] = repository.fetch_execution_logs(execution_id)
        return summary

    def _run_background(
        self,
        *,
        execution_id: str,
        tenant_id: str,
        access_token: str,
        actor_email: str,
        execution_type: str,
    ) -> None:
        repository = self._get_repository()
        runner = WorkflowRunner(
            settings=self.settings,
            repository=repository,
            access_token=access_token,
            stop_requested=self._stop_event.is_set,
        )
        success_total = 0
        error_total = 0
        stopped = False
        started_at = datetime.now()
        try:
            # #region debug-point C:background-entry
            _debug_report(
                "C",
                "backend/olist_extraction/service.py:_run_background",
                "[DEBUG] background runner started",
                {
                    "executionId": execution_id,
                    "executionType": execution_type,
                    "tenantId": tenant_id,
                },
            )
            # #endregion
            for workflow in WORKFLOWS:
                if self._stop_event.is_set():
                    stopped = True
                    break
                result = runner.run_workflow(
                    execution_id=execution_id,
                    execution_type=execution_type,
                    tenant_id=tenant_id,
                    workflow=workflow,
                )
                if result["status"] == "success":
                    success_total += 1
                elif result["status"] == "cancelled":
                    stopped = True
                    break
                else:
                    error_total += 1
            duration_seconds = max((datetime.now() - started_at).total_seconds(), 0.0)
            tone = "warning" if stopped else ("success" if error_total == 0 else "danger")
            title = "Extração interrompida" if stopped else "Extração concluída"
            detail = (
                f"A execução {execution_type} solicitada por {actor_email} foi interrompida com "
                f"{success_total} entidades bem-sucedidas, {error_total} com erro "
                f"em {duration_seconds:.2f}s."
                if stopped
                else (
                    f"A execução {execution_type} solicitada por {actor_email} terminou com "
                    f"{success_total} entidades bem-sucedidas, {error_total} com erro "
                    f"em {duration_seconds:.2f}s."
                )
            )
            repository.append_audit(
                title,
                detail,
                tone,
            )
        finally:
            # #region debug-point C:background-finally
            _debug_report(
                "C",
                "backend/olist_extraction/service.py:_run_background",
                "[DEBUG] background runner finalizing",
                {
                    "executionId": execution_id,
                    "executionType": execution_type,
                    "successTotal": success_total,
                    "errorTotal": error_total,
                    "stopped": stopped,
                },
            )
            # #endregion
            with self._lock:
                self._running_execution_id = None
                self._stop_event.clear()
                repository.release_execution_lock(self._execution_lock_connection)
                self._execution_lock_connection = None


extraction_service = ExtractionService()
