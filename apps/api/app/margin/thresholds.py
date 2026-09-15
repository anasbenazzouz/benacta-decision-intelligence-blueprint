"""Rule thresholds, loaded from a versioned configuration file and stamped on every evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from app.config import REPO_ROOT

THRESHOLDS_PATH = REPO_ROOT / "data" / "policies" / "margin_thresholds.yml"


@dataclass(frozen=True)
class Thresholds:
    threshold_set: str
    version: int
    currency: str
    materiality_min_exposure: Decimal
    severity_high: Decimal
    severity_medium: Decimal
    price_tolerance_pct: Decimal
    cost_tolerance_abs: Decimal
    cost_tolerance_pct: Decimal
    historical_months: int
    historical_min_observations: int
    historical_max_dispersion_pct: Decimal
    gm_pct_deterioration_points: Decimal
    freight_product_codes: frozenset[str]

    @property
    def stamp(self) -> str:
        return f"{self.threshold_set}/v{self.version}"

    def severity(self, amount: Decimal | None) -> str:
        if amount is None or amount <= 0:
            return "NONE"
        if amount >= self.severity_high:
            return "HIGH"
        if amount >= self.severity_medium:
            return "MEDIUM"
        return "LOW"

    def is_material(self, amount: Decimal | None) -> bool:
        return amount is not None and amount >= self.materiality_min_exposure

    def as_dict(self) -> dict[str, Any]:
        return {
            "threshold_set": self.threshold_set,
            "version": self.version,
            "currency": self.currency,
            "materiality_min_exposure": str(self.materiality_min_exposure),
            "severity": {"HIGH": str(self.severity_high), "MEDIUM": str(self.severity_medium)},
            "price_tolerance_pct": str(self.price_tolerance_pct),
            "cost_tolerance_abs": str(self.cost_tolerance_abs),
            "cost_tolerance_pct": str(self.cost_tolerance_pct),
            "historical_baseline": {"months": self.historical_months, "min_observations": self.historical_min_observations,
                                    "max_dispersion_pct": str(self.historical_max_dispersion_pct)},
            "gm_pct_deterioration_points": str(self.gm_pct_deterioration_points),
            "freight_product_codes": sorted(self.freight_product_codes),
        }


def load_thresholds(path: Path = THRESHOLDS_PATH) -> Thresholds:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Thresholds(
        threshold_set=str(raw["threshold_set"]),
        version=int(raw["version"]),
        currency=str(raw["currency"]),
        materiality_min_exposure=Decimal(str(raw["materiality_min_exposure"])),
        severity_high=Decimal(str(raw["severity"]["HIGH"])),
        severity_medium=Decimal(str(raw["severity"]["MEDIUM"])),
        price_tolerance_pct=Decimal(str(raw["price_tolerance_pct"])),
        cost_tolerance_abs=Decimal(str(raw["cost_tolerance_abs"])),
        cost_tolerance_pct=Decimal(str(raw["cost_tolerance_pct"])),
        historical_months=int(raw["historical_baseline"]["months"]),
        historical_min_observations=int(raw["historical_baseline"]["min_observations"]),
        historical_max_dispersion_pct=Decimal(str(raw["historical_baseline"].get("max_dispersion_pct", 15))),
        gm_pct_deterioration_points=Decimal(str(raw["gm_pct_deterioration_points"])),
        freight_product_codes=frozenset(str(c) for c in raw.get("freight_product_codes", [])),
    )
