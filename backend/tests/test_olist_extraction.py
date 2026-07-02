from __future__ import annotations

import json
import unittest
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import requests

from backend.olist_extraction.catalog import (
    WORKFLOW_BY_ENTITY,
    EndpointStep,
    IncrementalStrategy,
    Workflow,
    list_non_incremental_workflows,
)
from backend.olist_extraction.config import ExtractionSettings
from backend.olist_extraction.extract import OlistApiClient, OlistInvalidJsonError, WorkflowCounters, WorkflowRunner
from backend.olist_extraction.load import UpsertResult
from backend.olist_extraction.service import ExtractionService


def build_settings(log_dir: Path) -> ExtractionSettings:
    return ExtractionSettings(
        database_url="postgresql://user:pass@localhost:5432/albertina",
        api_base_url="https://api.tiny.com.br/public-api/v3/",
        timeout_seconds=5,
        request_retries=2,
        backoff_seconds=0.01,
        page_limit=100,
        safety_sleep_seconds=0.0,
        default_tenant_code="default",
        default_tenant_name="Tenant Padrao Olist",
        products_stock_cooldown_hours=24,
        execution_lease_seconds=180,
        stop_poll_seconds=0.01,
        log_directory=log_dir,
        log_file_path=log_dir / "olist_extraction.log",
    )


def build_response(
    status_code: int,
    *,
    payload: object | None = None,
    text: str = "",
    headers: dict[str, str] | None = None,
) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.headers.update(headers or {})
    response.url = "https://api.tiny.com.br/public-api/v3/test"
    response.request = requests.Request("GET", response.url).prepare()
    if payload is not None:
        response._content = json.dumps(payload).encode("utf-8")
        response.headers.setdefault("Content-Type", "application/json")
    else:
        response._content = text.encode("utf-8")
    return response


class DummyRepository:
    def fetch_olist_settings(self) -> dict[str, str]:
        return {}

    def renew_olist_access_token(self) -> dict[str, str]:
        return {}


class FakeWorkflowRepository:
    def __init__(self) -> None:
        self.watermark: datetime | None = None
        self.saved_watermark: datetime | None = None
        self.watermarks: dict[str, datetime] = {}
        self.saved_watermarks: dict[str, datetime] = {}
        self.finished_runs: list[dict[str, object]] = []
        self.progress_updates: list[dict[str, object]] = []
        self.created_runs: list[dict[str, object]] = []
        self.reconciled_deleted_total = 0
        self.reconcile_calls: list[dict[str, object]] = []

    def get_watermark(self, tenant_id: str, entity_name: str, endpoint_path: str) -> datetime | None:
        del tenant_id, entity_name
        return self.watermarks.get(endpoint_path, self.watermark)

    def create_sync_run(
        self,
        *,
        execution_id: str,
        execution_type: str,
        tenant_id: str,
        entity_name: str,
        endpoint_path: str,
        sync_mode: str,
        watermark_from: datetime | None,
        details: dict[str, object],
    ) -> str:
        self.created_runs.append(
            {
                "execution_id": execution_id,
                "execution_type": execution_type,
                "tenant_id": tenant_id,
                "entity_name": entity_name,
                "endpoint_path": endpoint_path,
                "sync_mode": sync_mode,
                "watermark_from": watermark_from,
                "details": details,
            }
        )
        return "sync-run-1"

    def begin(self):
        return nullcontext(object())

    def upsert_raw_payload(self, **kwargs) -> UpsertResult:
        del kwargs
        return UpsertResult(inserted=1, updated=0)

    def save_watermark(self, tenant_id: str, entity_name: str, endpoint_path: str, last_success_at: datetime) -> None:
        del tenant_id, entity_name
        self.saved_watermark = last_success_at
        self.saved_watermarks[endpoint_path] = last_success_at

    def finish_sync_run(self, **kwargs) -> None:
        self.finished_runs.append(kwargs)

    def update_sync_run_progress(self, **kwargs) -> None:
        self.progress_updates.append(kwargs)

    def append_run_log(self, **kwargs) -> None:
        del kwargs

    def reconcile_entity_deletions(self, **kwargs) -> int:
        self.reconcile_calls.append(kwargs)
        return self.reconciled_deleted_total

    def fetch_olist_settings(self) -> dict[str, str]:
        return {}

    def renew_olist_access_token(self) -> dict[str, str]:
        return {}


class OlistApiClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.settings = build_settings(Path(self.temp_dir.name))
        self.client = OlistApiClient(self.settings, DummyRepository(), "token-inicial")
        self.client._sleep_interruptibly = Mock()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_request_json_does_not_retry_non_retryable_http_error(self) -> None:
        self.client.session.get = Mock(return_value=build_response(404, payload={"message": "Nao encontrado"}))

        with self.assertRaises(requests.HTTPError):
            self.client.request_json("/nao-existe")

        self.assertEqual(self.client.session.get.call_count, 1)

    def test_request_json_refreshes_token_after_unauthorized(self) -> None:
        self.client.session.get = Mock(
            side_effect=[
                build_response(401, payload={"message": "Token expirado"}),
                build_response(200, payload={"items": [{"id": 1}]}),
            ]
        )

        def refresh_token() -> bool:
            self.client.session.headers["Authorization"] = "Bearer token-renovado"
            return True

        self.client._refresh_access_token = Mock(side_effect=refresh_token)

        payload, _headers = self.client.request_json("/contatos")

        self.assertEqual(payload, {"items": [{"id": 1}]})
        self.assertEqual(self.client.session.get.call_count, 2)
        self.assertEqual(self.client.session.headers["Authorization"], "Bearer token-renovado")

    def test_request_json_retries_when_rate_limited(self) -> None:
        self.client.session.get = Mock(
            side_effect=[
                build_response(429, payload={"message": "Rate limit"}, headers={"X-RateLimit-Reset": "1"}),
                build_response(200, payload={"items": [{"id": 10}]}),
            ]
        )

        payload, _headers = self.client.request_json("/contatos")

        self.assertEqual(payload, {"items": [{"id": 10}]})
        self.assertEqual(self.client.session.get.call_count, 2)
        self.assertGreaterEqual(self.client._sleep_interruptibly.call_count, 1)

    def test_request_json_retries_when_invalid_json_is_transient(self) -> None:
        self.client.session.get = Mock(
            side_effect=[
                build_response(200, text="<html>temporario</html>", headers={"Content-Type": "text/html"}),
                build_response(200, payload={"items": [{"id": 22}]}),
            ]
        )

        payload, _headers = self.client.request_json("/contas-receber")

        self.assertEqual(payload, {"items": [{"id": 22}]})
        self.assertEqual(self.client.session.get.call_count, 2)
        self.assertGreaterEqual(self.client._sleep_interruptibly.call_count, 1)

    def test_request_json_adjusts_date_range_when_plan_blocks_old_start_date(self) -> None:
        captured_params: list[dict[str, object] | None] = []
        responses = iter(
            [
                build_response(400, payload={"mensagem": "Consulta permitida apenas a partir de 01/06/2026"}),
                build_response(200, payload={"items": []}),
            ]
        )

        def fake_get(url: str, params: dict[str, object] | None = None, timeout: int | None = None) -> requests.Response:
            del url, timeout
            captured_params.append(dict(params) if params is not None else None)
            return next(responses)

        self.client.session.get = Mock(side_effect=fake_get)

        payload, _headers = self.client.request_json(
            "/contas-receber",
            {"dataInicialEmissao": "2020-01-01", "dataFinalEmissao": "2026-06-27"},
        )

        self.assertEqual(payload, {"items": []})
        self.assertEqual(captured_params[1]["dataInicialEmissao"], "2026-06-01")

    def test_request_json_adjusts_generic_data_inicial_when_plan_blocks_old_start_date(self) -> None:
        captured_params: list[dict[str, object] | None] = []
        responses = iter(
            [
                build_response(400, payload={"mensagem": "Consulta permitida apenas a partir de 15/06/2026"}),
                build_response(200, payload={"items": []}),
            ]
        )

        def fake_get(url: str, params: dict[str, object] | None = None, timeout: int | None = None) -> requests.Response:
            del url, timeout
            captured_params.append(dict(params) if params is not None else None)
            return next(responses)

        self.client.session.get = Mock(side_effect=fake_get)

        payload, _headers = self.client.request_json(
            "/notas",
            {"dataInicial": "2020-01-01", "dataFinal": "2026-06-27"},
        )

        self.assertEqual(payload, {"items": []})
        self.assertEqual(captured_params[1]["dataInicial"], "2026-06-15")


class WorkflowRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.settings = build_settings(Path(self.temp_dir.name))
        self.repository = FakeWorkflowRepository()
        self.logger = Mock()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _build_runner(self) -> WorkflowRunner:
        with patch("backend.olist_extraction.extract.build_logger", return_value=self.logger):
            return WorkflowRunner(
                settings=self.settings,
                repository=self.repository,
                access_token="token-inicial",
            )

    @staticmethod
    def _build_incremental_workflow() -> Workflow:
        return Workflow(
            entity_name="orders",
            root_step="orders.list",
            steps=(
                EndpointStep(
                    name="orders.list",
                    endpoint_path="/pedidos",
                    pagination=True,
                    incremental=IncrementalStrategy(mode="watermark", start_param="dataAtualizacao"),
                    record_id_keys=("id",),
                    updated_at_keys=("dataAtualizacao",),
                ),
            ),
        )

    def test_run_workflow_saves_observed_root_watermark(self) -> None:
        runner = self._build_runner()
        runner.client = Mock()
        runner.client.request_json = Mock(
            return_value=(
                {"items": [{"id": 1, "dataAtualizacao": "2026-06-20 12:00:00"}]},
                {},
            )
        )

        result = runner.run_workflow(
            execution_id="exec-1",
            execution_type="incremental",
            tenant_id="tenant-1",
            workflow=self._build_incremental_workflow(),
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            self.repository.saved_watermark,
            datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            self.repository.finished_runs[-1]["watermark_to"],
            datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_run_workflow_uses_started_at_when_incremental_step_returns_no_records(self) -> None:
        runner = self._build_runner()
        runner.client = Mock()
        runner.client.request_json = Mock(return_value=({"items": []}, {}))
        started_at = datetime(2026, 6, 27, 9, 0, 0, tzinfo=timezone.utc)
        finished_at = datetime(2026, 6, 27, 9, 0, 5, tzinfo=timezone.utc)

        with patch("backend.olist_extraction.extract.utc_now", side_effect=[started_at, finished_at]):
            result = runner.run_workflow(
                execution_id="exec-2",
                execution_type="incremental",
                tenant_id="tenant-1",
                workflow=self._build_incremental_workflow(),
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(self.repository.saved_watermark, started_at)
        self.assertEqual(self.repository.finished_runs[-1]["watermark_to"], started_at)

    def test_run_workflow_updates_live_progress_during_running_entity(self) -> None:
        runner = self._build_runner()
        runner.client = Mock()
        runner.client.request_json = Mock(
            side_effect=[
                (
                    {
                        "items": [
                            {"id": 1, "dataAtualizacao": "2026-06-20 12:00:00"},
                            {"id": 2, "dataAtualizacao": "2026-06-20 12:01:00"},
                        ]
                    },
                    {},
                ),
                ({"items": []}, {}),
            ]
        )

        result = runner.run_workflow(
            execution_id="exec-3",
            execution_type="incremental",
            tenant_id="tenant-1",
            workflow=self._build_incremental_workflow(),
        )

        self.assertEqual(result["status"], "success")
        self.assertGreaterEqual(len(self.repository.progress_updates), 1)
        latest_progress = self.repository.progress_updates[-1]
        self.assertEqual(latest_progress["request_count"], 1)
        self.assertEqual(latest_progress["success_count"], 2)
        self.assertEqual(latest_progress["error_count"], 0)
        self.assertEqual(latest_progress["details"]["currentStep"], "orders.list")
        self.assertEqual(latest_progress["details"]["currentEndpointPath"], "/pedidos")
        self.assertEqual(latest_progress["details"]["sourceContextsProcessed"], 1)
        self.assertEqual(latest_progress["details"]["sourceContextsTotal"], 1)
        self.assertEqual(latest_progress["details"]["extractedCount"], 2)
        self.assertEqual(latest_progress["details"]["insertedCount"], 2)
        self.assertEqual(latest_progress["details"]["updatedCount"], 0)

    def test_debug_heartbeat_loop_persists_progress_and_log(self) -> None:
        class OneShotWait:
            def __init__(self) -> None:
                self.calls = 0

            def wait(self, timeout: float) -> bool:
                del timeout
                self.calls += 1
                return self.calls > 1

        runner = self._build_runner()
        runner._debug_state = {
            "entity": "contacts",
            "step": "contacts.detail",
            "sourceIndex": 10,
            "sourceTotal": 100,
            "endpointPath": "/contatos/{idContato}",
        }
        counters = WorkflowCounters(requests=5, extracted=10, inserted=3, updated=1, errors=0)
        runner._log = Mock()

        runner._debug_heartbeat_loop(
            heartbeat_stop=OneShotWait(),
            execution_id="exec-4",
            sync_run_id="sync-run-4",
            tenant_id="tenant-1",
            entity_name="contacts",
            counters=counters,
        )

        latest_progress = self.repository.progress_updates[-1]
        self.assertEqual(latest_progress["sync_run_id"], "sync-run-4")
        self.assertEqual(latest_progress["request_count"], 5)
        self.assertEqual(latest_progress["success_count"], 4)
        self.assertEqual(latest_progress["details"]["currentStep"], "contacts.detail")
        self.assertEqual(latest_progress["details"]["sourceContextsProcessed"], 10)
        self.assertEqual(latest_progress["details"]["sourceContextsTotal"], 100)
        self.assertEqual(latest_progress["details"]["currentEndpointPath"], "/contatos/{idContato}")
        runner._log.assert_called_once()
        self.assertEqual(runner._log.call_args.kwargs["stage"], "heartbeat")

    def test_log_persistence_failure_does_not_raise(self) -> None:
        runner = self._build_runner()
        runner.repository.append_run_log = Mock(side_effect=RuntimeError("log indisponivel"))

        runner._log(
            execution_id="exec-log",
            sync_run_id="sync-log",
            tenant_id="tenant-1",
            entity_name="orders",
            level="INFO",
            stage="orders.list",
            message="teste",
        )

        self.logger.warning.assert_called()
        self.logger.info.assert_called_with("teste")

    def test_build_query_params_formats_orders_watermark_as_br_datetime(self) -> None:
        self.repository.watermark = datetime(2026, 6, 28, 6, 14, 13, tzinfo=timezone.utc)
        runner = self._build_runner()
        step = EndpointStep(
            name="orders.list",
            endpoint_path="/pedidos",
            pagination=True,
            incremental=IncrementalStrategy(mode="watermark", start_param="dataAtualizacao", datetime_format="br"),
        )

        params = runner._build_query_params(step, "tenant-1", "orders", "incremental")

        self.assertEqual(params["dataAtualizacao"], "28/06/2026 06:14:13")

    def test_build_query_params_reconciliation_ignores_watermark_filter(self) -> None:
        self.repository.watermark = datetime(2026, 6, 28, 6, 14, 13, tzinfo=timezone.utc)
        runner = self._build_runner()
        step = EndpointStep(
            name="orders.list",
            endpoint_path="/pedidos",
            pagination=True,
            incremental=IncrementalStrategy(mode="watermark", start_param="dataAtualizacao", datetime_format="br"),
        )

        params = runner._build_query_params(step, "tenant-1", "orders", "reconciliation")

        self.assertEqual(params, {})

    def test_build_query_params_reconciliation_date_range_uses_open_history_start(self) -> None:
        runner = self._build_runner()
        step = EndpointStep(
            name="invoices.list",
            endpoint_path="/notas",
            pagination=True,
            incremental=IncrementalStrategy(
                mode="date_range",
                start_param="dataInicial",
                end_param="dataFinal",
            ),
        )

        params = runner._build_query_params(step, "tenant-1", "invoices", "reconciliation")

        self.assertEqual(params["dataInicial"], "1900-01-01")
        self.assertIn("dataFinal", params)

    def test_orders_list_falls_back_to_date_range_when_data_atualizacao_returns_400(self) -> None:
        self.repository.watermark = datetime(2026, 6, 28, 6, 14, 13, tzinfo=timezone.utc)
        runner = self._build_runner()
        runner._log = Mock()

        captured_params: list[dict[str, object] | None] = []

        def fake_request_json(endpoint_path: str, params: dict[str, object] | None = None):
            captured_params.append(dict(params) if params is not None else None)
            if len(captured_params) == 1:
                raise requests.HTTPError(
                    "400 Client Error",
                    response=build_response(400, payload={"mensagem": "Bad Request"}),
                )
            return ({"items": [{"id": 1, "dataAtualizacao": "2026-06-28 06:14:13"}]}, {})

        runner.client = Mock()
        runner.client.request_json = Mock(side_effect=fake_request_json)

        workflow = Workflow(
            entity_name="orders",
            root_step="orders.list",
            steps=(
                EndpointStep(
                    name="orders.list",
                    endpoint_path="/pedidos",
                    pagination=True,
                    incremental=IncrementalStrategy(mode="watermark", start_param="dataAtualizacao", datetime_format="br"),
                    record_id_keys=("id",),
                    updated_at_keys=("dataAtualizacao",),
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-orders-fallback",
            execution_type="incremental",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(runner.client.request_json.call_count, 2)
        self.assertIn("dataAtualizacao", captured_params[0] or {})
        self.assertNotIn("dataAtualizacao", captured_params[1] or {})
        self.assertIn("dataInicial", captured_params[1] or {})
        self.assertIn("dataFinal", captured_params[1] or {})

    def test_build_query_params_date_range_replays_overlap_window(self) -> None:
        self.repository.watermark = datetime(2026, 6, 28, 6, 14, 13, tzinfo=timezone.utc)
        runner = self._build_runner()
        step = EndpointStep(
            name="invoices.list",
            endpoint_path="/notas",
            pagination=True,
            incremental=IncrementalStrategy(
                mode="date_range",
                start_param="dataInicial",
                end_param="dataFinal",
                overlap_days=3,
            ),
        )

        params = runner._build_query_params(step, "tenant-1", "invoices", "incremental")

        self.assertEqual(params["dataInicial"], "2026-06-25")
        self.assertIn("dataFinal", params)

    def test_build_query_params_date_range_without_watermark_uses_open_history_start(self) -> None:
        runner = self._build_runner()
        step = EndpointStep(
            name="invoices.list",
            endpoint_path="/notas",
            pagination=True,
            incremental=IncrementalStrategy(
                mode="date_range",
                start_param="dataInicial",
                end_param="dataFinal",
            ),
        )

        params = runner._build_query_params(step, "tenant-1", "invoices", "incremental")

        self.assertEqual(params["dataInicial"], "1900-01-01")
        self.assertIn("dataFinal", params)

    def test_cooldown_incremental_skips_recent_workflow_without_requests(self) -> None:
        self.repository.watermark = datetime.now(timezone.utc)
        runner = self._build_runner()
        runner.client = Mock()
        runner._log = Mock()
        workflow = Workflow(
            entity_name="company_info",
            root_step="company.info",
            steps=(
                EndpointStep(
                    name="company.info",
                    endpoint_path="/info",
                    singleton=True,
                    incremental=IncrementalStrategy(mode="cooldown", cooldown_hours=24),
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-cooldown",
            execution_type="incremental",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["requestCount"], 0)
        self.assertFalse(runner.client.request_json.called)
        self.assertTrue(self.repository.finished_runs[-1]["details"]["skippedDueToCooldown"])
        self.assertEqual(self.repository.created_runs[-1]["sync_mode"], "cooldown")
        self.assertIn("ignorada_por_cooldown=true", runner._log.call_args_list[-1].kwargs["message"])

    def test_incremental_cooldown_substep_is_skipped_without_derived_requests(self) -> None:
        self.repository.watermarks["/produtos/{idProduto}/tags"] = datetime.now(timezone.utc)
        runner = self._build_runner()
        runner.client = Mock()
        runner._log = Mock()
        runner.client.request_json = Mock(
            return_value=(
                {
                    "items": [
                        {"id": 10, "dataAlteracao": "2026-06-28 01:00:00"},
                    ]
                },
                {},
            )
        )

        workflow = Workflow(
            entity_name="products",
            root_step="products.list",
            steps=(
                EndpointStep(
                    name="products.list",
                    endpoint_path="/produtos",
                    pagination=True,
                    incremental=IncrementalStrategy(mode="watermark", start_param="dataAlteracao"),
                    record_id_keys=("id",),
                    updated_at_keys=("dataAlteracao",),
                ),
                EndpointStep(
                    name="products.tags",
                    endpoint_path="/produtos/{idProduto}/tags",
                    source_step="products.list",
                    path_params={"idProduto": ("record_id", "id")},
                    incremental=IncrementalStrategy(mode="cooldown", cooldown_hours=24),
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-products-cooldown-step",
            execution_type="incremental",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["requestCount"], 1)
        self.assertEqual(runner.client.request_json.call_count, 1)
        self.assertEqual(
            self.repository.finished_runs[-1]["details"]["skippedStepsDueToCooldown"],
            ["products.tags"],
        )
        cooldown_logs = [call.kwargs for call in runner._log.call_args_list if call.kwargs.get("stage") == "cooldown"]
        self.assertEqual(len(cooldown_logs), 1)
        self.assertIn("Etapa products.tags ignorada", cooldown_logs[0]["message"])

    def test_incremental_cooldown_substep_saves_own_watermark_after_success(self) -> None:
        runner = self._build_runner()
        runner.client = Mock()
        runner._log = Mock()
        runner.client.request_json = Mock(
            side_effect=[
                (
                    {
                        "items": [
                            {"id": 10, "dataAlteracao": "2026-06-28 01:00:00"},
                        ]
                    },
                    {},
                ),
                (
                    {
                        "items": [{"id": 1, "nome": "Tag A"}],
                    },
                    {},
                ),
            ]
        )

        workflow = Workflow(
            entity_name="products",
            root_step="products.list",
            steps=(
                EndpointStep(
                    name="products.list",
                    endpoint_path="/produtos",
                    pagination=True,
                    incremental=IncrementalStrategy(mode="watermark", start_param="dataAlteracao"),
                    record_id_keys=("id",),
                    updated_at_keys=("dataAlteracao",),
                ),
                EndpointStep(
                    name="products.tags",
                    endpoint_path="/produtos/{idProduto}/tags",
                    source_step="products.list",
                    path_params={"idProduto": ("record_id", "id")},
                    incremental=IncrementalStrategy(mode="cooldown", cooldown_hours=24),
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-products-cooldown-step-watermark",
            execution_type="incremental",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["requestCount"], 2)
        self.assertIn("/produtos/{idProduto}/tags", self.repository.saved_watermarks)
        self.assertIn("/produtos", self.repository.saved_watermarks)
        self.assertEqual(
            self.repository.finished_runs[-1]["details"]["skippedStepsDueToCooldown"],
            [],
        )

    def test_optional_http_error_does_not_fail_entity(self) -> None:
        runner = self._build_runner()
        runner.client = Mock()
        runner._log = Mock()
        runner.client.request_json = Mock(
            side_effect=[
                (
                    {
                        "items": [
                            {"id": 10, "dataAlteracao": "2026-06-28 01:00:00"},
                        ]
                    },
                    {},
                ),
                requests.HTTPError(
                    "404 Client Error",
                    response=build_response(404, payload={"message": "Nao encontrado"}),
                ),
            ]
        )

        workflow = Workflow(
            entity_name="products",
            root_step="products.list",
            steps=(
                EndpointStep(
                    name="products.list",
                    endpoint_path="/produtos",
                    pagination=True,
                    incremental=IncrementalStrategy(mode="watermark", start_param="dataAlteracao"),
                    record_id_keys=("id",),
                    updated_at_keys=("dataAlteracao",),
                ),
                EndpointStep(
                    name="products.fabricated",
                    endpoint_path="/produtos/{idProduto}/fabricado",
                    source_step="products.list",
                    path_params={"idProduto": ("record_id", "id")},
                    singleton=True,
                    ignore_http_statuses=(404,),
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-5",
            execution_type="incremental",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["errorCount"], 0)
        warning_logs = [call.kwargs for call in runner._log.call_args_list if call.kwargs.get("level") == "WARNING"]
        self.assertEqual(len(warning_logs), 1)
        self.assertIn("Etapa opcional products.fabricated ignorada", warning_logs[0]["message"])

    def test_optional_kit_http_400_does_not_fail_entity(self) -> None:
        runner = self._build_runner()
        runner.client = Mock()
        runner._log = Mock()
        runner.client.request_json = Mock(
            side_effect=[
                (
                    {
                        "items": [
                            {"id": 10, "dataAlteracao": "2026-06-28 01:00:00"},
                        ]
                    },
                    {},
                ),
                requests.HTTPError(
                    "400 Client Error",
                    response=build_response(400, payload={"mensagem": "Produto nao possui composicao de kit"}),
                ),
            ]
        )

        workflow = Workflow(
            entity_name="products",
            root_step="products.list",
            steps=(
                EndpointStep(
                    name="products.list",
                    endpoint_path="/produtos",
                    pagination=True,
                    incremental=IncrementalStrategy(mode="watermark", start_param="dataAlteracao"),
                    record_id_keys=("id",),
                    updated_at_keys=("dataAlteracao",),
                ),
                EndpointStep(
                    name="products.kit",
                    endpoint_path="/produtos/{idProduto}/kit",
                    source_step="products.list",
                    path_params={"idProduto": ("record_id", "id")},
                    singleton=True,
                    ignore_http_statuses=(400,),
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-5b",
            execution_type="incremental",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["errorCount"], 0)
        warning_logs = [call.kwargs for call in runner._log.call_args_list if call.kwargs.get("level") == "WARNING"]
        self.assertEqual(len(warning_logs), 1)
        self.assertIn("Etapa opcional products.kit ignorada", warning_logs[0]["message"])

    def test_optional_invalid_json_does_not_fail_entity(self) -> None:
        runner = self._build_runner()
        runner.client = Mock()
        runner._log = Mock()
        runner.client.request_json = Mock(
            side_effect=[
                (
                    {
                        "items": [
                            {"id": 11, "dataEmissao": "2026-06-28 01:00:00"},
                        ]
                    },
                    {},
                ),
                OlistInvalidJsonError(
                    endpoint_path="/contas-receber/11/recebimentos",
                    status_code=200,
                    response_text="",
                    response_headers={"Content-Type": "text/plain"},
                ),
            ]
        )

        workflow = Workflow(
            entity_name="accounts_receivable",
            root_step="accounts_receivable.list",
            steps=(
                EndpointStep(
                    name="accounts_receivable.list",
                    endpoint_path="/contas-receber",
                    pagination=True,
                    incremental=IncrementalStrategy(
                        mode="date_range",
                        start_param="dataInicialEmissao",
                        end_param="dataFinalEmissao",
                    ),
                    record_id_keys=("id",),
                ),
                EndpointStep(
                    name="accounts_receivable.receipts",
                    endpoint_path="/contas-receber/{idContaReceber}/recebimentos",
                    source_step="accounts_receivable.list",
                    path_params={"idContaReceber": ("record_id", "id")},
                    ignore_invalid_json=True,
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-6",
            execution_type="incremental",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["errorCount"], 0)
        warning_logs = [call.kwargs for call in runner._log.call_args_list if call.kwargs.get("level") == "WARNING"]
        self.assertEqual(len(warning_logs), 1)
        self.assertIn("Etapa opcional accounts_receivable.receipts ignorada", warning_logs[0]["message"])

    def test_invoices_derived_steps_are_skipped_when_detail_is_unchanged(self) -> None:
        runner = self._build_runner()
        runner.client = Mock()
        runner._log = Mock()
        runner.client.request_json = Mock(
            side_effect=[
                (
                    {
                        "items": [
                            {"idNota": 100, "dataCriacao": "2026-06-28 01:00:00"},
                        ]
                    },
                    {},
                ),
                (
                    {
                        "idNota": 100,
                        "itens": [{"idItem": 501}],
                    },
                    {},
                ),
            ]
        )
        runner.repository.upsert_raw_payload = Mock(
            side_effect=[
                UpsertResult(inserted=1, updated=0),
                UpsertResult(inserted=0, updated=0),
            ]
        )

        workflow = Workflow(
            entity_name="invoices",
            root_step="invoices.list",
            steps=(
                EndpointStep(
                    name="invoices.list",
                    endpoint_path="/notas",
                    pagination=True,
                    incremental=IncrementalStrategy(
                        mode="date_range",
                        start_param="dataInicial",
                        end_param="dataFinal",
                    ),
                    record_id_keys=("id", "idNota"),
                ),
                EndpointStep(
                    name="invoices.detail",
                    endpoint_path="/notas/{idNota}",
                    source_step="invoices.list",
                    path_params={"idNota": ("record_id", "id", "idNota")},
                    record_id_keys=("id", "idNota"),
                    singleton=True,
                    only_if_changed=True,
                ),
                EndpointStep(
                    name="invoices.link",
                    endpoint_path="/notas/{idNota}/link",
                    source_step="invoices.detail",
                    path_params={"idNota": ("record_id", "id", "idNota")},
                    singleton=True,
                    only_if_changed=True,
                ),
                EndpointStep(
                    name="invoices.item_detail",
                    endpoint_path="/notas/{idNota}/itens/{idItem}",
                    source_step="invoices.detail",
                    path_params={
                        "idNota": ("idNota",),
                        "idItem": ("record_id", "id", "idItem"),
                    },
                    nested_collection_keys=("itens",),
                    record_id_keys=("id", "idItem"),
                    singleton=True,
                    only_if_changed=True,
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-invoices-unchanged",
            execution_type="incremental",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["requestCount"], 2)
        self.assertEqual(runner.client.request_json.call_count, 2)

    def test_invoices_derived_steps_run_when_detail_changes(self) -> None:
        runner = self._build_runner()
        runner.client = Mock()
        runner._log = Mock()
        runner.client.request_json = Mock(
            side_effect=[
                (
                    {
                        "items": [
                            {"idNota": 100, "dataCriacao": "2026-06-28 01:00:00"},
                        ]
                    },
                    {},
                ),
                (
                    {
                        "idNota": 100,
                        "itens": [{"idItem": 501}],
                    },
                    {},
                ),
                (
                    {"url": "https://exemplo.local/nota/100"},
                    {},
                ),
                (
                    {"idItem": 501, "descricao": "Item alterado"},
                    {},
                ),
            ]
        )
        runner.repository.upsert_raw_payload = Mock(
            side_effect=[
                UpsertResult(inserted=1, updated=0),
                UpsertResult(inserted=1, updated=0),
                UpsertResult(inserted=1, updated=0),
                UpsertResult(inserted=1, updated=0),
            ]
        )

        workflow = Workflow(
            entity_name="invoices",
            root_step="invoices.list",
            steps=(
                EndpointStep(
                    name="invoices.list",
                    endpoint_path="/notas",
                    pagination=True,
                    incremental=IncrementalStrategy(
                        mode="date_range",
                        start_param="dataInicial",
                        end_param="dataFinal",
                    ),
                    record_id_keys=("id", "idNota"),
                ),
                EndpointStep(
                    name="invoices.detail",
                    endpoint_path="/notas/{idNota}",
                    source_step="invoices.list",
                    path_params={"idNota": ("record_id", "id", "idNota")},
                    record_id_keys=("id", "idNota"),
                    singleton=True,
                    only_if_changed=True,
                ),
                EndpointStep(
                    name="invoices.link",
                    endpoint_path="/notas/{idNota}/link",
                    source_step="invoices.detail",
                    path_params={"idNota": ("record_id", "id", "idNota")},
                    singleton=True,
                    only_if_changed=True,
                ),
                EndpointStep(
                    name="invoices.item_detail",
                    endpoint_path="/notas/{idNota}/itens/{idItem}",
                    source_step="invoices.detail",
                    path_params={
                        "idNota": ("idNota",),
                        "idItem": ("record_id", "id", "idItem"),
                    },
                    nested_collection_keys=("itens",),
                    record_id_keys=("id", "idItem"),
                    singleton=True,
                    only_if_changed=True,
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-invoices-changed",
            execution_type="incremental",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["requestCount"], 4)
        self.assertEqual(runner.client.request_json.call_count, 4)

    def test_reconciliation_runs_invoices_derived_steps_even_when_detail_is_unchanged(self) -> None:
        runner = self._build_runner()
        runner.client = Mock()
        runner._log = Mock()
        runner.client.request_json = Mock(
            side_effect=[
                (
                    {
                        "items": [
                            {"idNota": 100, "dataCriacao": "2026-06-28 01:00:00"},
                        ]
                    },
                    {},
                ),
                (
                    {
                        "idNota": 100,
                        "itens": [{"idItem": 501}],
                    },
                    {},
                ),
                (
                    {"url": "https://exemplo.local/nota/100"},
                    {},
                ),
                (
                    {"idItem": 501, "descricao": "Item conciliado"},
                    {},
                ),
            ]
        )
        runner.repository.upsert_raw_payload = Mock(
            side_effect=[
                UpsertResult(inserted=1, updated=0),
                UpsertResult(inserted=0, updated=0),
                UpsertResult(inserted=1, updated=0),
                UpsertResult(inserted=1, updated=0),
            ]
        )

        workflow = Workflow(
            entity_name="invoices",
            root_step="invoices.list",
            steps=(
                EndpointStep(
                    name="invoices.list",
                    endpoint_path="/notas",
                    pagination=True,
                    incremental=IncrementalStrategy(
                        mode="date_range",
                        start_param="dataInicial",
                        end_param="dataFinal",
                    ),
                    record_id_keys=("id", "idNota"),
                ),
                EndpointStep(
                    name="invoices.detail",
                    endpoint_path="/notas/{idNota}",
                    source_step="invoices.list",
                    path_params={"idNota": ("record_id", "id", "idNota")},
                    record_id_keys=("id", "idNota"),
                    singleton=True,
                    only_if_changed=True,
                ),
                EndpointStep(
                    name="invoices.link",
                    endpoint_path="/notas/{idNota}/link",
                    source_step="invoices.detail",
                    path_params={"idNota": ("record_id", "id", "idNota")},
                    singleton=True,
                    only_if_changed=True,
                ),
                EndpointStep(
                    name="invoices.item_detail",
                    endpoint_path="/notas/{idNota}/itens/{idItem}",
                    source_step="invoices.detail",
                    path_params={
                        "idNota": ("idNota",),
                        "idItem": ("record_id", "id", "idItem"),
                    },
                    nested_collection_keys=("itens",),
                    record_id_keys=("id", "idItem"),
                    singleton=True,
                    only_if_changed=True,
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-invoices-reconciliation",
            execution_type="reconciliation",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["requestCount"], 4)
        self.assertEqual(runner.client.request_json.call_count, 4)
        self.assertEqual(len(self.repository.reconcile_calls), 1)

    def test_reconciliation_marks_absent_records_as_deleted(self) -> None:
        runner = self._build_runner()
        self.repository.reconciled_deleted_total = 3
        runner.client = Mock()
        runner.client.request_json = Mock(return_value=({"items": [{"id": 1}]}, {}))

        workflow = Workflow(
            entity_name="products",
            root_step="products.list",
            steps=(
                EndpointStep(
                    name="products.list",
                    endpoint_path="/produtos",
                    pagination=True,
                    incremental=IncrementalStrategy(mode="watermark", start_param="dataAlteracao"),
                    record_id_keys=("id",),
                    updated_at_keys=("dataAlteracao",),
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-7",
            execution_type="reconciliation",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(self.repository.reconcile_calls), 1)
        self.assertEqual(self.repository.reconcile_calls[0]["execution_id"], "exec-7")
        self.assertIsNone(self.repository.saved_watermark)
        self.assertEqual(self.repository.finished_runs[-1]["details"]["reconciledDeletedCount"], 3)

    def test_reconciliation_invalid_json_fails_entity_and_skips_delete_reconcile(self) -> None:
        runner = self._build_runner()
        runner.client = Mock()
        runner.client.request_json = Mock(
            side_effect=[
                (
                    {
                        "items": [
                            {"id": 11, "dataEmissao": "2026-06-28 01:00:00"},
                        ]
                    },
                    {},
                ),
                OlistInvalidJsonError(
                    endpoint_path="/contas-receber/11/recebimentos",
                    status_code=200,
                    response_text="",
                    response_headers={"Content-Type": "text/plain"},
                ),
            ]
        )

        workflow = Workflow(
            entity_name="accounts_receivable",
            root_step="accounts_receivable.list",
            steps=(
                EndpointStep(
                    name="accounts_receivable.list",
                    endpoint_path="/contas-receber",
                    pagination=True,
                    incremental=IncrementalStrategy(
                        mode="date_range",
                        start_param="dataInicialEmissao",
                        end_param="dataFinalEmissao",
                    ),
                    record_id_keys=("id",),
                ),
                EndpointStep(
                    name="accounts_receivable.receipts",
                    endpoint_path="/contas-receber/{idContaReceber}/recebimentos",
                    source_step="accounts_receivable.list",
                    path_params={"idContaReceber": ("record_id", "id", "idContaReceber")},
                    ignore_invalid_json=True,
                ),
            ),
        )

        result = runner.run_workflow(
            execution_id="exec-reconciliation-invalid-json",
            execution_type="reconciliation",
            tenant_id="tenant-1",
            workflow=workflow,
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(len(self.repository.reconcile_calls), 0)
        self.assertEqual(self.repository.finished_runs[-1]["details"]["reconciledDeletedCount"], 0)


class ExtractionServiceTests(unittest.TestCase):
    def test_catalog_has_no_non_incremental_workflows(self) -> None:
        self.assertEqual(list_non_incremental_workflows(), [])

    def test_catalog_separates_products_stock_into_dedicated_workflow(self) -> None:
        products_workflow = WORKFLOW_BY_ENTITY["products"]
        products_stock_workflow = WORKFLOW_BY_ENTITY["products_stock"]

        self.assertTrue(all(step.name != "products.stock" for step in products_workflow.steps))
        self.assertEqual(products_stock_workflow.root_step, "products_stock.list")
        self.assertEqual(
            [step.name for step in products_stock_workflow.steps],
            ["products_stock.list", "products_stock.stock"],
        )

    def test_resolve_requested_workflows_skips_products_stock_by_policy_in_default_incremental(self) -> None:
        service = ExtractionService()
        repository = Mock()
        with TemporaryDirectory() as temp_dir:
            service.settings = build_settings(Path(temp_dir))
        repository.get_watermark.return_value = datetime.now(timezone.utc)

        workflows = service._resolve_requested_workflows(
            repository=repository,
            tenant_id="tenant-1",
            execution_type="incremental",
        )

        self.assertTrue(all(workflow.entity_name != "products_stock" for workflow in workflows))
        repository.get_watermark.assert_called_once_with("tenant-1", "products_stock", "/produtos")

    def test_resolve_requested_workflows_keeps_products_stock_when_policy_disabled(self) -> None:
        service = ExtractionService()
        repository = Mock()
        with TemporaryDirectory() as temp_dir:
            settings = build_settings(Path(temp_dir))
            service.settings = ExtractionSettings(
                database_url=settings.database_url,
                api_base_url=settings.api_base_url,
                timeout_seconds=settings.timeout_seconds,
                request_retries=settings.request_retries,
                backoff_seconds=settings.backoff_seconds,
                page_limit=settings.page_limit,
                safety_sleep_seconds=settings.safety_sleep_seconds,
                default_tenant_code=settings.default_tenant_code,
                default_tenant_name=settings.default_tenant_name,
                products_stock_cooldown_hours=0,
                execution_lease_seconds=settings.execution_lease_seconds,
                stop_poll_seconds=settings.stop_poll_seconds,
                log_directory=settings.log_directory,
                log_file_path=settings.log_file_path,
            )
        repository.get_watermark.return_value = datetime.now(timezone.utc) - timedelta(hours=1)

        workflows = service._resolve_requested_workflows(
            repository=repository,
            tenant_id="tenant-1",
            execution_type="incremental",
        )

        self.assertTrue(any(workflow.entity_name == "products_stock" for workflow in workflows))
        repository.get_watermark.assert_not_called()

    def test_start_execution_runs_only_incremental_policy_without_manual_entity_selection(self) -> None:
        service = ExtractionService()
        repository = Mock()
        repository.fetch_olist_settings.return_value = {"access_token": "token-ok"}
        repository.fetch_execution_control.return_value = {}
        repository.recover_expired_execution.return_value = None
        repository.claim_execution_slot.return_value = {"claimed": True, "execution_id": "exec-123"}
        repository.append_audit.return_value = None
        repository.get_watermark.return_value = datetime.now(timezone.utc)
        service.ensure_ready = Mock(return_value="tenant-1")
        service._get_repository = Mock(return_value=repository)
        service._launch_worker_process = Mock()

        response = service.start_execution(
            user_id="user-1",
            actor_email="teste@empresa.com",
            execution_type="incremental",
        )

        self.assertEqual(response["status"], "started")
        launch_kwargs = service._launch_worker_process.call_args.kwargs
        self.assertIn("workflow_names", launch_kwargs)
        self.assertNotIn("products_stock", launch_kwargs["workflow_names"])
        self.assertIsInstance(launch_kwargs["workflow_names"], list)

    def test_get_overview_recovers_orphan_execution_when_lock_is_free(self) -> None:
        service = ExtractionService()
        repository = Mock()
        repository.fetch_olist_settings.return_value = {}
        repository.fetch_recent_executions.return_value = []
        repository.fetch_execution_control.side_effect = [
            {"active_execution_id": "exec-orphan", "stop_requested_at": None},
            {"active_execution_id": None, "stop_requested_at": None},
        ]
        repository.recover_expired_execution.return_value = "exec-orphan"
        repository.append_audit.return_value = None

        service.ensure_ready = Mock(return_value="tenant-1")
        service._get_repository = Mock(return_value=repository)

        overview = service.get_overview()

        self.assertFalse(overview["running"])
        self.assertIsNone(overview["activeExecutionId"])
        repository.recover_expired_execution.assert_called_once()
        repository.append_audit.assert_called_once()

    @patch("backend.olist_extraction.service.list_non_incremental_workflows")
    def test_start_execution_rejects_incremental_when_any_entity_is_snapshot(
        self,
        mock_list_non_incremental_workflows: Mock,
    ) -> None:
        service = ExtractionService()
        repository = Mock()
        repository.fetch_olist_settings.return_value = {"access_token": "token-ok"}
        service.ensure_ready = Mock(return_value="tenant-1")
        service._get_repository = Mock(return_value=repository)
        mock_list_non_incremental_workflows.return_value = [
            Workflow(
                entity_name="company_info",
                root_step="company.info",
                steps=(EndpointStep(name="company.info", endpoint_path="/info", singleton=True),),
            )
        ]

        with self.assertRaises(RuntimeError) as context:
            service.start_execution(
                user_id="user-1",
                actor_email="teste@empresa.com",
                execution_type="incremental",
            )

        self.assertIn("company_info", str(context.exception))
        repository.try_acquire_execution_lock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
