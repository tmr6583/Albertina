from __future__ import annotations

import json
import os
import time
import threading
import traceback
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Any, Callable

import requests
from sqlalchemy.exc import OperationalError

from .catalog import EndpointStep, Workflow
from .config import ExtractionSettings
from .load import ExtractionRepository, UpsertResult, utc_now
from .logs import build_logger
from .transform import (
    build_external_key,
    extract_first_value,
    extract_items,
    extract_nested_objects,
    format_incremental_date,
    format_incremental_datetime,
    format_incremental_datetime_br,
    parse_olist_datetime,
    payload_hash,
)


COMMON_UPDATED_AT_KEYS = (
    "dataAtualizacao",
    "dataAlteracao",
    "dataEmissao",
    "dataCriacao",
    "data",
)

RETRYABLE_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
PLAN_LIMIT_START_DATE_RE = re.compile(r"a partir de (\d{2}/\d{2}/\d{4})")


#region debug-point lastlog-report
def _debug_report(hypothesis_id: str, location: str, msg: str, data: dict[str, Any] | None = None) -> None:
    try:
        debug_server_url = "http://127.0.0.1:7782/event"
        debug_session_id = "lastlog-execution"
        debug_env_path = os.path.join(".dbg", "lastlog-execution.env")
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
            "ts": int(time.time() * 1000),
        }
        request = urllib.request.Request(
            debug_server_url,
            data=json.dumps(payload, default=str).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(request, timeout=2).read()
    except Exception:
        pass


#endregion


@dataclass
class WorkflowCounters:
    requests: int = 0
    extracted: int = 0
    inserted: int = 0
    updated: int = 0
    errors: int = 0


class ExtractionStopped(Exception):
    pass


class OlistInvalidJsonError(RuntimeError):
    def __init__(
        self,
        *,
        endpoint_path: str,
        status_code: int | None,
        response_text: str,
        response_headers: dict[str, str],
    ) -> None:
        super().__init__(f"A API da Olist retornou JSON invalido em {endpoint_path}.")
        self.endpoint_path = endpoint_path
        self.status_code = status_code
        self.response_text = response_text
        self.response_headers = response_headers


class OlistApiClient:
    def __init__(
        self,
        settings: ExtractionSettings,
        repository: ExtractionRepository,
        access_token: str,
        stop_requested: Callable[[], bool] | None = None,
    ):
        self.settings = settings
        self.repository = repository
        self.stop_requested = stop_requested or (lambda: False)
        self._refresh_lock = threading.Lock()
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": "Albertina-Extraction/1.0"})
        self._set_access_token(access_token)

    def request_json(self, endpoint_path: str, params: dict[str, Any] | None = None) -> tuple[Any, dict[str, str]]:
        url = self.settings.api_base_url.rstrip("/") + endpoint_path
        attempts = self.settings.request_retries + 1
        request_params = dict(params or {}) if params else None
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            request_started_at = time.monotonic()
            try:
                response = self.session.get(url, params=request_params, timeout=self.settings.timeout_seconds)
                response_headers = {key: value for key, value in response.headers.items()}
                elapsed_seconds = round(time.monotonic() - request_started_at, 3)
                if response.status_code in {401, 403}:
                    auth_error = requests.HTTPError("Falha de autenticacao com a API da Olist.", response=response)
                    last_error = auth_error
                    if self._refresh_access_token():
                        self._sleep_interruptibly(self.settings.safety_sleep_seconds)
                        continue
                    raise auth_error
                if response.status_code == 429:
                    rate_limit_error = requests.HTTPError("Rate limit atingido.", response=response)
                    last_error = rate_limit_error
                    raise rate_limit_error
                response.raise_for_status()
                self._respect_rate_limit(response_headers)
                try:
                    return response.json(), response_headers
                except ValueError as exc:
                    #region debug-point lastlog-invalid-json
                    _debug_report(
                        "H1",
                        "extract.py:request_json",
                        "[DEBUG] Invalid JSON response observed",
                        {
                            "endpointPath": endpoint_path,
                            "statusCode": response.status_code,
                            "contentType": response.headers.get("Content-Type"),
                            "responseTextPreview": (response.text or "")[:500],
                        },
                    )
                    #endregion
                    raise OlistInvalidJsonError(
                        endpoint_path=endpoint_path,
                        status_code=response.status_code,
                        response_text=response.text or "",
                        response_headers=response_headers,
                    ) from exc
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                last_error = exc
                #region debug-point lastlog-http-error
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    _debug_report(
                        "H1",
                        "extract.py:request_json",
                        "[DEBUG] HTTP error response observed",
                        {
                            "endpointPath": endpoint_path,
                            "statusCode": exc.response.status_code,
                            "contentType": exc.response.headers.get("Content-Type"),
                            "responseTextPreview": (exc.response.text or "")[:500],
                        },
                    )
                #endregion
                adjusted_params = self._adjust_date_range_from_plan_limit(exc, request_params)
                if adjusted_params is not None and adjusted_params != request_params:
                    request_params = adjusted_params
                    self._sleep_interruptibly(self.settings.safety_sleep_seconds)
                    continue
                if isinstance(exc, requests.HTTPError):
                    status_code = exc.response.status_code if exc.response is not None else None
                    if status_code is not None and status_code not in RETRYABLE_HTTP_STATUS_CODES:
                        raise
                if attempt >= attempts:
                    raise
                is_rate_limited = isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code == 429
                wait_seconds = (
                    self._rate_limit_backoff_seconds(
                        {key: value for key, value in exc.response.headers.items()},
                        attempt,
                    )
                    if is_rate_limited
                    else self.settings.backoff_seconds * attempt
                )
                self._sleep_interruptibly(wait_seconds)
                if isinstance(exc, requests.HTTPError) and exc.response is not None and not is_rate_limited:
                    headers = {key: value for key, value in exc.response.headers.items()}
                    self._respect_rate_limit(headers)
                if not is_rate_limited:
                    self._sleep_interruptibly(self.settings.safety_sleep_seconds)
                continue

        if last_error is not None:
            raise last_error
        raise RuntimeError("Falha inesperada na camada HTTP da Olist.")

    def _set_access_token(self, access_token: str) -> None:
        self.session.headers["Authorization"] = f"Bearer {access_token}"

    def _refresh_access_token(self) -> bool:
        with self._refresh_lock:
            current_settings = self.repository.fetch_olist_settings() or {}
            current_access_token = str(current_settings.get("access_token") or "").strip()
            if current_access_token and self.session.headers.get("Authorization") != f"Bearer {current_access_token}":
                self._set_access_token(current_access_token)
                return True

            refreshed_settings = self.repository.renew_olist_access_token()
            refreshed_access_token = str(refreshed_settings.get("access_token") or "").strip()
            if not refreshed_access_token:
                return False
            self._set_access_token(refreshed_access_token)
            return True

    def _rate_limit_backoff_seconds(self, headers: dict[str, str], attempt: int) -> float:
        reset = headers.get("X-RateLimit-Reset")
        try:
            reset_value = int(reset) if reset is not None else None
        except ValueError:
            reset_value = None
        if reset_value is not None and reset_value > 0:
            return float(reset_value)
        return max(self.settings.backoff_seconds * attempt * 2, 5.0)

    def _adjust_date_range_from_plan_limit(
        self,
        exc: requests.Timeout | requests.ConnectionError | requests.HTTPError,
        request_params: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(exc, requests.HTTPError) or exc.response is None or exc.response.status_code != 400:
            return None
        if not request_params:
            return None
        start_param = next(
            (
                key
                for key in request_params
                if isinstance(key, str) and key.startswith("dataInicial")
            ),
            None,
        )
        if start_param is None:
            return None

        raw_text = exc.response.text or ""
        try:
            response_message = response.json().get("mensagem", "") if (response := exc.response) is not None else ""
        except ValueError:
            response_message = raw_text

        match = PLAN_LIMIT_START_DATE_RE.search(response_message)
        if match is None:
            return None

        allowed_start = datetime.strptime(match.group(1), "%d/%m/%Y").date().isoformat()
        adjusted_params = dict(request_params)
        adjusted_params[start_param] = allowed_start
        return adjusted_params

    def _respect_rate_limit(self, headers: dict[str, str]) -> None:
        remaining = headers.get("X-RateLimit-Remaining")
        reset = headers.get("X-RateLimit-Reset")
        try:
            remaining_value = int(remaining) if remaining is not None else None
        except ValueError:
            remaining_value = None
        try:
            reset_value = int(reset) if reset is not None else None
        except ValueError:
            reset_value = None

        if remaining_value is not None and remaining_value <= 1 and reset_value is not None:
            self._sleep_interruptibly(max(reset_value, 1))
        else:
            self._sleep_interruptibly(self.settings.safety_sleep_seconds)

    def _sleep_interruptibly(self, seconds: float) -> None:
        deadline = time.monotonic() + max(seconds, 0.0)
        while True:
            if self.stop_requested():
                raise ExtractionStopped("Interrupcao solicitada durante a espera da camada HTTP.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.25))


class WorkflowRunner:
    def __init__(
        self,
        *,
        settings: ExtractionSettings,
        repository: ExtractionRepository,
        access_token: str,
        stop_requested: Callable[[], bool] | None = None,
    ):
        self.settings = settings
        self.repository = repository
        self.client = OlistApiClient(settings, repository, access_token, stop_requested=stop_requested)
        self.logger = build_logger("albertina.olist_extraction", settings.log_file_path)
        self.stop_requested = stop_requested or (lambda: False)
        self._debug_state: dict[str, Any] = {"entity": None, "step": None, "sourceIndex": 0, "sourceTotal": 0}

    def run_workflow(
        self,
        *,
        execution_id: str,
        execution_type: str,
        tenant_id: str,
        workflow: Workflow,
    ) -> dict[str, Any]:
        root_step = next(step for step in workflow.steps if step.name == workflow.root_step)
        watermark_from = self.repository.get_watermark(tenant_id, workflow.entity_name, root_step.endpoint_path)
        sync_mode = self._resolve_sync_mode(root_step=root_step, execution_type=execution_type)
        sync_run_id = self.repository.create_sync_run(
            execution_id=execution_id,
            execution_type=execution_type,
            tenant_id=tenant_id,
            entity_name=workflow.entity_name,
            endpoint_path=root_step.endpoint_path,
            sync_mode=sync_mode,
            watermark_from=watermark_from,
            details={"entity": workflow.entity_name, "rootStep": root_step.name, "executionType": execution_type},
        )
        counters = WorkflowCounters()
        contexts_by_step: dict[str, list[dict[str, Any]]] = {}
        status = "success"
        started_at = utc_now()
        next_watermark = started_at if root_step.incremental else None
        reconciled_deleted_count = 0
        skipped_due_to_cooldown = False
        skipped_steps_due_to_cooldown: list[str] = []
        step_watermarks_to_save: dict[str, datetime] = {}
        heartbeat_stop = threading.Event()
        self._debug_state = {"entity": workflow.entity_name, "step": "workflow.start", "sourceIndex": 0, "sourceTotal": 0}
        heartbeat_thread = threading.Thread(
            target=self._debug_heartbeat_loop,
            kwargs={
                "heartbeat_stop": heartbeat_stop,
                "execution_id": execution_id,
                "sync_run_id": sync_run_id,
                "tenant_id": tenant_id,
                "entity_name": workflow.entity_name,
                "counters": counters,
            },
            daemon=True,
        )
        heartbeat_thread.start()

        self._log(
            execution_id=execution_id,
            sync_run_id=sync_run_id,
            tenant_id=tenant_id,
            entity_name=workflow.entity_name,
            level="INFO",
            stage="workflow",
            message=f"Iniciando extração da entidade {workflow.entity_name}.",
        )

        try:
            if execution_type == "incremental" and self._should_skip_workflow_due_to_cooldown(root_step, watermark_from):
                skipped_due_to_cooldown = True
                self._log(
                    execution_id=execution_id,
                    sync_run_id=sync_run_id,
                    tenant_id=tenant_id,
                    entity_name=workflow.entity_name,
                    level="INFO",
                    stage="cooldown",
                    message=(
                        f"Entidade {workflow.entity_name} ignorada nesta execução incremental "
                        "por estar dentro da janela de cooldown."
                    ),
                )
            else:
                for step in workflow.steps:
                    self._ensure_not_stopped(workflow.entity_name)
                    step_watermark_from = (
                        self.repository.get_watermark(tenant_id, workflow.entity_name, step.endpoint_path)
                        if step.incremental
                        else None
                    )
                    if (
                        execution_type == "incremental"
                        and step.name != root_step.name
                        and self._should_skip_step_due_to_cooldown(step, step_watermark_from)
                    ):
                        skipped_steps_due_to_cooldown.append(step.name)
                        contexts_by_step[step.name] = []
                        self._log(
                            execution_id=execution_id,
                            sync_run_id=sync_run_id,
                            tenant_id=tenant_id,
                            entity_name=workflow.entity_name,
                            level="INFO",
                            stage="cooldown",
                            message=(
                                f"Etapa {step.name} ignorada nesta execução incremental "
                                "por estar dentro da janela de cooldown."
                            ),
                        )
                        self._update_run_progress(
                            sync_run_id=sync_run_id,
                            counters=counters,
                            details={
                                "currentStep": step.name,
                                "currentEndpointPath": step.endpoint_path,
                                "skippedStepDueToCooldown": step.name,
                            },
                        )
                        continue
                    step_contexts = self._resolve_step_contexts(step, contexts_by_step)
                    extracted_contexts = self._execute_step(
                        execution_id=execution_id,
                        sync_run_id=sync_run_id,
                        tenant_id=tenant_id,
                        entity_name=workflow.entity_name,
                        execution_type=execution_type,
                        step=step,
                        source_contexts=step_contexts,
                        counters=counters,
                    )
                    contexts_by_step[step.name] = extracted_contexts
                    if execution_type != "reconciliation" and root_step.incremental and step.name == root_step.name:
                        next_watermark = self._resolve_next_watermark(extracted_contexts, started_at)
                    elif (
                        execution_type != "reconciliation"
                        and step.incremental is not None
                        and step.incremental.mode == "cooldown"
                    ):
                        step_watermarks_to_save[step.endpoint_path] = utc_now()

                if execution_type == "reconciliation":
                    reconciled_deleted_count = self.repository.reconcile_entity_deletions(
                        execution_id=execution_id,
                        tenant_id=tenant_id,
                        entity_name=workflow.entity_name,
                    )
                    self._log(
                        execution_id=execution_id,
                        sync_run_id=sync_run_id,
                        tenant_id=tenant_id,
                        entity_name=workflow.entity_name,
                        level="INFO",
                        stage="reconciliation",
                        message=(
                            f"Conciliação da entidade {workflow.entity_name} concluída. "
                            f"Registros marcados como deletados: {reconciled_deleted_count}."
                        ),
                    )
                elif root_step.incremental:
                    self.repository.save_watermark(
                        tenant_id,
                        workflow.entity_name,
                        root_step.endpoint_path,
                        next_watermark or started_at,
                    )
                for endpoint_path, step_watermark in step_watermarks_to_save.items():
                    self.repository.save_watermark(
                        tenant_id,
                        workflow.entity_name,
                        endpoint_path,
                        step_watermark,
                    )
        except ExtractionStopped:
            status = "cancelled"
            self._log(
                execution_id=execution_id,
                sync_run_id=sync_run_id,
                tenant_id=tenant_id,
                entity_name=workflow.entity_name,
                level="INFO",
                stage="workflow",
                message=f"Execução interrompida com segurança durante a entidade {workflow.entity_name}.",
            )
            self.logger.info("Execucao interrompida com seguranca na entidade %s", workflow.entity_name)
        except Exception:
            status = "error"
            counters.errors += 1
            stack_trace = traceback.format_exc()
            self._log(
                execution_id=execution_id,
                sync_run_id=sync_run_id,
                tenant_id=tenant_id,
                entity_name=workflow.entity_name,
                level="ERROR",
                stage="workflow",
                message=f"Falha na entidade {workflow.entity_name}.",
                error_count=1,
                stack_trace=stack_trace,
            )
            self.logger.exception("Falha na entidade %s", workflow.entity_name)
        finally:
            duration_seconds = max((utc_now() - started_at).total_seconds(), 0.0)
            details = {
                "entity": workflow.entity_name,
                "executionType": execution_type,
                "durationSeconds": round(duration_seconds, 2),
                "extractedCount": counters.extracted,
                "insertedCount": counters.inserted,
                "updatedCount": counters.updated,
                "reconciledDeletedCount": reconciled_deleted_count if status == "success" else 0,
                "skippedDueToCooldown": skipped_due_to_cooldown,
                "skippedStepsDueToCooldown": skipped_steps_due_to_cooldown,
            }
            self.repository.finish_sync_run(
                sync_run_id=sync_run_id,
                status=status,
                request_count=counters.requests,
                success_count=counters.inserted + counters.updated,
                error_count=counters.errors,
                watermark_to=(
                    (next_watermark or started_at)
                    if status == "success" and execution_type != "reconciliation" and root_step.incremental
                    else None
                ),
                details=details,
            )
            self._log(
                execution_id=execution_id,
                sync_run_id=sync_run_id,
                tenant_id=tenant_id,
                entity_name=workflow.entity_name,
                level="INFO" if status in {"success", "cancelled"} else "ERROR",
                stage="workflow",
                message=self._build_workflow_finished_message(
                    entity_name=workflow.entity_name,
                    status=status,
                    counters=counters,
                    duration_seconds=duration_seconds,
                    execution_type=execution_type,
                    reconciled_deleted_count=details["reconciledDeletedCount"],
                    skipped_due_to_cooldown=skipped_due_to_cooldown,
                ),
                extracted_count=counters.extracted,
                inserted_count=counters.inserted,
                updated_count=counters.updated,
                error_count=counters.errors,
            )
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=1)

        return {
            "status": status,
            "syncRunId": sync_run_id,
            "entity": workflow.entity_name,
            "requestCount": counters.requests,
            "extractedCount": counters.extracted,
            "insertedCount": counters.inserted,
            "updatedCount": counters.updated,
            "errorCount": counters.errors,
        }

    def _resolve_step_contexts(
        self,
        step: EndpointStep,
        contexts_by_step: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        if step.source_step is None:
            return [{"path_params": {}, "payload": None, "record_id": None}]

        source_contexts = contexts_by_step.get(step.source_step, [])
        if step.only_if_changed:
            source_contexts = [context for context in source_contexts if context.get("source_changed")]
        if not step.nested_collection_keys:
            return source_contexts

        derived_contexts: list[dict[str, Any]] = []
        for source_context in source_contexts:
            payload = source_context.get("payload")
            for nested_item in extract_nested_objects(payload, step.nested_collection_keys):
                derived_contexts.append(
                    {
                        **source_context,
                        "payload": nested_item,
                        "record_id": extract_first_value(
                            {"payload": nested_item, "path_params": source_context.get("path_params", {})},
                            step.record_id_keys,
                        ),
                    }
                )
        return derived_contexts

    def _execute_step(
        self,
        *,
        execution_id: str,
        sync_run_id: str,
        tenant_id: str,
        entity_name: str,
        execution_type: str,
        step: EndpointStep,
        source_contexts: list[dict[str, Any]],
        counters: WorkflowCounters,
    ) -> list[dict[str, Any]]:
        discovered_contexts: list[dict[str, Any]] = []
        total_source_contexts = len(source_contexts)
        self._debug_state.update(
            {
                "entity": entity_name,
                "step": step.name,
                "sourceIndex": 0,
                "sourceTotal": total_source_contexts,
                "endpointPath": step.endpoint_path,
            }
        )
        if entity_name == "contacts" and step.name == "contacts.detail" and total_source_contexts == 0:
            self._log(
                execution_id=execution_id,
                sync_run_id=sync_run_id,
                tenant_id=tenant_id,
                entity_name=entity_name,
                level="INFO",
                stage=step.name,
                message="Etapa contacts.detail sem registros alterados para detalhar.",
            )
            self._update_run_progress(
                sync_run_id=sync_run_id,
                counters=counters,
                details={
                    "currentStep": step.name,
                    "currentEndpointPath": step.endpoint_path,
                    "sourceContextsTotal": total_source_contexts,
                    "sourceContextsProcessed": 0,
                },
            )
        for source_index, source_context in enumerate(source_contexts):
            self._ensure_not_stopped(entity_name)
            self._debug_state.update({"sourceIndex": source_index + 1, "sourceTotal": total_source_contexts})
            if entity_name == "contacts" and step.name == "contacts.detail" and source_index > 0 and source_index % 250 == 0:
                self._log(
                    execution_id=execution_id,
                    sync_run_id=sync_run_id,
                    tenant_id=tenant_id,
                    entity_name=entity_name,
                    level="INFO",
                    stage=step.name,
                    message=f"Andamento de contacts.detail: processados={source_index}/{total_source_contexts}.",
                )
            path_params = self._build_path_params(step, source_context)
            params = self._build_query_params(step, tenant_id, entity_name, execution_type)
            endpoint_path = step.endpoint_path.format(**path_params)

            if step.pagination:
                page_limit = step.page_limit or self.settings.page_limit
                page_offset = 0
                while True:
                    self._ensure_not_stopped(entity_name)
                    paged_params = {**params, "limit": page_limit, "offset": page_offset}
                    try:
                        payload, _ = self.client.request_json(endpoint_path, paged_params)
                    except Exception as exc:
                        recovered_from_orders_400 = False
                        if (
                            entity_name == "orders"
                            and step.name == "orders.list"
                            and isinstance(exc, requests.HTTPError)
                            and exc.response is not None
                            and exc.response.status_code == 400
                            and isinstance(paged_params.get("dataAtualizacao"), str)
                        ):
                            watermark = self.repository.get_watermark(tenant_id, entity_name, step.endpoint_path)
                            start_reference = watermark - timedelta(days=3) if watermark is not None else (utc_now() - timedelta(days=30))
                            fallback_params = dict(paged_params)
                            fallback_params.pop("dataAtualizacao", None)
                            try:
                                start_value = format_incremental_date(start_reference)
                                end_value = format_incremental_date(utc_now())
                                if start_value:
                                    fallback_params["dataInicial"] = start_value
                                if end_value:
                                    fallback_params["dataFinal"] = end_value
                                payload, _ = self.client.request_json(endpoint_path, fallback_params)
                                paged_params = fallback_params
                                recovered_from_orders_400 = True
                            except Exception:
                                pass
                        if recovered_from_orders_400:
                            counters.requests += 1
                            page_contexts = self._persist_payloads(
                                execution_id=execution_id,
                                sync_run_id=sync_run_id,
                                tenant_id=tenant_id,
                                entity_name=entity_name,
                                endpoint_path=endpoint_path,
                                resolved_path_params=path_params,
                                source_context=source_context,
                                payload=payload,
                                step=step,
                                counters=counters,
                            )
                            self._update_run_progress(
                                sync_run_id=sync_run_id,
                                counters=counters,
                                details={
                                    "currentStep": step.name,
                                    "currentEndpointPath": endpoint_path,
                                    "sourceContextsTotal": total_source_contexts,
                                    "sourceContextsProcessed": source_index + 1,
                                    "lastPageOffset": page_offset,
                                    "lastPageExtracted": len(page_contexts),
                                },
                            )
                            discovered_contexts.extend(page_contexts)
                            if not page_contexts or len(page_contexts) < page_limit:
                                break
                            page_offset += page_limit
                            continue
                        if self._handle_ignorable_step_error(
                            execution_id=execution_id,
                            sync_run_id=sync_run_id,
                            tenant_id=tenant_id,
                            entity_name=entity_name,
                            step=step,
                            endpoint_path=endpoint_path,
                            error=exc,
                        ):
                            break
                        raise
                    counters.requests += 1
                    page_contexts = self._persist_payloads(
                        execution_id=execution_id,
                        sync_run_id=sync_run_id,
                        tenant_id=tenant_id,
                        entity_name=entity_name,
                        endpoint_path=endpoint_path,
                        resolved_path_params=path_params,
                        source_context=source_context,
                        payload=payload,
                        step=step,
                        counters=counters,
                    )
                    self._update_run_progress(
                        sync_run_id=sync_run_id,
                        counters=counters,
                        details={
                            "currentStep": step.name,
                            "currentEndpointPath": endpoint_path,
                            "sourceContextsTotal": total_source_contexts,
                            "sourceContextsProcessed": source_index + 1,
                            "lastPageOffset": page_offset,
                            "lastPageExtracted": len(page_contexts),
                        },
                    )
                    discovered_contexts.extend(page_contexts)
                    if not page_contexts or len(page_contexts) < page_limit:
                        break
                    page_offset += page_limit
                continue

            try:
                payload, _ = self.client.request_json(endpoint_path, params or None)
            except Exception as exc:
                if self._handle_ignorable_step_error(
                    execution_id=execution_id,
                    sync_run_id=sync_run_id,
                    tenant_id=tenant_id,
                    entity_name=entity_name,
                    step=step,
                    endpoint_path=endpoint_path,
                    error=exc,
                ):
                    continue
                raise
            counters.requests += 1
            page_contexts = self._persist_payloads(
                execution_id=execution_id,
                sync_run_id=sync_run_id,
                tenant_id=tenant_id,
                entity_name=entity_name,
                endpoint_path=endpoint_path,
                resolved_path_params=path_params,
                source_context=source_context,
                payload=payload,
                step=step,
                counters=counters,
            )
            self._update_run_progress(
                sync_run_id=sync_run_id,
                counters=counters,
                details={
                    "currentStep": step.name,
                    "currentEndpointPath": endpoint_path,
                    "sourceContextsTotal": total_source_contexts,
                    "sourceContextsProcessed": source_index + 1,
                    "lastPageExtracted": len(page_contexts),
                },
            )
            discovered_contexts.extend(page_contexts)
        return discovered_contexts

    def _build_path_params(self, step: EndpointStep, source_context: dict[str, Any]) -> dict[str, Any]:
        resolved: dict[str, Any] = dict(source_context.get("path_params") or {})
        for param_name, candidate_keys in step.path_params.items():
            value = extract_first_value(source_context, candidate_keys)
            if value in {None, ""}:
                raise ValueError(f"Parametro de rota ausente para {step.name}: {param_name}")
            resolved[param_name] = value
        return resolved

    def _build_query_params(
        self,
        step: EndpointStep,
        tenant_id: str,
        entity_name: str,
        execution_type: str,
    ) -> dict[str, Any]:
        params: dict[str, Any] = dict(step.extra_params)
        if step.incremental is None:
            return params

        if execution_type == "reconciliation":
            if step.incremental.mode == "date_range":
                start_reference = utc_now() - timedelta(days=3650)
                start_value = format_incremental_date(start_reference)
                end_value = format_incremental_date(utc_now())
                if start_value:
                    params[step.incremental.start_param] = start_value
                if step.incremental.end_param and end_value:
                    params[step.incremental.end_param] = end_value
            return params

        watermark = self.repository.get_watermark(tenant_id, entity_name, step.endpoint_path)
        if step.incremental.mode == "cooldown":
            return params
        if step.incremental.mode == "watermark":
            formatted = self._format_incremental_watermark(watermark, step.incremental.datetime_format)
            if formatted:
                params[step.incremental.start_param] = formatted
        elif step.incremental.mode == "date_range":
            start_reference = watermark or (utc_now() - timedelta(days=3650))
            if watermark is not None and step.incremental.overlap_days > 0:
                start_reference = watermark - timedelta(days=step.incremental.overlap_days)
            start_value = format_incremental_date(start_reference)
            end_value = format_incremental_date(utc_now())
            if start_value:
                params[step.incremental.start_param] = start_value
            if step.incremental.end_param and end_value:
                params[step.incremental.end_param] = end_value
        return params

    @staticmethod
    def _format_incremental_watermark(value: datetime | None, datetime_format: str) -> str | None:
        if datetime_format == "br":
            return format_incremental_datetime_br(value)
        return format_incremental_datetime(value)

    def _persist_payloads(
        self,
        *,
        execution_id: str,
        sync_run_id: str,
        tenant_id: str,
        entity_name: str,
        endpoint_path: str,
        resolved_path_params: dict[str, Any],
        source_context: dict[str, Any],
        payload: Any,
        step: EndpointStep,
        counters: WorkflowCounters,
    ) -> list[dict[str, Any]]:
        if step.singleton:
            records = [payload]
        else:
            records = extract_items(payload)

        page_contexts: list[dict[str, Any]] = []
        parent_object_id = source_context.get("record_id")
        page_inserted = 0
        page_updated = 0
        for attempt in range(2):
            page_contexts = []
            page_inserted = 0
            page_updated = 0
            try:
                with self.repository.begin() as connection:
                    for index, record in enumerate(records):
                        self._ensure_not_stopped(entity_name)
                        record_context = {
                            "path_params": dict(resolved_path_params or source_context.get("path_params") or {}),
                            "payload": record,
                            "record_id": extract_first_value(
                                {"payload": record, "path_params": resolved_path_params or source_context.get("path_params") or {}},
                                step.record_id_keys,
                            ),
                            "source_updated_at": None,
                            "source_changed": False,
                        }
                        object_id = record_context["record_id"]
                        updated_at = extract_first_value(record_context, step.updated_at_keys or COMMON_UPDATED_AT_KEYS)
                        source_updated_at = parse_olist_datetime(updated_at)
                        record_context["source_updated_at"] = source_updated_at
                        external_key = build_external_key(
                            endpoint_path=endpoint_path,
                            path_params=record_context["path_params"],
                            payload=record,
                            object_id=object_id,
                            fallback_index=index,
                        )
                        upsert_result = self.repository.upsert_raw_payload(
                            execution_id=execution_id,
                            tenant_id=tenant_id,
                            entity_name=entity_name,
                            endpoint_path=endpoint_path,
                            external_key=external_key,
                            olist_object_id=int(object_id) if isinstance(object_id, int) or str(object_id).isdigit() else None,
                            parent_olist_object_id=int(parent_object_id)
                            if isinstance(parent_object_id, int) or str(parent_object_id).isdigit()
                            else None,
                            source_updated_at=source_updated_at,
                            source_status=self._extract_source_status(record),
                            sync_run_id=sync_run_id,
                            payload_hash_value=payload_hash(record),
                            payload=record,
                            connection=connection,
                        )
                        record_context["source_changed"] = bool(upsert_result.inserted or upsert_result.updated)
                        page_inserted += upsert_result.inserted
                        page_updated += upsert_result.updated
                        page_contexts.append(record_context)
                break
            except OperationalError:
                if attempt >= 1:
                    raise
                continue

        counters.extracted += len(records)
        counters.inserted += page_inserted
        counters.updated += page_updated

        self._log(
            execution_id=execution_id,
            sync_run_id=sync_run_id,
            tenant_id=tenant_id,
            entity_name=entity_name,
            level="INFO",
            stage=step.name,
            message=(
                f"Etapa {step.name} concluida em {endpoint_path}. "
                f"Extraidos={len(records)}, inseridos={page_inserted}, atualizados={page_updated}."
            ),
            extracted_count=len(records),
            inserted_count=page_inserted,
            updated_count=page_updated,
        )
        return page_contexts

    def _handle_ignorable_step_error(
        self,
        *,
        execution_id: str,
        sync_run_id: str,
        tenant_id: str,
        entity_name: str,
        step: EndpointStep,
        endpoint_path: str,
        error: Exception,
    ) -> bool:
        status_code: int | None = None
        response_preview = ""
        reason = ""

        if isinstance(error, requests.HTTPError) and error.response is not None:
            status_code = error.response.status_code
            response_preview = (error.response.text or "")[:200]
            if status_code in step.ignore_http_statuses:
                reason = f"status HTTP {status_code}"
        elif isinstance(error, OlistInvalidJsonError) and step.ignore_invalid_json:
            status_code = error.status_code
            response_preview = error.response_text[:200]
            reason = "JSON invalido"

        if not reason:
            return False

        self._log(
            execution_id=execution_id,
            sync_run_id=sync_run_id,
            tenant_id=tenant_id,
            entity_name=entity_name,
            level="WARNING",
            stage=step.name,
            message=(
                f"Etapa opcional {step.name} ignorada em {endpoint_path} por {reason}. "
                f"A entidade seguira em frente."
            ),
        )
        self.logger.warning(
            "Etapa opcional ignorada: entity=%s step=%s endpoint=%s reason=%s status=%s preview=%s",
            entity_name,
            step.name,
            endpoint_path,
            reason,
            status_code,
            response_preview,
        )
        return True

    @staticmethod
    def _resolve_next_watermark(extracted_contexts: list[dict[str, Any]], started_at: datetime) -> datetime:
        latest_seen: datetime | None = None
        for context in extracted_contexts:
            source_updated_at = context.get("source_updated_at")
            if isinstance(source_updated_at, datetime) and (latest_seen is None or source_updated_at > latest_seen):
                latest_seen = source_updated_at
        if latest_seen is None:
            return started_at
        return latest_seen if latest_seen <= started_at else started_at

    @staticmethod
    def _resolve_sync_mode(*, root_step: EndpointStep, execution_type: str) -> str:
        if execution_type == "reconciliation":
            return "reconciliation"
        if root_step.incremental:
            if root_step.incremental.mode == "cooldown":
                return "cooldown"
            return "incremental"
        return "snapshot"

    @staticmethod
    def _should_skip_workflow_due_to_cooldown(root_step: EndpointStep, watermark_from: datetime | None) -> bool:
        return WorkflowRunner._should_skip_step_due_to_cooldown(root_step, watermark_from)

    @staticmethod
    def _should_skip_step_due_to_cooldown(step: EndpointStep, watermark_from: datetime | None) -> bool:
        if step.incremental is None or step.incremental.mode != "cooldown":
            return False
        cooldown_hours = step.incremental.cooldown_hours
        if cooldown_hours is None or watermark_from is None:
            return False
        return utc_now() < watermark_from + timedelta(hours=cooldown_hours)

    @staticmethod
    def _extract_source_status(record: Any) -> str | None:
        if not isinstance(record, dict):
            return None
        for key in ("situacao", "status", "statusCrm"):
            value = record.get(key)
            if value not in {None, ""}:
                return str(value)
        if "arquivado" in record:
            return f"arquivado={bool(record.get('arquivado'))}"
        return None

    def _log(
        self,
        *,
        execution_id: str,
        sync_run_id: str | None,
        tenant_id: str,
        entity_name: str,
        level: str,
        stage: str,
        message: str,
        extracted_count: int = 0,
        inserted_count: int = 0,
        updated_count: int = 0,
        error_count: int = 0,
        stack_trace: str | None = None,
    ) -> None:
        self.repository.append_run_log(
            execution_id=execution_id,
            sync_run_id=sync_run_id,
            tenant_id=tenant_id,
            entity_name=entity_name,
            level=level,
            stage=stage,
            message=message,
            extracted_count=extracted_count,
            inserted_count=inserted_count,
            updated_count=updated_count,
            error_count=error_count,
            stack_trace=stack_trace,
        )
        log_method = self.logger.error if level.upper() == "ERROR" else self.logger.info
        log_method(message)

    def _update_run_progress(
        self,
        *,
        sync_run_id: str,
        counters: WorkflowCounters,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.repository.update_sync_run_progress(
            sync_run_id=sync_run_id,
            request_count=counters.requests,
            success_count=counters.inserted + counters.updated,
            error_count=counters.errors,
            details={
                "extractedCount": counters.extracted,
                "insertedCount": counters.inserted,
                "updatedCount": counters.updated,
                **(details or {}),
            },
        )

    def _debug_heartbeat_loop(
        self,
        *,
        heartbeat_stop: threading.Event,
        execution_id: str,
        sync_run_id: str,
        tenant_id: str,
        entity_name: str,
        counters: WorkflowCounters,
    ) -> None:
        while not heartbeat_stop.wait(30):
            heartbeat_details = {
                "currentStep": self._debug_state.get("step"),
                "currentEndpointPath": self._debug_state.get("endpointPath"),
                "sourceContextsProcessed": self._debug_state.get("sourceIndex"),
                "sourceContextsTotal": self._debug_state.get("sourceTotal"),
                "heartbeatAt": utc_now().isoformat(),
                "extractedCount": counters.extracted,
                "insertedCount": counters.inserted,
                "updatedCount": counters.updated,
            }
            self.repository.update_sync_run_progress(
                sync_run_id=sync_run_id,
                request_count=counters.requests,
                success_count=counters.inserted + counters.updated,
                error_count=counters.errors,
                details=heartbeat_details,
            )
            self._log(
                execution_id=execution_id,
                sync_run_id=sync_run_id,
                tenant_id=tenant_id,
                entity_name=entity_name,
                level="INFO",
                stage="heartbeat",
                message=(
                    f"Heartbeat da entidade {entity_name}: etapa={self._debug_state.get('step')}, "
                    f"processados={self._debug_state.get('sourceIndex')}/{self._debug_state.get('sourceTotal')}, "
                    f"requests={counters.requests}, extraidos={counters.extracted}, "
                    f"inseridos={counters.inserted}, atualizados={counters.updated}, erros={counters.errors}."
                ),
                extracted_count=0,
                inserted_count=0,
                updated_count=0,
                error_count=counters.errors,
            )

    def _ensure_not_stopped(self, entity_name: str) -> None:
        if self.stop_requested():
            raise ExtractionStopped(f"Interrupcao solicitada durante a entidade {entity_name}.")

    @staticmethod
    def _build_workflow_finished_message(
        *,
        entity_name: str,
        status: str,
        counters: WorkflowCounters,
        duration_seconds: float,
        execution_type: str,
        reconciled_deleted_count: int,
        skipped_due_to_cooldown: bool,
    ) -> str:
        prefix = "Execução interrompida" if status == "cancelled" else "Fim"
        base = (
            f"{prefix} da entidade {entity_name}. Extraidos={counters.extracted}, "
            f"inseridos={counters.inserted}, atualizados={counters.updated}, "
            f"tempo_total={duration_seconds:.2f}s."
        )
        if skipped_due_to_cooldown and status == "success":
            return f"{base} ignorada_por_cooldown=true."
        if execution_type == "reconciliation" and status == "success":
            return f"{base} deletados_conciliados={reconciled_deleted_count}."
        return base
