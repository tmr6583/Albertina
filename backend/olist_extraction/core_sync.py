from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from sqlalchemy import text

from .load import ExtractionRepository
from .transform import extract_first_value, parse_olist_datetime


JSON_COLUMNS = {"source_payload", "raw_attributes", "consumer_final_payload", "details", "tax_attributes"}


@dataclass
class SyncEntityStats:
    processed: int = 0
    children: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "processed": self.processed,
            "children": self.children,
        }


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_decimal(value: Any) -> Decimal | None:
    if value in {None, "", "null"}:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        normalized = str(value).strip().replace(".", "").replace(",", ".") if isinstance(value, str) and value.count(",") == 1 and value.count(".") > 1 else str(value).strip().replace(",", ".")
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None


def _normalize_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "sim", "s", "a", "e", "ativo", "active"}:
        return True
    if text in {"0", "false", "f", "nao", "n", "i", "inactive", "inativo"}:
        return False
    return None


def _normalize_date(value: Any) -> date | None:
    if value in {None, "", "0000-00-00"}:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str) and len(value.strip()) == 7 and value.count("-") == 1:
        value = f"{value.strip()}-01"
    parsed = parse_olist_datetime(value)
    return parsed.date() if parsed is not None else None


def _normalize_datetime(value: Any) -> datetime | None:
    if value in {None, "", "0000-00-00", "0000-00-00 00:00:00"}:
        return None
    return parse_olist_datetime(value)


def _extract(payload: dict[str, Any], *candidate_keys: str) -> Any:
    return extract_first_value({"payload": payload}, tuple(candidate_keys))


