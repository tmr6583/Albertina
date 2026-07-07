from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from .catalog import WORKFLOWS, WORKFLOW_BY_ENTITY, Workflow, list_non_incremental_workflows
from .config import BACKEND_DIR, build_settings
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


class _StopRequestPoller:
    def __init__(self, repository: ExtractionRepository, execution_id: str, interval_seconds: float) -> None:
        self.repository = repository
        self.execution_id = execution_id
        self.interval_seconds = max(interval_seconds, 0.1)
        self._next_check_at = 0.0
        self._cached_stop = False

    def __call__(self) -> bool:
        now = time.monotonic()
        if self._cached_stop and now < self._next_check_at:
            return True
        if now >= self._next_check_at:
            self._cached_stop = self.repository.is_stop_requested(self.execution_id)
            self._next_check_at = now + self.interval_seconds
        return self._cached_stop


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
        control = repository.fetch_execution_control() or {}
        active_execution_id = control.get("active_execution_id")
        if active_execution_id is None:
            return None

        recovered_execution_id = repository.recover_expired_execution(
            "Execucao marcada como running foi recuperada automaticamente no overview porque a lease do worker expirou."
        )
        if recovered_execution_id:
            repository.append_audit(
                "Execucao orfa recuperada",
                "A aplicacao detectou uma execucao marcada como running com lease expirada e a cancelou automaticamente.",
                "warning",
            )
            return None
        return str(active_execution_id)

    def get_overview(self, user_id: str | None = None) -> dict[str, Any]:
        repository = self._get_repository()
        tenant_id = self.ensure_ready(user_id)
        settings = repository.fetch_olist_settings() or {}
        recent_executions = repository.fetch_recent_executions(limit=10)
        active_execution_id = self._recover_orphan_execution_if_safe(repository)
        control = repository.fetch_execution_control() or {}
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
                "runningExecutionId": active_execution_id,
                "activeExecutionId": active_execution_id,
                "hasActiveExecution": active_execution is not None,
                "recentExecutionsCount": len(recent_executions),
                "stopRequested": control.get("stop_requested_at") is not None,
            },
        )
        # #endregion
        return {
            "tenantId": tenant_id,
            "running": active_execution_id is not None,
            "activeExecutionId": active_execution_id,
            "activeExecution": active_execution,
            "stopRequested": control.get("stop_requested_at") is not None,
            "supportedEntities": [workflow.entity_name for workflow in WORKFLOWS],
            "olist": {
                "status": settings.get("status"),
                "tokenStatus": settings.get("token_status"),
                "accessTokenExpiresAt": settings.get("access_token_expires_at"),
                "lastTokenRefreshAt": settings.get("last_token_refresh_at"),
            },
            "recentExecutions": recent_executions,
        }

    def start_execution(
        self,
        *,
        user_id: str,
        actor_email: str,
        execution_type: str,
    ) -> dict[str, Any]:
        repository = self._get_repository()
        tenant_id = self.ensure_ready(user_id)
        requested_workflows = self._resolve_requested_workflows(
            repository=repository,
            tenant_id=tenant_id,
            execution_type=execution_type,
        )
        self._resolve_access_token(repository)
        selected_entities = [workflow.entity_name for workflow in requested_workflows]
        selected_entities_detail = ", ".join(selected_entities)
        execution_id = str(uuid4())
        slot_metadata = {
            "tenantId": tenant_id,
            "actorEmail": actor_email,
            "selectedEntities": selected_entities,
            "requestedAt": utc_now().isoformat(),
        }

        with self._lock:
            active_execution_id = self._recover_orphan_execution_if_safe(repository)
            if active_execution_id is not None:
                return {
                    "status": "running",
                    "executionId": active_execution_id,
                    "detail": "Já existe uma extração em andamento.",
                }
            claim_result = repository.claim_execution_slot(
                execution_id=execution_id,
                execution_type=execution_type,
                lease_seconds=self.settings.execution_lease_seconds,
                metadata=slot_metadata,
            )
            if not claim_result["claimed"]:
                return {
                    "status": "running",
                    "executionId": claim_result.get("execution_id"),
                    "detail": "Já existe uma extração em andamento em outra instância da aplicação.",
                }
            # #region debug-point B:start-accepted
            _debug_report(
                "B",
                "backend/olist_extraction/service.py:start_execution",
                "[DEBUG] start accepted and worker process prepared",
                {
                    "executionType": execution_type,
                    "executionId": execution_id,
                    "tenantId": tenant_id,
                    "selectedEntities": selected_entities,
                },
            )
            # #endregion
            try:
                self._launch_worker_process(
                    execution_id=execution_id,
                    user_id=user_id,
                    actor_email=actor_email,
                    execution_type=execution_type,
                    workflow_names=selected_entities,
                )
            except Exception as exc:
                repository.clear_execution_slot(
                    execution_id=execution_id,
                    metadata={
                        "launchFailure": str(exc),
                        "failedAt": utc_now().isoformat(),
                    },
                )
                raise RuntimeError("Falha ao iniciar o worker da extração.") from exc

        repository.append_audit(
            "Extração iniciada",
            (
                f"O usuário {actor_email} iniciou a execução {execution_type} da sincronização "
                f"da API Olist para o Supabase. Entidades: {selected_entities_detail}."
            ),
            "accent",
        )
        return {
            "status": "started",
            "executionId": execution_id,
            "detail": f"A execução {execution_type} foi iniciada.",
            "selectedEntities": selected_entities,
        }

    def start_full_sync(self, *, user_id: str, actor_email: str) -> dict[str, Any]:
        return self.start_execution(user_id=user_id, actor_email=actor_email, execution_type="incremental")

    def request_stop(self, *, actor_email: str) -> dict[str, Any]:
        del actor_email
        repository = self._get_repository()
        control = repository.fetch_execution_control() or {}
        active_execution_id = control.get("active_execution_id")
        if active_execution_id is None:
            return {
                "status": "idle",
                "detail": "Nenhuma extração está em andamento.",
            }
        if control.get("stop_requested_at") is not None:
            return {
                "status": "stopping",
                "executionId": active_execution_id,
                "detail": "A interrupção da extração já foi solicitada.",
            }
        repository.request_execution_stop()
        return {
            "status": "stopping",
            "executionId": active_execution_id,
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
        workflow_names: list[str] | None = None,
        stop_requested: Any | None = None,
        heartbeat_callback: Any | None = None,
    ) -> None:
        repository = self._get_repository()
        runner = WorkflowRunner(
            settings=self.settings,
            repository=repository,
            access_token=access_token,
            stop_requested=stop_requested,
            heartbeat_callback=heartbeat_callback,
        )
        success_total = 0
        error_total = 0
        stopped = False
        started_at = datetime.now()
        selected_workflows = [
            WORKFLOW_BY_ENTITY[workflow_name] for workflow_name in workflow_names
        ] if workflow_names else list(WORKFLOWS)
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
                    "workflowNames": workflow_names or [],
                },
            )
            # #endregion
            for workflow in selected_workflows:
                if stop_requested is not None and stop_requested():
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
                    "workflowNames": workflow_names or [],
                },
            )
            # #endregion

    def run_worker_execution(
        self,
        *,
        execution_id: str,
        user_id: str,
        actor_email: str,
        execution_type: str,
        workflow_names: list[str] | None = None,
    ) -> None:
        repository = self._get_repository()
        tenant_id = self.ensure_ready(user_id)
        access_token = self._resolve_access_token(repository)
        worker_id = f"pid-{os.getpid()}-{uuid4()}"
        selected_entities = workflow_names or [workflow.entity_name for workflow in WORKFLOWS]
        adopted = repository.adopt_execution_slot(
            execution_id=execution_id,
            worker_id=worker_id,
            worker_pid=os.getpid(),
            lease_seconds=self.settings.execution_lease_seconds,
            metadata={
                "tenantId": tenant_id,
                "actorEmail": actor_email,
                "selectedEntities": selected_entities,
                "workerStartedAt": utc_now().isoformat(),
            },
        )
        if not adopted:
            raise RuntimeError("Nao foi possivel assumir a execução no worker.")

        stop_poller = _StopRequestPoller(
            repository=repository,
            execution_id=execution_id,
            interval_seconds=self.settings.stop_poll_seconds,
        )

        def renew_lease(payload: dict[str, Any]) -> None:
            # #region debug-point reconciliation-sync-lease-renew-request
            _debug_report(
                "reconciliation-sync-lease-renew-request",
                "backend/olist_extraction/service.py:_run_worker",
                "renew execution slot requested",
                {
                    "executionId": execution_id,
                    "workerId": worker_id,
                    "entityName": payload.get("entityName"),
                    "currentStep": payload.get("currentStep"),
                    "currentEndpointPath": payload.get("currentEndpointPath"),
                    "sourceContextsProcessed": payload.get("sourceContextsProcessed"),
                    "sourceContextsTotal": payload.get("sourceContextsTotal"),
                    "heartbeatAt": payload.get("heartbeatAt"),
                    "leaseSeconds": self.settings.execution_lease_seconds,
                },
            )
            # #endregion
            renewed = repository.renew_execution_slot(
                execution_id=execution_id,
                worker_id=worker_id,
                lease_seconds=self.settings.execution_lease_seconds,
                metadata={
                    "entityName": payload.get("entityName"),
                    "currentStep": payload.get("currentStep"),
                    "currentEndpointPath": payload.get("currentEndpointPath"),
                    "sourceContextsProcessed": payload.get("sourceContextsProcessed"),
                    "sourceContextsTotal": payload.get("sourceContextsTotal"),
                    "heartbeatAt": payload.get("heartbeatAt"),
                },
            )
            if not renewed:
                raise RuntimeError(f"Nao foi possivel renovar a lease da execucao {execution_id}.")
            # #region debug-point reconciliation-sync-lease-renew-done
            _debug_report(
                "reconciliation-sync-lease-renew-done",
                "backend/olist_extraction/service.py:_run_worker",
                "renew execution slot completed",
                {
                    "executionId": execution_id,
                    "workerId": worker_id,
                    "entityName": payload.get("entityName"),
                    "currentStep": payload.get("currentStep"),
                    "currentEndpointPath": payload.get("currentEndpointPath"),
                },
            )
            # #endregion

        try:
            self._run_background(
                execution_id=execution_id,
                tenant_id=tenant_id,
                access_token=access_token,
                actor_email=actor_email,
                execution_type=execution_type,
                workflow_names=workflow_names,
                stop_requested=stop_poller,
                heartbeat_callback=renew_lease,
            )
        finally:
            repository.clear_execution_slot(
                execution_id=execution_id,
                worker_id=worker_id,
                metadata={"lastFinishedAt": utc_now().isoformat()},
            )

    def _resolve_access_token(self, repository: ExtractionRepository) -> str:
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
        return access_token

    def _launch_worker_process(
        self,
        *,
        execution_id: str,
        user_id: str,
        actor_email: str,
        execution_type: str,
        workflow_names: list[str],
    ) -> None:
        command = [
            sys.executable,
            "-m",
            "olist_extraction.cli",
            "run-worker",
            "--execution-id",
            execution_id,
            "--user-id",
            user_id,
            "--actor-email",
            actor_email,
            "--execution-type",
            execution_type,
            "--workflow-names-json",
            json.dumps(workflow_names),
        ]
        creation_flags = 0
        if os.name == "nt":
            creation_flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creation_flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
            creation_flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)

        stdout_path = self.settings.log_directory / "olist_worker.stdout.log"
        stderr_path = self.settings.log_directory / "olist_worker.stderr.log"
        with open(stdout_path, "a", encoding="utf-8") as stdout_handle, open(
            stderr_path,
            "a",
            encoding="utf-8",
        ) as stderr_handle:
            subprocess.Popen(
                command,
                cwd=str(BACKEND_DIR),
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                creationflags=creation_flags,
                close_fds=False,
            )

    def _resolve_requested_workflows(
        self,
        *,
        repository: ExtractionRepository,
        tenant_id: str,
        execution_type: str,
    ) -> list[Workflow]:
        if execution_type == "incremental":
            non_incremental_entities = [workflow.entity_name for workflow in list_non_incremental_workflows()]
            if non_incremental_entities:
                raise RuntimeError(
                    "A execução incremental não pode iniciar enquanto existirem entidades sem estratégia incremental configurada: "
                    + ", ".join(non_incremental_entities)
                    + "."
                )

        requested = list(WORKFLOWS)
        if execution_type == "incremental":
            requested = [
                workflow
                for workflow in requested
                if not self._should_skip_products_stock_by_policy(
                    repository=repository,
                    tenant_id=tenant_id,
                    workflow=workflow,
                )
            ]
        if not requested:
            raise RuntimeError("Nenhuma entidade elegível foi selecionada para esta execução.")
        return requested

    def _should_skip_products_stock_by_policy(
        self,
        *,
        repository: ExtractionRepository,
        tenant_id: str,
        workflow: Workflow,
    ) -> bool:
        if workflow.entity_name != "products_stock":
            return False
        cooldown_hours = self.settings.products_stock_cooldown_hours
        if cooldown_hours <= 0:
            return False
        watermark = repository.get_watermark(tenant_id, workflow.entity_name, "/produtos")
        if watermark is None:
            return False
        return utc_now() < watermark + timedelta(hours=cooldown_hours)


extraction_service = ExtractionService()
