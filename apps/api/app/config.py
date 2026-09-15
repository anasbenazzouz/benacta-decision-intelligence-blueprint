"""Runtime configuration with explicitly separated connections.

Five connections never share a variable, so an Odoo database can never be
mistaken for the BENACTA analytics database:

1. ODOO_READ_DSN            direct PostgreSQL read access (not available on Odoo Online)
2. ODOO_URL / ODOO_DB / ... business access through the Odoo external API
3. ANALYTICS_DATABASE_URL   BENACTA-owned database, the only migration target
4. NEO4J_*                  rebuildable ontology projection, never financial truth
5. LLM_* / EMBEDDING_MODEL  server-side only

Secrets are SecretStr and are never rendered by `describe()`.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Mode(StrEnum):
    FIXTURE = "fixture"
    ODOO_SANDBOX = "odoo_sandbox"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    benacta_mode: Mode = Mode.FIXTURE

    # 1. Direct read access to the Odoo PostgreSQL database, only where it exists and is authorised.
    odoo_read_dsn: SecretStr | None = None

    # 2. Odoo external API (JSON-2 on Odoo 19).
    odoo_url: str | None = None
    odoo_db: str | None = None
    odoo_username: str | None = None
    odoo_api_key: SecretStr | None = None
    odoo_source_instance: str = "benacta_odoo_online"
    odoo_timeout_seconds: float = 60.0

    # Write-back safety. Every check must pass before any Odoo write.
    odoo_writes_enabled: bool = False
    odoo_sandbox_allowlist: Annotated[list[str], NoDecode] = Field(default_factory=list)
    odoo_sandbox_company: str | None = None
    odoo_protected_companies: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["Benacta"])
    odoo_backup_attested_at: str | None = None
    odoo_backup_reference: str | None = None
    odoo_backup_max_age_days: int = 7

    # 3. BENACTA analytics database.
    analytics_database_url: SecretStr | None = None
    analytics_db_expected_name: str = "benacta_analytics"

    # 4. Ontology projection.
    neo4j_uri: str | None = None
    neo4j_username: str | None = None
    neo4j_password: SecretStr | None = None

    # 5. Language models.
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: SecretStr | None = None
    embedding_model: str | None = None

    @field_validator("benacta_mode", mode="before")
    @classmethod
    def _reject_production(cls, value: object) -> object:
        if str(value).strip().lower() in {"production", "prod"}:
            raise ValueError("production mode is not supported by this delivery")
        return value

    @field_validator("odoo_sandbox_allowlist", "odoo_protected_companies", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def odoo_api_configured(self) -> bool:
        return all([self.odoo_url, self.odoo_db, self.odoo_username, self.odoo_api_key])

    @property
    def odoo_target(self) -> str | None:
        """`host/db` identity used by the sandbox allowlist."""
        if not (self.odoo_url and self.odoo_db):
            return None
        return f"{urlsplit(self.odoo_url).hostname}/{self.odoo_db}"

    def describe(self) -> dict[str, str]:
        """Configuration presence only. Never values of secrets."""

        def state(*values: object) -> str:
            present = [v is not None and v != "" for v in values]
            if all(present):
                return "CONFIGURED"
            return "PARTIAL" if any(present) else "NOT_CONFIGURED"

        return {
            "mode": self.benacta_mode.value,
            "odoo_read_dsn": state(self.odoo_read_dsn),
            "odoo_api": state(self.odoo_url, self.odoo_db, self.odoo_username, self.odoo_api_key),
            "odoo_writes_enabled": str(self.odoo_writes_enabled).lower(),
            "analytics_database": state(self.analytics_database_url),
            "neo4j": state(self.neo4j_uri, self.neo4j_username, self.neo4j_password),
            "llm": state(self.llm_provider, self.llm_model, self.llm_api_key),
            "embedding_model": state(self.embedding_model),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