def _extract_payload_id(payload: dict[str, Any], *candidate_keys: str) -> int | None:
    value = _extract(payload, *candidate_keys)
    if value in {None, ""}:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _json_value(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


def _row_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload") or {}
    return payload if isinstance(payload, dict) else {}


def _path_parts(endpoint_path: str) -> list[str]:
    return [part for part in str(endpoint_path or "").split("/") if part]


def _latest_rows_by_key(rows: Iterable[dict[str, Any]], key_getter: Any) -> list[dict[str, Any]]:
    selected: dict[Any, dict[str, Any]] = {}
    for row in rows:
        key = key_getter(row)
        if key in {None, ""}:
            continue
        current = selected.get(key)
        if current is None or len(str(row.get("endpoint_path") or "")) > len(str(current.get("endpoint_path") or "")):
            selected[key] = row
    return list(selected.values())


def _marker_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_markers = payload.get("marcadores")
    if not isinstance(raw_markers, list):
        return []
    unique: dict[str, dict[str, Any]] = {}
    for marker in raw_markers:
        if not isinstance(marker, dict):
            continue
        description = _normalize_text(_extract(marker, "descricao", "nome"))
        if description is None:
            continue
        unique[description] = marker
    return list(unique.values())


class CoreSyncService:
    def __init__(self, repository: ExtractionRepository):
        self.repository = repository
        self._execution_id_filter: str | None = None

    def sync_all(
        self,
        *,
        tenant_id: str,
        entity_names: list[str] | None = None,
        refresh_marts: bool = True,
        execution_id: str | None = None,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        requested = set(entity_names or [])
        stats: dict[str, SyncEntityStats] = {}
        self._execution_id_filter = execution_id

        sync_steps = [
            ("company_info", lambda connection: self._sync_company_info(connection, tenant_id, stats, requested)),
            (
                "users",
                lambda connection: self._sync_simple_lookup(
                    connection,
                    tenant_id,
                    stats,
                    requested,
                    "users",
                    "olist_core.olist_users",
                    "olist_user_id",
                    "olist_user_pk",
                    lambda payload: {
                        "tenant_id": tenant_id,
                        "olist_user_id": _extract_payload_id(payload, "id"),
                        "user_name": _extract(payload, "nome"),
                        "user_type": _extract(payload, "tipo"),
                        "email": _extract(payload, "email", "emailComunicacao"),
                        "status": None,
                        "source_payload": payload,
                    },
                ),
            ),
            ("vendors", lambda connection: self._sync_vendors(connection, tenant_id, stats, requested)),
            ("contacts", lambda connection: self._sync_contacts(connection, tenant_id, stats, requested)),
            (
                "brands",
                lambda connection: self._sync_simple_lookup(
                    connection,
                    tenant_id,
                    stats,
                    requested,
                    "brands",
                    "olist_core.brands",
                    "olist_brand_id",
                    "brand_id",
                    lambda payload: {
                        "tenant_id": tenant_id,
                        "olist_brand_id": _extract_payload_id(payload, "id"),
                        "brand_name": _extract(payload, "nome", "descricao"),
                        "is_active": _normalize_bool(_extract(payload, "situacao", "ativo")),
                        "source_payload": payload,
                    },
                ),
            ),
            ("categories", lambda connection: self._sync_categories(connection, tenant_id, stats, requested)),
            (
                "revenue_expense_categories",
                lambda connection: self._sync_revenue_expense_categories(connection, tenant_id, stats, requested),
            ),
            (
                "payment_methods",
                lambda connection: self._sync_simple_lookup(
                    connection,
                    tenant_id,
                    stats,
                    requested,
                    "payment_methods",
                    "olist_core.payment_methods",
                    "olist_payment_method_id",
                    "payment_method_id",
                    lambda payload: {
                        "tenant_id": tenant_id,
                        "olist_payment_method_id": _extract_payload_id(payload, "id"),
                        "payment_method_name": _extract(payload, "nome", "descricao", "meioPagamento"),
                        "source_payload": payload,
                    },
                ),
            ),
            (
                "receipt_methods",
                lambda connection: self._sync_simple_lookup(
                    connection,
                    tenant_id,
                    stats,
                    requested,
                    "receipt_methods",
                    "olist_core.receipt_methods",
                    "olist_receipt_method_id",
                    "receipt_method_id",
                    lambda payload: {
                        "tenant_id": tenant_id,
                        "olist_receipt_method_id": _extract_payload_id(payload, "id"),
                        "receipt_method_name": _extract(payload, "nome", "descricao", "formaRecebimento"),
                        "source_payload": payload,
                    },
                ),
            ),
            ("shipping_methods", lambda connection: self._sync_shipping_methods(connection, tenant_id, stats, requested)),
            (
                "deposits",
                lambda connection: self._sync_simple_lookup(
                    connection,
                    tenant_id,
                    stats,
                    requested,
                    "deposits",
                    "olist_core.deposits",
                    "olist_deposit_id",
                    "deposit_id",
                    lambda payload: {
                        "tenant_id": tenant_id,
                        "olist_deposit_id": _extract_payload_id(payload, "id"),
                        "deposit_name": _extract(payload, "nome", "descricao"),
                        "is_active": True if _normalize_bool(_extract(payload, "situacao")) is None else _normalize_bool(_extract(payload, "situacao")),
                        "source_payload": payload,
                    },
                ),
            ),
            (
                "intermediators",
                lambda connection: self._sync_simple_lookup(
                    connection,
                    tenant_id,
                    stats,
                    requested,
                    "intermediators",
                    "olist_core.intermediators",
                    "olist_intermediator_id",
                    "intermediator_id",
                    lambda payload: {
                        "tenant_id": tenant_id,
                        "olist_intermediator_id": _extract_payload_id(payload, "id"),
                        "intermediator_name": _extract(payload, "nome", "descricao"),
                        "cnpj": _extract(payload, "cnpj"),
                        "payment_institution_cnpj": _extract(payload, "cnpjInstituicaoPagamento"),
                        "source_payload": payload,
                    },
                ),
            ),
            (
                "services",
                lambda connection: self._sync_simple_lookup(
                    connection,
                    tenant_id,
                    stats,
                    requested,
                    "services",
                    "olist_core.services",
                    "olist_service_id",
                    "service_id",
                    lambda payload: {
                        "tenant_id": tenant_id,
                        "olist_service_id": _extract_payload_id(payload, "id"),
                        "service_code": _extract(payload, "codigo"),
                        "service_name": _extract(payload, "nome", "descricao"),
                        "is_active": _normalize_bool(_extract(payload, "situacao", "ativo")),
                        "raw_attributes": payload,
                        "source_payload": payload,
                    },
                ),
            ),
            ("tag_groups", lambda connection: self._sync_tag_groups(connection, tenant_id, stats, requested)),
            ("product_tags", lambda connection: self._sync_product_tags(connection, tenant_id, stats, requested)),
            ("price_lists", lambda connection: self._sync_price_lists(connection, tenant_id, stats, requested)),
            ("products", lambda connection: self._sync_products(connection, tenant_id, stats, requested)),
            ("products_stock", lambda connection: self._sync_stock_balances(connection, tenant_id, stats, requested)),
            ("operation_natures", lambda connection: self._sync_operation_natures_from_orders(connection, tenant_id)),
            ("orders", lambda connection: self._sync_orders(connection, tenant_id, stats, requested)),
            ("purchase_orders", lambda connection: self._sync_purchase_orders(connection, tenant_id, stats, requested)),
            ("service_orders", lambda connection: self._sync_service_orders(connection, tenant_id, stats, requested)),
            ("invoices", lambda connection: self._sync_invoices(connection, tenant_id, stats, requested)),
            ("accounts_receivable", lambda connection: self._sync_accounts_receivable(connection, tenant_id, stats, requested)),
            ("accounts_payable", lambda connection: self._sync_accounts_payable(connection, tenant_id, stats, requested)),
            ("shipments", lambda connection: self._sync_shipments(connection, tenant_id, stats, requested)),
            ("separations", lambda connection: self._sync_separations(connection, tenant_id, stats, requested)),
            ("crm_stages", lambda connection: self._sync_crm_stages(connection, tenant_id, stats, requested)),
            ("crm_subjects", lambda connection: self._sync_crm_subjects(connection, tenant_id, stats, requested)),
        ]

        try:
            for step_name, step_runner in sync_steps:
                if progress_callback is not None:
                    progress_callback(step_name)
                with self.repository.begin() as connection:
                    step_runner(connection)

            if refresh_marts:
                if progress_callback is not None:
                    progress_callback("refresh_marts")
                with self.repository.begin() as connection:
                    connection.execute(text("SELECT olist_admin.refresh_olist_mart_views(FALSE)"))
        finally:
            self._execution_id_filter = None

        return {entity: entity_stats.as_dict() for entity, entity_stats in stats.items()}

    def _should_sync(self, requested: set[str], entity_name: str) -> bool:
        return not requested or entity_name in requested

    def _fetch_rows(
        self,
        connection: Any,
        tenant_id: str,
        entity_name: str,
        execution_id: str | None = None,
    ) -> list[dict[str, Any]]:
        resolved_execution_id = execution_id or self._execution_id_filter
        rows = connection.execute(
            text(
                """
                SELECT endpoint_path, olist_object_id, parent_olist_object_id, source_updated_at, payload
                FROM olist_raw.api_payloads
                WHERE tenant_id = :tenant_id
                  AND entity_name = :entity_name
                  AND is_deleted = FALSE
                  AND (:execution_id IS NULL OR last_seen_execution_id = CAST(:execution_id AS UUID))
                ORDER BY endpoint_path, created_at DESC
                """
            ),
            {"tenant_id": tenant_id, "entity_name": entity_name, "execution_id": resolved_execution_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def _lookup_uuid_map(self, connection: Any, table_name: str, id_column: str, pk_column: str, tenant_id: str) -> dict[int, str]:
        rows = connection.execute(
            text(
                f"""
                SELECT {id_column} AS raw_id, {pk_column} AS pk
                FROM {table_name}
                WHERE tenant_id = :tenant_id
                  AND {id_column} IS NOT NULL
                """
            ),
            {"tenant_id": tenant_id},
        ).mappings().all()
        return {int(row["raw_id"]): str(row["pk"]) for row in rows if row["raw_id"] is not None}

    def _delete_children(self, connection: Any, table_name: str, tenant_id: str, parent_column: str, parent_id: str) -> None:
        connection.execute(
            text(f"DELETE FROM {table_name} WHERE tenant_id = :tenant_id AND {parent_column} = :parent_id"),
            {"tenant_id": tenant_id, "parent_id": parent_id},
        )

    def _insert_row(self, connection: Any, table_name: str, values: dict[str, Any]) -> None:
        columns = list(values.keys())
        serialized = {
            key: (_json_value(value) if key in JSON_COLUMNS else value)
            for key, value in values.items()
        }
        value_exprs = [f"CAST(:{column} AS JSONB)" if column in JSON_COLUMNS else f":{column}" for column in columns]
        connection.execute(
            text(
                f"""
                INSERT INTO {table_name} ({", ".join(columns)})
                VALUES ({", ".join(value_exprs)})
                """
            ),
            serialized,
        )

    def _upsert_row(
        self,
        connection: Any,
        table_name: str,
        values: dict[str, Any],
        conflict_columns: list[str],
        returning_column: str,
    ) -> str:
        columns = list(values.keys())
        serialized = {
            key: (_json_value(value) if key in JSON_COLUMNS else value)
            for key, value in values.items()
        }
        value_exprs = [f"CAST(:{column} AS JSONB)" if column in JSON_COLUMNS else f":{column}" for column in columns]
        update_columns = [column for column in columns if column not in conflict_columns]
        update_expr = ", ".join(f"{column} = EXCLUDED.{column}" for column in update_columns)
        row = connection.execute(
            text(
                f"""
                INSERT INTO {table_name} ({", ".join(columns)})
                VALUES ({", ".join(value_exprs)})
                ON CONFLICT ({", ".join(conflict_columns)}) DO UPDATE
                SET {update_expr}
                RETURNING {returning_column}
                """
            ),
            serialized,
        ).mappings().one()
        return str(row[returning_column])

    def _sync_company_info(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "company_info"):
            return
        rows = self._fetch_rows(connection, tenant_id, "company_info")
        if not rows:
            return
        stats["company_info"] = SyncEntityStats(processed=1)
        payload = _row_payload(rows[0])
        connection.execute(text("DELETE FROM olist_core.companies WHERE tenant_id = :tenant_id"), {"tenant_id": tenant_id})
        self._insert_row(
            connection,
            "olist_core.companies",
            {
                "tenant_id": tenant_id,
                "olist_company_id": None,
                "legal_name": _extract(payload, "razaoSocial"),
                "trade_name": _extract(payload, "fantasia"),
                "cnpj": _extract(payload, "cpfCnpj"),
                "state_registration": _extract(payload, "inscricaoEstadual"),
                "company_type": _extract(payload, "regimeTributario"),
                "source_payload": payload,
            },
        )

    def _sync_simple_lookup(
        self,
        connection: Any,
        tenant_id: str,
        stats: dict[str, SyncEntityStats],
        requested: set[str],
        entity_name: str,
        table_name: str,
        raw_id_column: str,
        pk_column: str,
        builder: Any,
    ) -> None:
        if not self._should_sync(requested, entity_name):
            return
        rows = self._fetch_rows(connection, tenant_id, entity_name)
        if not rows:
            return
        processed = 0
        for row in rows:
            payload = _row_payload(row)
            values = builder(payload)
            raw_id = values.get(raw_id_column)
            if raw_id is None:
                continue
            self._upsert_row(connection, table_name, values, ["tenant_id", raw_id_column], pk_column)
            processed += 1
        stats[entity_name] = SyncEntityStats(processed=processed)

    def _sync_vendors(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "vendors"):
            return
        rows = self._fetch_rows(connection, tenant_id, "vendors")
        if not rows:
            return
        processed = 0
        for row in rows:
            payload = _row_payload(row)
            vendor_id = _extract_payload_id(payload, "id")
            contact = payload.get("contato") if isinstance(payload.get("contato"), dict) else {}
            if vendor_id is None:
                continue
            self._upsert_row(
                connection,
                "olist_core.vendors",
                {
                    "tenant_id": tenant_id,
                    "olist_vendor_id": vendor_id,
                    "vendor_name": _extract(contact, "nome") or _extract(payload, "nome"),
                    "vendor_code": _extract(contact, "codigo"),
                    "email": _extract(contact, "email"),
                    "source_payload": payload,
                },
                ["tenant_id", "olist_vendor_id"],
                "vendor_id",
            )
            processed += 1
        stats["vendors"] = SyncEntityStats(processed=processed)

    def _sync_contacts(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "contacts"):
            return
        rows = self._fetch_rows(connection, tenant_id, "contacts")
        if not rows:
            return
        vendor_map = self._lookup_uuid_map(connection, "olist_core.vendors", "olist_vendor_id", "vendor_id", tenant_id)
        type_map = self._lookup_uuid_map(connection, "olist_core.contact_types", "olist_contact_type_id", "contact_type_id", tenant_id)
        processed = 0
        children = 0
        for row in rows:
            payload = _row_payload(row)
            contact_id_raw = _extract_payload_id(payload, "id")
            if contact_id_raw is None:
                continue
            for contact_type in payload.get("tipos") or []:
                if not isinstance(contact_type, dict):
                    continue
                raw_type_id = _extract_payload_id(contact_type, "id")
                type_name = _extract(contact_type, "descricao", "nome")
                if type_name is None:
                    continue
                conflict_columns = ["tenant_id", "olist_contact_type_id"] if raw_type_id is not None else ["tenant_id", "type_name"]
                values = {
                    "tenant_id": tenant_id,
                    "olist_contact_type_id": raw_type_id,
                    "type_name": type_name,
                    "is_active": True,
                    "source_payload": contact_type,
                }
                type_pk = self._upsert_row(connection, "olist_core.contact_types", values, conflict_columns, "contact_type_id")
                if raw_type_id is not None:
                    type_map[raw_type_id] = type_pk

            vendor_payload = payload.get("vendedor") if isinstance(payload.get("vendedor"), dict) else {}
            vendor_pk = vendor_map.get(_extract_payload_id(vendor_payload, "id") or -1)
            contact_type_pk = None
            first_type = next((item for item in payload.get("tipos") or [] if isinstance(item, dict)), None)
            if first_type is not None:
                contact_type_pk = type_map.get(_extract_payload_id(first_type, "id") or -1)

            contact_pk = self._upsert_row(
                connection,
                "olist_core.contacts",
                {
                    "tenant_id": tenant_id,
                    "olist_contact_id": contact_id_raw,
                    "contact_code": _extract(payload, "codigo"),
                    "contact_name": _extract(payload, "nome"),
                    "trade_name": _extract(payload, "fantasia"),
                    "person_type": _extract(payload, "tipoPessoa"),
                    "cpf_cnpj": _extract(payload, "cpfCnpj"),
                    "state_registration": _extract(payload, "inscricaoEstadual"),
                    "rg": _extract(payload, "rg"),
                    "phone": _extract(payload, "telefone"),
                    "mobile": _extract(payload, "celular"),
                    "email": _extract(payload, "email"),
                    "crm_status": _extract(payload, "statusCrm"),
                    "vendor_id": vendor_pk,
                    "contact_type_id": contact_type_pk,
                    "source_payload": payload,
                },
                ["tenant_id", "olist_contact_id"],
                "contact_id",
            )
            processed += 1

            self._delete_children(connection, "olist_core.contact_people", tenant_id, "contact_id", contact_pk)
            self._delete_children(connection, "olist_core.addresses", tenant_id, "contact_id", contact_pk)

            for role_name, key_name in (
                ("principal", "endereco"),
                ("cobranca", "enderecoCobranca"),
            ):
                address = payload.get(key_name)
                if not isinstance(address, dict):
                    continue
                self._insert_row(
                    connection,
                    "olist_core.addresses",
                    {
                        "tenant_id": tenant_id,
                        "contact_id": contact_pk,
                        "address_role": role_name,
                        "recipient_name": _extract(payload, "nome"),
                        "person_type": _extract(payload, "tipoPessoa"),
                        "cpf_cnpj": _extract(payload, "cpfCnpj"),
                        "state_registration": _extract(payload, "inscricaoEstadual"),
                        "phone": _extract(payload, "telefone", "celular"),
                        "street": _extract(address, "endereco"),
                        "street_number": _extract(address, "numero"),
                        "complement": _extract(address, "complemento"),
                        "district": _extract(address, "bairro"),
                        "city": _extract(address, "municipio"),
                        "state": _extract(address, "uf"),
                        "zip_code": _extract(address, "cep"),
                        "country": _extract(address, "pais"),
                        "source_payload": address,
                    },
                )
                children += 1

            contact_people = payload.get("contatos")
            if isinstance(contact_people, list):
                for person in contact_people:
                    if not isinstance(person, dict):
                        continue
                    self._insert_row(
                        connection,
                        "olist_core.contact_people",
                        {
                            "tenant_id": tenant_id,
                            "contact_id": contact_pk,
                            "olist_contact_person_id": _extract_payload_id(person, "id"),
                            "person_name": _extract(person, "nome"),
                            "role_name": _extract(person, "cargo"),
                            "email": _extract(person, "email"),
                            "phone": _extract(person, "telefone"),
                            "mobile": _extract(person, "celular"),
                            "source_payload": person,
                        },
                    )
                    children += 1

        stats["contacts"] = SyncEntityStats(processed=processed, children=children)

    def _sync_categories(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "categories"):
            return
        rows = self._fetch_rows(connection, tenant_id, "categories")
        if not rows:
            return
        staged: list[tuple[int, int | None]] = []
        processed = 0
        for row in rows:
            payload = _row_payload(row)
            category_raw_id = _extract_payload_id(payload, "id")
            if category_raw_id is None:
                continue
            parent_raw_id = _extract_payload_id(payload, "idPai", "idCategoriaPai")
            self._upsert_row(
                connection,
                "olist_core.categories",
                {
                    "tenant_id": tenant_id,
                    "olist_category_id": category_raw_id,
                    "parent_category_id": None,
                    "parent_olist_category_id": parent_raw_id,
                    "category_name": _extract(payload, "nome", "descricao"),
                    "tree_level": _extract(payload, "nivel"),
                    "source_payload": payload,
                },
                ["tenant_id", "olist_category_id"],
                "category_id",
            )
            staged.append((category_raw_id, parent_raw_id))
            processed += 1

        category_map = self._lookup_uuid_map(connection, "olist_core.categories", "olist_category_id", "category_id", tenant_id)
        for category_raw_id, parent_raw_id in staged:
            if parent_raw_id is None:
                continue
            parent_pk = category_map.get(parent_raw_id)
            current_pk = category_map.get(category_raw_id)
            if parent_pk and current_pk:
                connection.execute(
                    text(
                        """
                        UPDATE olist_core.categories
                        SET parent_category_id = :parent_pk
                        WHERE tenant_id = :tenant_id
                          AND category_id = :current_pk
                        """
                    ),
                    {"tenant_id": tenant_id, "parent_pk": parent_pk, "current_pk": current_pk},
                )

        stats["categories"] = SyncEntityStats(processed=processed)

    def _sync_revenue_expense_categories(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "revenue_expense_categories"):
            return
        rows = self._fetch_rows(connection, tenant_id, "revenue_expense_categories")
        if not rows:
            return
        staged: list[tuple[int, int | None]] = []
        processed = 0
        for row in rows:
            payload = _row_payload(row)
            category_raw_id = _extract_payload_id(payload, "id")
            if category_raw_id is None:
                continue
            kind = _normalize_text(_extract(payload, "tipo", "categoria", "tipoCategoria")) or ""
            kind_normalized = "receita" if "rece" in kind.lower() else "despesa"
            parent_raw_id = _extract_payload_id(payload, "idPai", "categoriaPai", "idCategoriaPai")
            self._upsert_row(
                connection,
                "olist_core.revenue_expense_categories",
                {
                    "tenant_id": tenant_id,
                    "olist_fin_category_id": category_raw_id,
                    "category_name": _extract(payload, "descricao", "nome"),
                    "category_kind": kind_normalized,
                    "parent_category_fin_id": None,
                    "parent_olist_fin_category_id": parent_raw_id,
                    "source_payload": payload,
                },
                ["tenant_id", "olist_fin_category_id"],
                "category_fin_id",
            )
            staged.append((category_raw_id, parent_raw_id))
            processed += 1

        category_map = self._lookup_uuid_map(connection, "olist_core.revenue_expense_categories", "olist_fin_category_id", "category_fin_id", tenant_id)
        for category_raw_id, parent_raw_id in staged:
            if parent_raw_id is None:
                continue
            parent_pk = category_map.get(parent_raw_id)
            current_pk = category_map.get(category_raw_id)
            if parent_pk and current_pk:
                connection.execute(
                    text(
                        """
                        UPDATE olist_core.revenue_expense_categories
                        SET parent_category_fin_id = :parent_pk
                        WHERE tenant_id = :tenant_id
                          AND category_fin_id = :current_pk
                        """
                    ),
                    {"tenant_id": tenant_id, "parent_pk": parent_pk, "current_pk": current_pk},
                )

        stats["revenue_expense_categories"] = SyncEntityStats(processed=processed)

    def _sync_shipping_methods(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "shipping_methods"):
            return
        rows = self._fetch_rows(connection, tenant_id, "shipping_methods")
        if not rows:
            return
        processed = 0
        freight_children = 0
        for row in rows:
            payload = _row_payload(row)
            shipping_raw_id = _extract_payload_id(payload, "id")
            if shipping_raw_id is None:
                continue
            self._upsert_row(
                connection,
                "olist_core.shipping_methods",
                {
                    "tenant_id": tenant_id,
                    "olist_shipping_method_id": shipping_raw_id,
                    "shipping_method_name": _extract(payload, "nome", "descricao"),
                    "source_payload": payload,
                },
                ["tenant_id", "olist_shipping_method_id"],
                "shipping_method_id",
            )
            processed += 1
            for freight in payload.get("formasFrete") or []:
                if not isinstance(freight, dict):
                    continue
                freight_raw_id = _extract_payload_id(freight, "id")
                freight_name = _extract(freight, "nome", "descricao")
                if freight_name is None:
                    continue
                conflict_columns = ["tenant_id", "olist_freight_method_id"] if freight_raw_id is not None else ["tenant_id", "freight_method_name"]
                self._upsert_row(
                    connection,
                    "olist_core.freight_methods",
                    {
                        "tenant_id": tenant_id,
                        "olist_freight_method_id": freight_raw_id,
                        "freight_method_name": freight_name,
                        "source_payload": freight,
                    },
                    conflict_columns,
                    "freight_method_id",
                )
                freight_children += 1
        stats["shipping_methods"] = SyncEntityStats(processed=processed, children=freight_children)

    def _sync_tag_groups(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "tag_groups"):
            return
        rows = self._fetch_rows(connection, tenant_id, "tag_groups")
        if not rows:
            return
        processed = 0
        for row in rows:
            payload = _row_payload(row)
            tag_group_raw_id = _extract_payload_id(payload, "id")
            if tag_group_raw_id is None:
                continue
            self._upsert_row(
                connection,
                "olist_core.tag_groups",
                {
                    "tenant_id": tenant_id,
                    "olist_tag_group_id": tag_group_raw_id,
                    "group_name": _extract(payload, "nome", "descricao"),
                    "source_payload": payload,
                },
                ["tenant_id", "olist_tag_group_id"],
                "tag_group_id",
            )
            processed += 1
        stats["tag_groups"] = SyncEntityStats(processed=processed)

    def _sync_product_tags(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "product_tags"):
            return
        rows = self._fetch_rows(connection, tenant_id, "product_tags")
        if not rows:
            return
        tag_group_map = self._lookup_uuid_map(connection, "olist_core.tag_groups", "olist_tag_group_id", "tag_group_id", tenant_id)
        processed = 0
        for row in rows:
            payload = _row_payload(row)
            tag_raw_id = _extract_payload_id(payload, "id")
            if tag_raw_id is None:
                continue
            nested_group = payload.get("grupo") if isinstance(payload.get("grupo"), dict) else {}
            self._upsert_row(
                connection,
                "olist_core.product_tags",
                {
                    "tenant_id": tenant_id,
                    "olist_product_tag_id": tag_raw_id,
                    "tag_group_id": tag_group_map.get(_extract_payload_id(nested_group, "id") or -1),
                    "tag_name": _extract(payload, "nome", "descricao"),
                    "source_payload": payload,
                },
                ["tenant_id", "olist_product_tag_id"],
                "product_tag_id",
            )
            processed += 1
        stats["product_tags"] = SyncEntityStats(processed=processed)

    def _sync_price_lists(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "price_lists"):
            return
        rows = self._fetch_rows(connection, tenant_id, "price_lists")
        if not rows:
            return
        processed = 0
        children = 0
        product_map = self._lookup_uuid_map(connection, "olist_core.products", "olist_product_id", "product_id", tenant_id)
        for row in rows:
            payload = _row_payload(row)
            price_list_raw_id = _extract_payload_id(payload, "id")
            if price_list_raw_id is None:
                continue
            price_list_pk = self._upsert_row(
                connection,
                "olist_core.price_lists",
                {
                    "tenant_id": tenant_id,
                    "olist_price_list_id": price_list_raw_id,
                    "price_list_name": _extract(payload, "nome", "descricao"),
                    "adjustment_value": _normalize_decimal(_extract(payload, "acrescimoDesconto", "percentual")),
                    "is_active": _normalize_bool(_extract(payload, "situacao", "ativo")),
                    "source_payload": payload,
                },
                ["tenant_id", "olist_price_list_id"],
                "price_list_id",
            )
            processed += 1
            self._delete_children(connection, "olist_core.price_list_items", tenant_id, "price_list_id", price_list_pk)
            for item in payload.get("itens") or []:
                if not isinstance(item, dict):
                    continue
                item_product = item.get("produto") if isinstance(item.get("produto"), dict) else {}
                item_product_id = _extract_payload_id(item_product, "id", "idProduto") or _extract_payload_id(item, "idProduto")
                self._insert_row(
                    connection,
                    "olist_core.price_list_items",
                    {
                        "tenant_id": tenant_id,
                        "price_list_id": price_list_pk,
                        "product_id": product_map.get(item_product_id or -1),
                        "olist_product_id": item_product_id,
                        "unit_price": _normalize_decimal(_extract(item, "preco", "valor", "valorUnitario")),
                        "source_payload": item,
                    },
                )
                children += 1
        stats["price_lists"] = SyncEntityStats(processed=processed, children=children)

    def _sync_products(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "products"):
            return
        rows = self._fetch_rows(connection, tenant_id, "products")
        if not rows:
            return
        category_map = self._lookup_uuid_map(connection, "olist_core.categories", "olist_category_id", "category_id", tenant_id)
        brand_map = self._lookup_uuid_map(connection, "olist_core.brands", "olist_brand_id", "brand_id", tenant_id)
        product_tag_map = self._lookup_uuid_map(connection, "olist_core.product_tags", "olist_product_tag_id", "product_tag_id", tenant_id)
        processed = 0
        children = 0
        for row in rows:
            payload = _row_payload(row)
            product_raw_id = _extract_payload_id(payload, "id")
            if product_raw_id is None:
                continue
            category_payload = payload.get("categoria") if isinstance(payload.get("categoria"), dict) else {}
            brand_payload = payload.get("marca") if isinstance(payload.get("marca"), dict) else {}
            product_pk = self._upsert_row(
                connection,
                "olist_core.products",
                {
                    "tenant_id": tenant_id,
                    "olist_product_id": product_raw_id,
                    "product_code": _extract(payload, "codigo", "sku"),
                    "product_name": _extract(payload, "descricao", "nome"),
                    "sku": _extract(payload, "sku"),
                    "gtin": _extract(payload, "gtin"),
                    "product_type": _extract(payload, "tipo"),
                    "category_id": category_map.get(_extract_payload_id(category_payload, "id") or -1),
                    "brand_id": brand_map.get(_extract_payload_id(brand_payload, "id") or -1),
                    "is_active": _normalize_bool(_extract(payload, "situacao", "ativo")),
                    "source_updated_at": row.get("source_updated_at"),
                    "raw_attributes": payload,
                    "source_payload": payload,
                },
                ["tenant_id", "olist_product_id"],
                "product_id",
            )
            processed += 1

            self._delete_children(connection, "olist_core.product_variants", tenant_id, "product_id", product_pk)
            self._delete_children(connection, "olist_core.product_tag_links", tenant_id, "product_id", product_pk)

            for variant in payload.get("variacoes") or []:
                if not isinstance(variant, dict):
                    continue
                self._insert_row(
                    connection,
                    "olist_core.product_variants",
                    {
                        "tenant_id": tenant_id,
                        "product_id": product_pk,
                        "olist_variant_id": _extract_payload_id(variant, "id"),
                        "variant_code": _extract(variant, "codigo", "sku"),
                        "variant_name": _extract(variant, "descricao", "nome"),
                        "gtin": _extract(variant, "gtin"),
                        "raw_attributes": variant,
                        "source_payload": variant,
                    },
                )
                children += 1

            for tag in payload.get("tags") or []:
                if not isinstance(tag, dict):
                    continue
                tag_raw_id = _extract_payload_id(tag, "id")
                tag_pk = product_tag_map.get(tag_raw_id or -1)
                if tag_pk is None:
                    continue
                self._insert_row(
                    connection,
                    "olist_core.product_tag_links",
                    {
                        "tenant_id": tenant_id,
                        "product_id": product_pk,
                        "product_tag_id": tag_pk,
                    },
                )
                children += 1
        stats["products"] = SyncEntityStats(processed=processed, children=children)

    def _sync_stock_balances(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "products_stock"):
            return
        rows = self._fetch_rows(connection, tenant_id, "products_stock")
        if not rows:
            return
        product_map = self._lookup_uuid_map(connection, "olist_core.products", "olist_product_id", "product_id", tenant_id)
        deposit_map = self._lookup_uuid_map(connection, "olist_core.deposits", "olist_deposit_id", "deposit_id", tenant_id)
        processed = 0
        for row in rows:
            payload = _row_payload(row)
            product_raw_id = _extract_payload_id(payload, "id")
            product_pk = product_map.get(product_raw_id or -1)
            if product_pk is None:
                continue
            deposits = payload.get("depositos") if isinstance(payload.get("depositos"), list) and payload.get("depositos") else []
            if not deposits:
                deposits = [{"id": None, "saldo": payload.get("saldo"), "reservado": payload.get("reservado"), "disponivel": payload.get("disponivel")}]
            for deposit in deposits:
                if not isinstance(deposit, dict):
                    continue
                deposit_raw_id = _extract_payload_id(deposit, "id")
                connection.execute(
                    text(
                        """
                        DELETE FROM olist_core.stock_balances
                        WHERE tenant_id = :tenant_id
                          AND product_id = :product_id
                          AND (
                            (:deposit_id IS NULL AND deposit_id IS NULL)
                            OR deposit_id = :deposit_id
                          )
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "product_id": product_pk,
                        "deposit_id": deposit_map.get(deposit_raw_id or -1),
                    },
                )
                self._insert_row(
                    connection,
                    "olist_core.stock_balances",
                    {
                        "tenant_id": tenant_id,
                        "product_id": product_pk,
                        "deposit_id": deposit_map.get(deposit_raw_id or -1),
                        "physical_qty": _normalize_decimal(_extract(deposit, "saldo")) or _normalize_decimal(_extract(payload, "saldo")),
                        "reserved_qty": _normalize_decimal(_extract(deposit, "reservado")) or _normalize_decimal(_extract(payload, "reservado")),
                        "available_qty": _normalize_decimal(_extract(deposit, "disponivel")) or _normalize_decimal(_extract(payload, "disponivel")),
                        "source_updated_at": row.get("source_updated_at"),
                        "source_payload": deposit if deposit_raw_id is not None else payload,
                    },
                )
                processed += 1
        stats["products_stock"] = SyncEntityStats(processed=processed)

    def _sync_operation_natures_from_orders(self, connection: Any, tenant_id: str) -> None:
        rows = self._fetch_rows(connection, tenant_id, "orders")
        for row in rows:
            payload = _row_payload(row)
            nature = payload.get("naturezaOperacao") if isinstance(payload.get("naturezaOperacao"), dict) else {}
            nature_raw_id = _extract_payload_id(nature, "id")
            nature_name = _extract(nature, "nome", "descricao")
            if nature_name is None:
                continue
            conflict_columns = ["tenant_id", "olist_operation_nature_id"] if nature_raw_id is not None else ["tenant_id", "operation_nature_name"]
            self._upsert_row(
                connection,
                "olist_core.operation_natures",
                {
                    "tenant_id": tenant_id,
                    "olist_operation_nature_id": nature_raw_id,
                    "operation_nature_name": nature_name,
                    "source_payload": nature,
                },
                conflict_columns,
                "operation_nature_id",
            )

    def _sync_orders(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "orders"):
            return
        rows = self._fetch_rows(connection, tenant_id, "orders")
        if not rows:
            return
        contact_map = self._lookup_uuid_map(connection, "olist_core.contacts", "olist_contact_id", "contact_id", tenant_id)
        vendor_map = self._lookup_uuid_map(connection, "olist_core.vendors", "olist_vendor_id", "vendor_id", tenant_id)
        deposit_map = self._lookup_uuid_map(connection, "olist_core.deposits", "olist_deposit_id", "deposit_id", tenant_id)
        price_list_map = self._lookup_uuid_map(connection, "olist_core.price_lists", "olist_price_list_id", "price_list_id", tenant_id)
        intermediator_map = self._lookup_uuid_map(connection, "olist_core.intermediators", "olist_intermediator_id", "intermediator_id", tenant_id)
        product_map = self._lookup_uuid_map(connection, "olist_core.products", "olist_product_id", "product_id", tenant_id)
        service_map = self._lookup_uuid_map(connection, "olist_core.services", "olist_service_id", "service_id", tenant_id)
        operation_nature_map = self._lookup_uuid_map(connection, "olist_core.operation_natures", "olist_operation_nature_id", "operation_nature_id", tenant_id)
        receipt_method_map = self._lookup_uuid_map(connection, "olist_core.receipt_methods", "olist_receipt_method_id", "receipt_method_id", tenant_id)
        payment_method_map = self._lookup_uuid_map(connection, "olist_core.payment_methods", "olist_payment_method_id", "payment_method_id", tenant_id)
        shipping_method_map = self._lookup_uuid_map(connection, "olist_core.shipping_methods", "olist_shipping_method_id", "shipping_method_id", tenant_id)
        freight_method_map = self._lookup_uuid_map(connection, "olist_core.freight_methods", "olist_freight_method_id", "freight_method_id", tenant_id)
        processed = 0
        children = 0
        for row in rows:
            payload = _row_payload(row)
            order_raw_id = _extract_payload_id(payload, "id")
            if order_raw_id is None:
                continue
            customer = payload.get("cliente") if isinstance(payload.get("cliente"), dict) else {}
            vendor = payload.get("vendedor") if isinstance(payload.get("vendedor"), dict) else {}
            deposit = payload.get("deposito") if isinstance(payload.get("deposito"), dict) else {}
            price_list = payload.get("listaPreco") if isinstance(payload.get("listaPreco"), dict) else {}
            intermediator = payload.get("intermediador") if isinstance(payload.get("intermediador"), dict) else {}
            nature = payload.get("naturezaOperacao") if isinstance(payload.get("naturezaOperacao"), dict) else {}
            order_pk = self._upsert_row(
                connection,
                "olist_core.orders",
                {
                    "tenant_id": tenant_id,
                    "olist_order_id": order_raw_id,
                    "order_number": _extract(payload, "numeroPedido"),
                    "order_status": _extract(payload, "situacao"),
                    "order_origin": _extract(payload, "origemPedido"),
                    "olist_invoice_id": _extract(payload, "idNotaFiscal"),
                    "contact_id": contact_map.get(_extract_payload_id(customer, "id") or -1),
                    "vendor_id": vendor_map.get(_extract_payload_id(vendor, "id") or -1),
                    "deposit_id": deposit_map.get(_extract_payload_id(deposit, "id") or -1),
                    "price_list_id": price_list_map.get(_extract_payload_id(price_list, "id") or -1),
                    "intermediator_id": intermediator_map.get(_extract_payload_id(intermediator, "id") or -1),
                    "operation_nature_id": operation_nature_map.get(_extract_payload_id(nature, "id") or -1),
                    "billing_address_id": None,
                    "shipping_address_id": None,
                    "external_order_number": _extract(payload, "numeroPedidoExterno"),
                    "sales_channel_order_number": _extract(payload, "numeroPedidoCanalVenda"),
                    "sales_channel_name": _extract(payload.get("ecommerce") if isinstance(payload.get("ecommerce"), dict) else {}, "canalVenda"),
                    "ecommerce_name": _extract(payload.get("ecommerce") if isinstance(payload.get("ecommerce"), dict) else {}, "nome"),
                    "order_date": _normalize_date(_extract(payload, "data")),
                    "delivery_date": _normalize_date(_extract(payload, "dataEntrega")),
                    "billing_date": _normalize_datetime(_extract(payload, "dataFaturamento")),
                    "expected_date": _normalize_date(_extract(payload, "dataPrevista")),
                    "shipped_at": _normalize_datetime(_extract(payload, "dataEnvio")),
                    "purchase_order_number": _extract(payload, "numeroOrdemCompra"),
                    "total_products_amount": _normalize_decimal(_extract(payload, "valorTotalProdutos")),
                    "total_order_amount": _normalize_decimal(_extract(payload, "valorTotalPedido")),
                    "discount_amount": _normalize_decimal(_extract(payload, "valorDesconto")),
                    "freight_amount": _normalize_decimal(_extract(payload, "valorFrete")),
                    "other_expenses_amount": _normalize_decimal(_extract(payload, "valorOutrasDespesas")),
                    "notes": _extract(payload, "observacoes"),
                    "internal_notes": _extract(payload, "observacoesInternas"),
                    "is_consumer_final": False if _normalize_bool(_extract(payload, "consumidorFinal")) is None else bool(_normalize_bool(_extract(payload, "consumidorFinal"))),
                    "consumer_final_payload": payload.get("consumidorFinal") if isinstance(payload.get("consumidorFinal"), dict) else {},
                    "source_updated_at": row.get("source_updated_at"),
                    "raw_attributes": payload,
                    "source_payload": payload,
                },
                ["tenant_id", "olist_order_id"],
                "order_id",
            )
            processed += 1

            self._delete_children(connection, "olist_core.order_items", tenant_id, "order_id", order_pk)
            self._delete_children(connection, "olist_core.order_markers", tenant_id, "order_id", order_pk)
            self._delete_children(connection, "olist_core.order_installments", tenant_id, "order_id", order_pk)
            self._delete_children(connection, "olist_core.order_integrated_payments", tenant_id, "order_id", order_pk)
            self._delete_children(connection, "olist_core.order_shipping", tenant_id, "order_id", order_pk)
            self._delete_children(connection, "olist_core.order_operations", tenant_id, "order_id", order_pk)

            for index, item in enumerate(payload.get("itens") or [], start=1):
                if not isinstance(item, dict):
                    continue
                product = item.get("produto") if isinstance(item.get("produto"), dict) else {}
                service = item.get("servico") if isinstance(item.get("servico"), dict) else {}
                product_raw_id = _extract_payload_id(product, "id", "idProduto") or _extract_payload_id(item, "idProduto")
                service_raw_id = _extract_payload_id(service, "id", "idServico") or _extract_payload_id(item, "idServico")
                self._insert_row(
                    connection,
                    "olist_core.order_items",
                    {
                        "tenant_id": tenant_id,
                        "order_id": order_pk,
                        "line_number": index,
                        "product_id": product_map.get(product_raw_id or -1),
                        "service_id": service_map.get(service_raw_id or -1),
                        "olist_product_id": product_raw_id,
                        "product_name_snapshot": _extract(product, "descricao", "nome"),
                        "quantity": _normalize_decimal(_extract(item, "quantidade")) or Decimal("0"),
                        "unit_price": _normalize_decimal(_extract(item, "valorUnitario", "preco")) or Decimal("0"),
                        "additional_info": _extract(item, "infoAdicional"),
                        "raw_attributes": item,
                        "source_payload": item,
                    },
                )
                children += 1

            for marker in _marker_entries(payload):
                self._insert_row(
                    connection,
                    "olist_core.order_markers",
                    {
                        "tenant_id": tenant_id,
                        "order_id": order_pk,
                        "marker_description": _extract(marker, "descricao", "nome"),
                    },
                )
                children += 1

            payment = payload.get("pagamento") if isinstance(payload.get("pagamento"), dict) else {}
            for installment in payment.get("parcelas") or []:
                if not isinstance(installment, dict):
                    continue
                receipt_method = installment.get("formaRecebimento") if isinstance(installment.get("formaRecebimento"), dict) else {}
                payment_method = installment.get("formaPagamento") if isinstance(installment.get("formaPagamento"), dict) else {}
                self._insert_row(
                    connection,
                    "olist_core.order_installments",
                    {
                        "tenant_id": tenant_id,
                        "order_id": order_pk,
                        "installment_number": _extract(installment, "numero"),
                        "term_days": _extract(installment, "dias"),
                        "due_date": _normalize_date(_extract(installment, "data", "dataVencimento")),
                        "installment_amount": _normalize_decimal(_extract(installment, "valor")) or Decimal("0"),
                        "observations": _extract(installment, "observacoes"),
                        "receipt_method_id": receipt_method_map.get(_extract_payload_id(receipt_method, "id") or -1),
                        "payment_method_id": payment_method_map.get(_extract_payload_id(payment_method, "id") or -1),
                        "olist_receipt_method_id": _extract_payload_id(receipt_method, "id"),
                        "olist_payment_method_id": _extract_payload_id(payment_method, "id"),
                        "source_payload": installment,
                    },
                )
                children += 1

            for integrated_payment in payload.get("pagamentosIntegrados") or []:
                if not isinstance(integrated_payment, dict):
                    continue
                self._insert_row(
                    connection,
                    "olist_core.order_integrated_payments",
                    {
                        "tenant_id": tenant_id,
                        "order_id": order_pk,
                        "payment_type": _extract(integrated_payment, "tipo"),
                        "payment_amount": _normalize_decimal(_extract(integrated_payment, "valor")),
                        "intermediator_cnpj": _extract(integrated_payment, "cnpjIntermediador"),
                        "authorization_code": _extract(integrated_payment, "codigoAutorizacao"),
                        "flag_code": _extract(integrated_payment, "bandeira"),
                        "source_payload": integrated_payment,
                    },
                )
                children += 1

            transporter = payload.get("transportador") if isinstance(payload.get("transportador"), dict) else {}
            if transporter or payload.get("idFormaEnvio") or payload.get("idFormaFrete"):
                self._insert_row(
                    connection,
                    "olist_core.order_shipping",
                    {
                        "tenant_id": tenant_id,
                        "order_id": order_pk,
                        "carrier_contact_id": contact_map.get(_extract_payload_id(transporter, "id") or -1),
                        "carrier_address_id": None,
                        "freight_account_code": _extract(payload, "fretePorConta"),
                        "shipping_method_id": shipping_method_map.get(_extract_payload_id(payload, "idFormaEnvio") or -1),
                        "freight_method_id": freight_method_map.get(_extract_payload_id(payload, "idFormaFrete") or -1),
                        "olist_shipping_method_id": _extract_payload_id(payload, "idFormaEnvio"),
                        "olist_freight_method_id": _extract_payload_id(payload, "idFormaFrete"),
                        "tracking_code": _extract(payload, "codigoRastreamento"),
                        "tracking_url": _extract(payload, "urlRastreamento"),
                        "company_paid_freight": _normalize_decimal(_extract(payload, "valorFrete")),
                        "predicted_date": _normalize_date(_extract(payload, "dataPrevista")),
                        "volumes": _extract(payload, "qtdVolumes"),
                        "gross_weight": _normalize_decimal(_extract(payload, "pesoBruto")),
                        "net_weight": _normalize_decimal(_extract(payload, "pesoLiquido")),
                        "shipping_notes": _extract(payload, "observacoes"),
                        "source_payload": payload,
                    },
                )
                children += 1
        stats["orders"] = SyncEntityStats(processed=processed, children=children)

    def _sync_purchase_orders(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "purchase_orders"):
            return
        rows = self._fetch_rows(connection, tenant_id, "purchase_orders")
        if not rows:
            return
        contact_map = self._lookup_uuid_map(connection, "olist_core.contacts", "olist_contact_id", "contact_id", tenant_id)
        product_map = self._lookup_uuid_map(connection, "olist_core.products", "olist_product_id", "product_id", tenant_id)
        processed = 0
        children = 0
        for row in rows:
            payload = _row_payload(row)
            purchase_order_raw_id = _extract_payload_id(payload, "id")
            if purchase_order_raw_id is None:
                continue
            contact = payload.get("contato") if isinstance(payload.get("contato"), dict) else {}
            purchase_order_pk = self._upsert_row(
                connection,
                "olist_core.purchase_orders",
                {
                    "tenant_id": tenant_id,
                    "olist_purchase_order_id": purchase_order_raw_id,
                    "supplier_contact_id": contact_map.get(_extract_payload_id(contact, "id") or -1),
                    "order_number": _extract(payload, "numeroPedido"),
                    "status": _extract(payload, "situacao"),
                    "issue_date": _normalize_date(_extract(payload, "data")),
                    "expected_date": _normalize_date(_extract(payload, "dataPrevista")),
                    "total_amount": _normalize_decimal(_extract(payload, "totalPedidoCompra")),
                    "notes": _extract(payload, "observacoesInternas", "observacoes"),
                    "source_updated_at": row.get("source_updated_at"),
                    "raw_attributes": payload,
                    "source_payload": payload,
                },
                ["tenant_id", "olist_purchase_order_id"],
                "purchase_order_id",
            )
            processed += 1
            self._delete_children(connection, "olist_core.purchase_order_items", tenant_id, "purchase_order_id", purchase_order_pk)
            self._delete_children(connection, "olist_core.purchase_order_markers", tenant_id, "purchase_order_id", purchase_order_pk)
            for item in payload.get("itens") or []:
                if not isinstance(item, dict):
                    continue
                product = item.get("produto") if isinstance(item.get("produto"), dict) else {}
                self._insert_row(
                    connection,
                    "olist_core.purchase_order_items",
                    {
                        "tenant_id": tenant_id,
                        "purchase_order_id": purchase_order_pk,
                        "product_id": product_map.get(_extract_payload_id(product, "id") or -1),
                        "quantity": _normalize_decimal(_extract(item, "quantidade")),
                        "unit_price": _normalize_decimal(_extract(item, "preco")),
                        "total_amount": _normalize_decimal(_extract(item, "valorTotal")) or (_normalize_decimal(_extract(item, "preco")) or Decimal("0")) * (_normalize_decimal(_extract(item, "quantidade")) or Decimal("0")),
                        "source_payload": item,
                    },
                )
                children += 1
            for marker in _marker_entries(payload):
                self._insert_row(
                    connection,
                    "olist_core.purchase_order_markers",
                    {
                        "tenant_id": tenant_id,
                        "purchase_order_id": purchase_order_pk,
                        "marker_description": _extract(marker, "descricao", "nome"),
                    },
                )
                children += 1
        stats["purchase_orders"] = SyncEntityStats(processed=processed, children=children)

    def _sync_service_orders(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "service_orders"):
            return
        rows = self._fetch_rows(connection, tenant_id, "service_orders")
        if not rows:
            return
        contact_map = self._lookup_uuid_map(connection, "olist_core.contacts", "olist_contact_id", "contact_id", tenant_id)
        service_map = self._lookup_uuid_map(connection, "olist_core.services", "olist_service_id", "service_id", tenant_id)
        processed = 0
        children = 0
        for row in rows:
            payload = _row_payload(row)
            service_order_raw_id = _extract_payload_id(payload, "id")
            if service_order_raw_id is None:
                continue
            contact = payload.get("contato") if isinstance(payload.get("contato"), dict) else {}
            service_order_pk = self._upsert_row(
                connection,
                "olist_core.service_orders",
                {
                    "tenant_id": tenant_id,
                    "olist_service_order_id": service_order_raw_id,
                    "contact_id": contact_map.get(_extract_payload_id(contact, "id") or -1),
                    "order_number": _extract(payload, "numeroPedido"),
                    "status": _extract(payload, "situacao"),
                    "issue_date": _normalize_date(_extract(payload, "data")),
                    "expected_date": _normalize_date(_extract(payload, "dataPrevista")),
                    "total_amount": _normalize_decimal(_extract(payload, "totalPedido")),
                    "notes": _extract(payload, "observacoesInternas", "observacoes"),
                    "source_updated_at": row.get("source_updated_at"),
                    "raw_attributes": payload,
                    "source_payload": payload,
                },
                ["tenant_id", "olist_service_order_id"],
                "service_order_id",
            )
            processed += 1
            self._delete_children(connection, "olist_core.service_order_items", tenant_id, "service_order_id", service_order_pk)
            self._delete_children(connection, "olist_core.service_order_markers", tenant_id, "service_order_id", service_order_pk)
            for item in payload.get("itens") or []:
                if not isinstance(item, dict):
                    continue
                service = item.get("servico") if isinstance(item.get("servico"), dict) else {}
                self._insert_row(
                    connection,
                    "olist_core.service_order_items",
                    {
                        "tenant_id": tenant_id,
                        "service_order_id": service_order_pk,
                        "service_id": service_map.get(_extract_payload_id(service, "id") or -1),
                        "quantity": _normalize_decimal(_extract(item, "quantidade")),
                        "unit_price": _normalize_decimal(_extract(item, "preco", "valorUnitario")),
                        "total_amount": _normalize_decimal(_extract(item, "valorTotal")),
                        "source_payload": item,
                    },
                )
                children += 1
            for marker in _marker_entries(payload):
                self._insert_row(
                    connection,
                    "olist_core.service_order_markers",
                    {
                        "tenant_id": tenant_id,
                        "service_order_id": service_order_pk,
                        "marker_description": _extract(marker, "descricao", "nome"),
                    },
                )
                children += 1
        stats["service_orders"] = SyncEntityStats(processed=processed, children=children)

    def _sync_invoices(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "invoices"):
            return
        rows = self._fetch_rows(connection, tenant_id, "invoices")
        if not rows:
            return
        contact_map = self._lookup_uuid_map(connection, "olist_core.contacts", "olist_contact_id", "contact_id", tenant_id)
        order_map = self._lookup_uuid_map(connection, "olist_core.orders", "olist_order_id", "order_id", tenant_id)
        product_map = self._lookup_uuid_map(connection, "olist_core.products", "olist_product_id", "product_id", tenant_id)
        service_map = self._lookup_uuid_map(connection, "olist_core.services", "olist_service_id", "service_id", tenant_id)
        header_rows = [row for row in rows if len(_path_parts(str(row.get("endpoint_path")))) == 2]
        link_rows = {int(row["olist_object_id"]): row for row in rows if "/link" in str(row.get("endpoint_path")) and row.get("olist_object_id") is not None}
        xml_rows = {int(row["olist_object_id"]): row for row in rows if "/xml" in str(row.get("endpoint_path")) and row.get("olist_object_id") is not None}
        marker_rows_by_invoice: dict[int, list[dict[str, Any]]] = {}
        item_rows_by_invoice: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            endpoint = str(row.get("endpoint_path") or "")
            parts = _path_parts(endpoint)
            if len(parts) >= 4 and parts[0] == "notas" and parts[2] == "itens":
                invoice_id = int(parts[1])
                item_rows_by_invoice.setdefault(invoice_id, []).append(row)
            if endpoint.endswith("/marcadores") and parts and parts[0] == "notas":
                invoice_id = int(parts[1])
                marker_rows_by_invoice.setdefault(invoice_id, []).append(row)

        processed = 0
        children = 0
        for row in header_rows:
            payload = _row_payload(row)
            invoice_raw_id = _extract_payload_id(payload, "id", "idNota")
            if invoice_raw_id is None:
                continue
            customer = payload.get("cliente") if isinstance(payload.get("cliente"), dict) else {}
            invoice_pk = self._upsert_row(
                connection,
                "olist_core.invoices",
                {
                    "tenant_id": tenant_id,
                    "olist_invoice_id": invoice_raw_id,
                    "order_id": order_map.get(_extract_payload_id(payload, "idPedido") or -1),
                    "contact_id": contact_map.get(_extract_payload_id(customer, "id") or -1),
                    "invoice_number": _extract(payload, "numero"),
                    "invoice_series": _extract(payload, "serie"),
                    "invoice_status": _extract(payload, "situacao"),
                    "invoice_type": _extract(payload, "tipo"),
                    "access_key": _extract(payload, "chaveAcesso"),
                    "issued_at": _normalize_datetime(_extract(payload, "dataEmissao")),
                    "authorized_at": _normalize_datetime(_extract(payload, "dataAutorizacao")),
                    "cancelled_at": _normalize_datetime(_extract(payload, "dataCancelamento")),
                    "tracking_code": _extract(payload, "codigoRastreamento"),
                    "tracking_url": _extract(_row_payload(link_rows.get(invoice_raw_id, {})), "url") or _extract(payload, "urlRastreamento"),
                    "xml_url": _extract(_row_payload(xml_rows.get(invoice_raw_id, {})), "url"),
                    "danfe_url": _extract(_row_payload(link_rows.get(invoice_raw_id, {})), "danfe", "urlDanfe"),
                    "total_amount": _normalize_decimal(_extract(payload, "valor", "valorFaturado")),
                    "source_updated_at": row.get("source_updated_at"),
                    "raw_attributes": payload,
                    "source_payload": payload,
                },
                ["tenant_id", "olist_invoice_id"],
                "invoice_id",
            )
            processed += 1

            self._delete_children(connection, "olist_core.invoice_items", tenant_id, "invoice_id", invoice_pk)
            self._delete_children(connection, "olist_core.invoice_markers", tenant_id, "invoice_id", invoice_pk)

            merged_items: list[dict[str, Any]] = []
            detail_items = _latest_rows_by_key(item_rows_by_invoice.get(invoice_raw_id, []), lambda current: _extract_payload_id(_row_payload(current), "id", "idItem"))
            if detail_items:
                merged_items.extend(_row_payload(current) for current in detail_items)
            else:
                merged_items.extend(item for item in payload.get("itens") or [] if isinstance(item, dict))

            for item in merged_items:
                product_raw_id = _extract_payload_id(item, "idProduto")
                service_raw_id = _extract_payload_id(item, "idServico")
                self._insert_row(
                    connection,
                    "olist_core.invoice_items",
                    {
                        "tenant_id": tenant_id,
                        "invoice_id": invoice_pk,
                        "order_item_id": None,
                        "product_id": product_map.get(product_raw_id or -1),
                        "service_id": service_map.get(service_raw_id or -1),
                        "quantity": _normalize_decimal(_extract(item, "quantidade")),
                        "unit_price": _normalize_decimal(_extract(item, "valorUnitario")),
                        "total_amount": _normalize_decimal(_extract(item, "valorTotal")),
                        "tax_attributes": {
                            "cfop": _extract(item, "cfop"),
                            "ncm": _extract(item, "ncm"),
                            "origem": _extract(item, "origem"),
                            "ipi": item.get("ipi"),
                            "icms": item.get("icms"),
                            "pis": item.get("pis"),
                            "cofins": item.get("cofins"),
                            "simples": item.get("simples"),
                        },
                        "source_payload": item,
                    },
                )
                children += 1

            for marker_row in marker_rows_by_invoice.get(invoice_raw_id, []):
                marker_payload = _row_payload(marker_row)
                for marker in marker_payload.get("itens") or marker_payload.get("marcadores") or []:
                    if not isinstance(marker, dict):
                        continue
                    description = _extract(marker, "descricao", "nome")
                    if description is None:
                        continue
                    self._insert_row(
                        connection,
                        "olist_core.invoice_markers",
                        {
                            "tenant_id": tenant_id,
                            "invoice_id": invoice_pk,
                            "marker_description": description,
                        },
                    )
                    children += 1
            existing_marker_descriptions = {
                _extract(marker, "descricao", "nome")
                for marker_row in marker_rows_by_invoice.get(invoice_raw_id, [])
                for marker in ((_row_payload(marker_row).get("itens") or _row_payload(marker_row).get("marcadores") or []))
                if isinstance(marker, dict) and _extract(marker, "descricao", "nome") is not None
            }
            for marker in _marker_entries(payload):
                description = _extract(marker, "descricao", "nome")
                if description in existing_marker_descriptions:
                    continue
                self._insert_row(
                    connection,
                    "olist_core.invoice_markers",
                    {
                        "tenant_id": tenant_id,
                        "invoice_id": invoice_pk,
                        "marker_description": description,
                    },
                )
                children += 1
        stats["invoices"] = SyncEntityStats(processed=processed, children=children)

    def _sync_accounts_receivable(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "accounts_receivable"):
            return
        rows = self._fetch_rows(connection, tenant_id, "accounts_receivable")
        if not rows:
            return
        contact_map = self._lookup_uuid_map(connection, "olist_core.contacts", "olist_contact_id", "contact_id", tenant_id)
        category_map = self._lookup_uuid_map(connection, "olist_core.revenue_expense_categories", "olist_fin_category_id", "category_fin_id", tenant_id)
        invoice_map = self._lookup_uuid_map(connection, "olist_core.invoices", "olist_invoice_id", "invoice_id", tenant_id)
        order_map = self._lookup_uuid_map(connection, "olist_core.orders", "olist_order_id", "order_id", tenant_id)
        receipt_method_map = self._lookup_uuid_map(connection, "olist_core.receipt_methods", "olist_receipt_method_id", "receipt_method_id", tenant_id)
        payment_method_map = self._lookup_uuid_map(connection, "olist_core.payment_methods", "olist_payment_method_id", "payment_method_id", tenant_id)
        header_rows = [row for row in rows if len(_path_parts(str(row.get("endpoint_path")))) == 2]
        receipt_rows_by_account: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            parts = _path_parts(str(row.get("endpoint_path") or ""))
            if len(parts) >= 3 and parts[0] == "contas-receber" and parts[2] == "recebimentos":
                receipt_rows_by_account.setdefault(int(parts[1]), []).append(row)

        processed = 0
        children = 0
        for row in header_rows:
            payload = _row_payload(row)
            ar_raw_id = _extract_payload_id(payload, "id")
            if ar_raw_id is None:
                continue
            customer = payload.get("cliente") if isinstance(payload.get("cliente"), dict) else {}
            category = payload.get("categoria") if isinstance(payload.get("categoria"), dict) else {}
            ar_pk = self._upsert_row(
                connection,
                "olist_core.accounts_receivable",
                {
                    "tenant_id": tenant_id,
                    "olist_ar_id": ar_raw_id,
                    "order_id": order_map.get(_extract_payload_id(payload, "idPedido") or -1),
                    "invoice_id": invoice_map.get(_extract_payload_id(payload, "idNotaFiscal") or -1),
                    "contact_id": contact_map.get(_extract_payload_id(customer, "id") or -1),
                    "revenue_category_id": category_map.get(_extract_payload_id(category, "id") or -1),
                    "document_number": _extract(payload, "numeroDocumento"),
                    "status": _extract(payload, "situacao"),
                    "issue_date": _normalize_date(_extract(payload, "data")),
                    "due_date": _normalize_date(_extract(payload, "dataVencimento")),
                    "competence_date": _normalize_date(_extract(payload, "dataCompetencia")),
                    "amount": _normalize_decimal(_extract(payload, "valor")),
                    "open_amount": _normalize_decimal(_extract(payload, "saldo")),
                    "notes": _extract(payload, "historico"),
                    "source_updated_at": row.get("source_updated_at"),
                    "raw_attributes": payload,
                    "source_payload": payload,
                },
                ["tenant_id", "olist_ar_id"],
                "ar_id",
            )
            processed += 1
            self._delete_children(connection, "olist_core.accounts_receivable_receipts", tenant_id, "ar_id", ar_pk)
            self._delete_children(connection, "olist_core.accounts_receivable_markers", tenant_id, "ar_id", ar_pk)

            for receipt_row in _latest_rows_by_key(receipt_rows_by_account.get(ar_raw_id, []), lambda current: _extract_payload_id(_row_payload(current), "id")):
                receipt_payload = _row_payload(receipt_row)
                self._insert_row(
                    connection,
                    "olist_core.accounts_receivable_receipts",
                    {
                        "tenant_id": tenant_id,
                        "ar_id": ar_pk,
                        "receipt_date": _normalize_date(_extract(receipt_payload, "data")),
                        "receipt_amount": _normalize_decimal(_extract(receipt_payload, "valorPago")),
                        "receipt_method_id": receipt_method_map.get(_extract_payload_id(receipt_payload, "idFormaRecebimento") or -1),
                        "payment_method_id": payment_method_map.get(_extract_payload_id(receipt_payload, "idFormaPagamento") or -1),
                        "source_payload": receipt_payload,
                    },
                )
                children += 1
            for marker in _marker_entries(payload):
                self._insert_row(
                    connection,
                    "olist_core.accounts_receivable_markers",
                    {
                        "tenant_id": tenant_id,
                        "ar_id": ar_pk,
                        "marker_description": _extract(marker, "descricao", "nome"),
                    },
                )
                children += 1
        stats["accounts_receivable"] = SyncEntityStats(processed=processed, children=children)

    def _sync_accounts_payable(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "accounts_payable"):
            return
        rows = self._fetch_rows(connection, tenant_id, "accounts_payable")
        if not rows:
            return
        contact_map = self._lookup_uuid_map(connection, "olist_core.contacts", "olist_contact_id", "contact_id", tenant_id)
        category_map = self._lookup_uuid_map(connection, "olist_core.revenue_expense_categories", "olist_fin_category_id", "category_fin_id", tenant_id)
        header_rows = [row for row in rows if len(_path_parts(str(row.get("endpoint_path")))) == 2]
        receipt_rows_by_account: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            parts = _path_parts(str(row.get("endpoint_path") or ""))
            if len(parts) >= 3 and parts[0] == "contas-pagar" and parts[2] == "recebimentos":
                receipt_rows_by_account.setdefault(int(parts[1]), []).append(row)

        processed = 0
        children = 0
        for row in header_rows:
            payload = _row_payload(row)
            ap_raw_id = _extract_payload_id(payload, "id")
            if ap_raw_id is None:
                continue
            contact = payload.get("contato") if isinstance(payload.get("contato"), dict) else {}
            category = payload.get("categoria") if isinstance(payload.get("categoria"), dict) else {}
            ap_pk = self._upsert_row(
                connection,
                "olist_core.accounts_payable",
                {
                    "tenant_id": tenant_id,
                    "olist_ap_id": ap_raw_id,
                    "purchase_order_id": None,
                    "contact_id": contact_map.get(_extract_payload_id(contact, "id") or -1),
                    "expense_category_id": category_map.get(_extract_payload_id(category, "id") or -1),
                    "document_number": _extract(payload, "numeroDocumento"),
                    "status": _extract(payload, "situacao"),
                    "issue_date": _normalize_date(_extract(payload, "data")),
                    "due_date": _normalize_date(_extract(payload, "dataVencimento")),
                    "competence_date": _normalize_date(_extract(payload, "dataCompetencia")),
                    "amount": _normalize_decimal(_extract(payload, "valor")),
                    "open_amount": _normalize_decimal(_extract(payload, "saldo")),
                    "notes": _extract(payload, "historico"),
                    "source_updated_at": row.get("source_updated_at"),
                    "raw_attributes": payload,
                    "source_payload": payload,
                },
                ["tenant_id", "olist_ap_id"],
                "ap_id",
            )
            processed += 1
            self._delete_children(connection, "olist_core.accounts_payable_receipts", tenant_id, "ap_id", ap_pk)
            self._delete_children(connection, "olist_core.accounts_payable_markers", tenant_id, "ap_id", ap_pk)

            for receipt_row in _latest_rows_by_key(receipt_rows_by_account.get(ap_raw_id, []), lambda current: _extract_payload_id(_row_payload(current), "id")):
                receipt_payload = _row_payload(receipt_row)
                self._insert_row(
                    connection,
                    "olist_core.accounts_payable_receipts",
                    {
                        "tenant_id": tenant_id,
                        "ap_id": ap_pk,
                        "payment_date": _normalize_date(_extract(receipt_payload, "data")),
                        "payment_amount": _normalize_decimal(_extract(receipt_payload, "valorPago")),
                        "source_payload": receipt_payload,
                    },
                )
                children += 1

            for marker in _marker_entries(payload):
                self._insert_row(
                    connection,
                    "olist_core.accounts_payable_markers",
                    {
                        "tenant_id": tenant_id,
                        "ap_id": ap_pk,
                        "marker_description": _extract(marker, "descricao", "nome"),
                    },
                )
                children += 1
        stats["accounts_payable"] = SyncEntityStats(processed=processed, children=children)

    def _sync_shipments(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "shipments"):
            return
        rows = self._fetch_rows(connection, tenant_id, "shipments")
        if not rows:
            return
        order_map = self._lookup_uuid_map(connection, "olist_core.orders", "olist_order_id", "order_id", tenant_id)
        shipping_method_map = self._lookup_uuid_map(connection, "olist_core.shipping_methods", "olist_shipping_method_id", "shipping_method_id", tenant_id)
        freight_method_map = self._lookup_uuid_map(connection, "olist_core.freight_methods", "olist_freight_method_id", "freight_method_id", tenant_id)
        processed = 0
        for row in rows:
            payload = _row_payload(row)
            shipment_raw_id = _extract_payload_id(payload, "id")
            if shipment_raw_id is None:
                continue
            group = payload.get("grupo") if isinstance(payload.get("grupo"), dict) else {}
            group_raw_id = _extract_payload_id(group, "id")
            group_pk = None
            if group_raw_id is not None:
                group_pk = self._upsert_row(
                    connection,
                    "olist_core.shipment_groups",
                    {
                        "tenant_id": tenant_id,
                        "olist_shipment_group_id": group_raw_id,
                        "group_name": _extract(group, "nome", "descricao"),
                        "status": _extract(group, "situacao", "status"),
                        "concluded_at": _normalize_datetime(_extract(group, "dataConclusao")),
                        "source_payload": group,
                    },
                    ["tenant_id", "olist_shipment_group_id"],
                    "shipment_group_id",
                )
            self._upsert_row(
                connection,
                "olist_core.shipments",
                {
                    "tenant_id": tenant_id,
                    "olist_shipment_id": shipment_raw_id,
                    "shipment_group_id": group_pk,
                    "order_id": order_map.get(_extract_payload_id(payload, "idPedido") or -1),
                    "status": _extract(payload, "situacao", "status"),
                    "shipping_method_id": shipping_method_map.get(_extract_payload_id(payload, "idFormaEnvio") or -1),
                    "freight_method_id": freight_method_map.get(_extract_payload_id(payload, "idFormaFrete") or -1),
                    "tracking_code": _extract(payload, "codigoRastreamento"),
                    "tracking_url": _extract(payload, "urlRastreamento"),
                    "shipped_at": _normalize_datetime(_extract(payload, "dataEnvio")),
                    "delivered_at": _normalize_datetime(_extract(payload, "dataEntrega")),
                    "source_payload": payload,
                },
                ["tenant_id", "olist_shipment_id"],
                "shipment_id",
            )
            processed += 1
        stats["shipments"] = SyncEntityStats(processed=processed)

    def _sync_separations(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "separations"):
            return
        rows = self._fetch_rows(connection, tenant_id, "separations")
        if not rows:
            return
        order_map = self._lookup_uuid_map(connection, "olist_core.orders", "olist_order_id", "order_id", tenant_id)
        product_map = self._lookup_uuid_map(connection, "olist_core.products", "olist_product_id", "product_id", tenant_id)
        user_map = self._lookup_uuid_map(connection, "olist_core.olist_users", "olist_user_id", "olist_user_pk", tenant_id)
        freight_method_map = self._lookup_uuid_map(connection, "olist_core.freight_methods", "olist_freight_method_id", "freight_method_id", tenant_id)
        processed = 0
        children = 0
        for row in rows:
            payload = _row_payload(row)
            separation_raw_id = _extract_payload_id(payload, "id")
            if separation_raw_id is None:
                continue
            separation_pk = self._upsert_row(
                connection,
                "olist_core.separations",
                {
                    "tenant_id": tenant_id,
                    "olist_separation_id": separation_raw_id,
                    "order_id": order_map.get(_extract_payload_id(payload, "idPedido") or -1),
                    "document_number": _extract(payload, "numeroDocumento"),
                    "status": _extract(payload, "situacao", "status"),
                    "origin_type": _extract(payload, "tipoOrigem"),
                    "issued_at": _normalize_datetime(_extract(payload, "data", "dataEmissao")),
                    "packed_by_olist_user_id": _extract_payload_id(payload, "idUsuario", "idUsuarioSeparou"),
                    "packed_by_user_id": user_map.get(_extract_payload_id(payload, "idUsuario", "idUsuarioSeparou") or -1),
                    "freight_method_id": freight_method_map.get(_extract_payload_id(payload, "idFormaFrete") or -1),
                    "source_payload": payload,
                },
                ["tenant_id", "olist_separation_id"],
                "separation_id",
            )
            processed += 1
            self._delete_children(connection, "olist_core.separation_items", tenant_id, "separation_id", separation_pk)
            for item in payload.get("itens") or []:
                if not isinstance(item, dict):
                    continue
                product = item.get("produto") if isinstance(item.get("produto"), dict) else {}
                self._insert_row(
                    connection,
                    "olist_core.separation_items",
                    {
                        "tenant_id": tenant_id,
                        "separation_id": separation_pk,
                        "order_item_id": None,
                        "product_id": product_map.get(_extract_payload_id(product, "id") or -1),
                        "quantity": _normalize_decimal(_extract(item, "quantidade")),
                        "status": _extract(item, "situacao", "status"),
                        "source_payload": item,
                    },
                )
                children += 1
        stats["separations"] = SyncEntityStats(processed=processed, children=children)

    def _sync_crm_stages(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "crm_stages"):
            return
        rows = self._fetch_rows(connection, tenant_id, "crm_stages")
        if not rows:
            return
        processed = 0
        for row in rows:
            payload = _row_payload(row)
            stage_raw_id = _extract_payload_id(payload, "id")
            if stage_raw_id is None:
                continue
            self._upsert_row(
                connection,
                "olist_core.crm_stages",
                {
                    "tenant_id": tenant_id,
                    "olist_crm_stage_id": stage_raw_id,
                    "stage_name": _extract(payload, "descricao", "nome"),
                    "pipeline_position": _extract(payload, "ordem"),
                    "is_active": True,
                    "source_payload": payload,
                },
                ["tenant_id", "olist_crm_stage_id"],
                "crm_stage_id",
            )
            processed += 1
        stats["crm_stages"] = SyncEntityStats(processed=processed)

    def _sync_crm_subjects(self, connection: Any, tenant_id: str, stats: dict[str, SyncEntityStats], requested: set[str]) -> None:
        if not self._should_sync(requested, "crm_subjects"):
            return
        rows = self._fetch_rows(connection, tenant_id, "crm_subjects")
        if not rows:
            return
        contact_map = self._lookup_uuid_map(connection, "olist_core.contacts", "olist_contact_id", "contact_id", tenant_id)
        stage_map = self._lookup_uuid_map(connection, "olist_core.crm_stages", "olist_crm_stage_id", "crm_stage_id", tenant_id)
        header_rows = [row for row in rows if len(_path_parts(str(row.get("endpoint_path")))) == 3]
        action_rows_by_subject: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            parts = _path_parts(str(row.get("endpoint_path") or ""))
            if len(parts) >= 4 and parts[:3] == ["crm", "assuntos", parts[2]] and parts[3] == "acoes":
                subject_id = int(parts[2])
                action_rows_by_subject.setdefault(subject_id, []).append(row)

        processed = 0
        children = 0
        for row in header_rows:
            payload = _row_payload(row)
            subject_raw_id = _extract_payload_id(payload, "id")
            if subject_raw_id is None:
                continue
            customer = payload.get("cliente") if isinstance(payload.get("cliente"), dict) else {}
            stage = payload.get("estagio") if isinstance(payload.get("estagio"), dict) else {}
            subject_pk = self._upsert_row(
                connection,
                "olist_core.crm_subjects",
                {
                    "tenant_id": tenant_id,
                    "olist_subject_id": subject_raw_id,
                    "contact_id": contact_map.get(_extract_payload_id(customer, "id") or -1),
                    "crm_stage_id": stage_map.get(_extract_payload_id(stage, "id") or -1),
                    "subject_title": _extract(payload, "assunto"),
                    "subject_status": _extract(payload, "situacao", "status"),
                    "is_archived": bool(_normalize_bool(_extract(payload, "arquivado")) or False),
                    "is_starred": bool(_normalize_bool(_extract(payload, "estrela")) or False),
                    "source_updated_at": _normalize_datetime(_extract(payload, "dataAtualizacao")) or row.get("source_updated_at"),
                    "raw_attributes": payload,
                    "source_payload": payload,
                },
                ["tenant_id", "olist_subject_id"],
                "crm_subject_id",
            )
            processed += 1
            self._delete_children(connection, "olist_core.crm_actions", tenant_id, "crm_subject_id", subject_pk)
            self._delete_children(connection, "olist_core.crm_notes", tenant_id, "crm_subject_id", subject_pk)
            self._delete_children(connection, "olist_core.crm_subject_markers", tenant_id, "crm_subject_id", subject_pk)

            recent_actions = payload.get("acoesRecentes") if isinstance(payload.get("acoesRecentes"), dict) else {}
            recent_notes = payload.get("anotacoesRecentes") if isinstance(payload.get("anotacoesRecentes"), dict) else {}
            merged_actions = list(recent_actions.get("itens") or [])
            detail_actions = _latest_rows_by_key(action_rows_by_subject.get(subject_raw_id, []), lambda current: _extract_payload_id(_row_payload(current), "id"))
            if detail_actions:
                detail_ids = {_extract_payload_id(_row_payload(detail_row), "id") for detail_row in detail_actions}
                merged_actions = [action for action in merged_actions if _extract_payload_id(action, "id") not in detail_ids]
                merged_actions.extend(_row_payload(detail_row) for detail_row in detail_actions)

            for action in merged_actions:
                if not isinstance(action, dict):
                    continue
                self._insert_row(
                    connection,
                    "olist_core.crm_actions",
                    {
                        "tenant_id": tenant_id,
                        "crm_subject_id": subject_pk,
                        "olist_action_id": _extract_payload_id(action, "id"),
                        "action_type": _extract(action, "tipoData"),
                        "action_status": "success" if _normalize_bool(_extract(action, "acaoConcluida")) else "pending",
                        "scheduled_at": _normalize_datetime(_extract(action, "data")),
                        "completed_at": _normalize_datetime(_extract(action, "dataConcluida")),
                        "source_payload": action,
                    },
                )
                children += 1

            for note in recent_notes.get("itens") or []:
                if not isinstance(note, dict):
                    continue
                self._insert_row(
                    connection,
                    "olist_core.crm_notes",
                    {
                        "tenant_id": tenant_id,
                        "crm_subject_id": subject_pk,
                        "olist_note_id": _extract_payload_id(note, "id"),
                        "note_body": _extract(note, "descricao", "texto"),
                        "source_payload": note,
                    },
                )
                children += 1
            for marker in _marker_entries(payload):
                marker_pk = self._upsert_row(
                    connection,
                    "olist_core.crm_markers",
                    {
                        "tenant_id": tenant_id,
                        "marker_description": _extract(marker, "descricao", "nome"),
                        "color_hex": _extract(marker, "cor", "corHex", "color"),
                        "source_payload": marker,
                    },
                    ["tenant_id", "marker_description"],
                    "crm_marker_id",
                )
                self._insert_row(
                    connection,
                    "olist_core.crm_subject_markers",
                    {
                        "tenant_id": tenant_id,
                        "crm_subject_id": subject_pk,
                        "crm_marker_id": marker_pk,
                    },
                )
                children += 1
        stats["crm_subjects"] = SyncEntityStats(processed=processed, children=children)
