from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable


LIST_CONTAINER_KEYS = ("itens", "items", "data", "resultados", "categorias", "expedicoes", "depositos")


def parse_olist_datetime(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)

    text = str(value).strip()
    patterns = (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    )
    for pattern in patterns:
        try:
            parsed = datetime.strptime(text, pattern)
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def format_incremental_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def format_incremental_datetime_br(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M:%S")


def format_incremental_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d")


def payload_hash(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def extract_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return [payload]
    for key in LIST_CONTAINER_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return [payload]


def walk_scalars(payload: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from walk_scalars(value)
        return
    if isinstance(payload, list):
        for item in payload:
            yield from walk_scalars(item)


def extract_first_value(context: dict[str, Any], candidate_keys: tuple[str, ...]) -> Any:
    if not candidate_keys:
        return None

    for key in candidate_keys:
        if key in context and context[key] not in {None, ""}:
            return context[key]

    path_params = context.get("path_params") or {}
    for key in candidate_keys:
        if key in path_params:
            return path_params[key]

    payload = context.get("payload")
    if isinstance(payload, dict):
        for key in candidate_keys:
            if key in payload and payload[key] not in {None, ""}:
                return payload[key]

    for key, value in walk_scalars(payload):
        if key in candidate_keys and value not in {None, ""}:
            return value
    return None


def extract_nested_objects(payload: Any, candidate_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for key in candidate_keys:
            nested = payload.get(key)
            if isinstance(nested, list):
                collected.extend(item for item in nested if isinstance(item, dict))
        for value in payload.values():
            collected.extend(extract_nested_objects(value, candidate_keys))
    elif isinstance(payload, list):
        for item in payload:
            collected.extend(extract_nested_objects(item, candidate_keys))
    return collected


def build_external_key(
    *,
    endpoint_path: str,
    path_params: dict[str, Any],
    payload: Any,
    object_id: Any,
    fallback_index: int | None = None,
) -> str:
    if object_id not in {None, ""}:
        return f"{endpoint_path}|{object_id}"

    normalized_params = ",".join(f"{key}={value}" for key, value in sorted(path_params.items()))
    payload_digest = payload_hash(payload)
    suffix = f"|{fallback_index}" if fallback_index is not None else ""
    return f"{endpoint_path}|{normalized_params}|{payload_digest}{suffix}"
