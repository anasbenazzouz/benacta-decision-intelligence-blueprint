"""Export the ground-truth manifest of the demonstration profile to data/golden for review and versioning.

Application code never reads data/golden; this script is the only writer and lives outside `apps/api/app`.
Run: `uv run --project apps/api python scripts/export_ground_truth.py`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from app.fixtures.full_profile import build_full_profile, ground_truth  # noqa: E402

TARGET = REPO_ROOT / "data" / "golden" / "demo_full_manifest_v1.json"


def main() -> int:
    manifest = ground_truth(build_full_profile())
    TARGET.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(f"wrote {TARGET.relative_to(REPO_ROOT)}: {len(manifest['scenarios'])} scenarios, {manifest['structure']['sale_order_lines']} order lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
