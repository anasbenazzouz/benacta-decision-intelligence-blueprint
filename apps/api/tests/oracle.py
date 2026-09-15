"""Test-only access to the hand-written oracle. Application code must never import this module."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import yaml

from app.config import REPO_ROOT

ORACLE_PATH = REPO_ROOT / "data" / "golden" / "oracle_v1.yml"
PROJECTS_ORACLE_PATH = REPO_ROOT / "data" / "golden" / "projects_oracle_v1.yml"


def load_oracle() -> dict[str, Any]:
    return yaml.safe_load(ORACLE_PATH.read_text(encoding="utf-8"))


def load_projects_oracle() -> dict[str, Any]:
    return yaml.safe_load(PROJECTS_ORACLE_PATH.read_text(encoding="utf-8"))


def case(oracle: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(c for c in oracle["cases"] if c["case_id"] == case_id)


def dec(value: Any) -> Decimal:
    return Decimal(str(value))
