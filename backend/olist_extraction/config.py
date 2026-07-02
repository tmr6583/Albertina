from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PACKAGE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PACKAGE_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
ENV_PATH = BACKEND_DIR / ".env"

load_dotenv(ENV_PATH)


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _as_int(name: str, default: int) -> int:
    raw_value = _get_env(name, str(default))
    try:
        return int(raw_value)
    except ValueError:
        return default


def _as_float(name: str, default: float) -> float:
    raw_value = _get_env(name, str(default))
    try:
        return float(raw_value)
    except ValueError:
        return default


@dataclass(frozen=True)
class ExtractionSettings:
    database_url: str
    api_base_url: str
    timeout_seconds: int
    request_retries: int
    backoff_seconds: float
    page_limit: int
    safety_sleep_seconds: float
    default_tenant_code: str
    default_tenant_name: str
    products_stock_cooldown_hours: int
    execution_lease_seconds: int
    stop_poll_seconds: float
    log_directory: Path
    log_file_path: Path


def build_settings() -> ExtractionSettings:
    database_url = _get_env("ALBERTINA_DATABASE_URL") or _get_env("DATABASE_URL")
    log_directory = BACKEND_DIR / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    return ExtractionSettings(
        database_url=database_url,
        api_base_url=_get_env("OLIST_API_BASE_URL", "https://api.tiny.com.br/public-api/v3/").rstrip("/") + "/",
        timeout_seconds=_as_int("OLIST_EXTRACT_TIMEOUT_SECONDS", 30),
        request_retries=_as_int("OLIST_EXTRACT_RETRIES", 4),
        backoff_seconds=_as_float("OLIST_EXTRACT_BACKOFF_SECONDS", 2.0),
        page_limit=_as_int("OLIST_EXTRACT_PAGE_LIMIT", 100),
        safety_sleep_seconds=_as_float("OLIST_EXTRACT_SAFETY_SLEEP_SECONDS", 0.15),
        default_tenant_code=_get_env("OLIST_DEFAULT_TENANT_CODE", "default"),
        default_tenant_name=_get_env("OLIST_DEFAULT_TENANT_NAME", "Tenant Padrao Olist"),
        products_stock_cooldown_hours=_as_int("OLIST_PRODUCTS_STOCK_COOLDOWN_HOURS", 24),
        execution_lease_seconds=_as_int("OLIST_EXECUTION_LEASE_SECONDS", 180),
        stop_poll_seconds=_as_float("OLIST_STOP_POLL_SECONDS", 2.0),
        log_directory=log_directory,
        log_file_path=log_directory / "olist_extraction.log",
    )
