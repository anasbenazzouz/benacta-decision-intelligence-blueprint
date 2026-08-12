"""
Copy the supplied BENACTA logo packs into the project and derive tight crops.

The supplied packs are full artboards on the charter grounds (#122B20 dark,
#F1E9DA light) with generous margin. The application needs the same lockup
cropped to its content so it can be placed against a matching band without a
visible artboard edge. Nothing is recoloured, stretched or re-proportioned —
the crop is the only transformation, per the charter's logo rules.

    python scripts/prepare_brand_assets.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source" / "brand"
ORIGINALS = ROOT / "assets" / "source-brand-assets"
GENERATED = ROOT / "assets" / "generated"

#: Padding around the detected content, as a share of the content height.
_PADDING = 0.08


def content_box(image: Image.Image, tolerance: int = 24) -> tuple[int, int, int, int]:
    """Bounding box of everything that differs from the artboard ground."""
    ground = image.getpixel((2, 2))
    width, height = image.size
    pixels = image.load()

    min_x, min_y, max_x, max_y = width, height, 0, 0
    for y in range(0, height, 2):
        for x in range(0, width, 2):
            pixel = pixels[x, y]
            if sum(abs(a - b) for a, b in zip(pixel, ground)) > tolerance:
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)

    pad = int((max_y - min_y) * _PADDING)
    return (
        max(0, min_x - pad),
        max(0, min_y - pad),
        min(width, max_x + pad),
        min(height, max_y + pad),
    )


def crop_lockup(source_name: str, output_name: str, target_width: int = 900) -> Path:
    image = Image.open(SOURCE / source_name).convert("RGB")
    cropped = image.crop(content_box(image))

    ratio = target_width / cropped.width
    cropped = cropped.resize(
        (target_width, int(cropped.height * ratio)), Image.LANCZOS
    )

    GENERATED.mkdir(parents=True, exist_ok=True)
    destination = GENERATED / output_name
    cropped.save(destination, "PNG")
    return destination


def main() -> int:
    if not SOURCE.exists():
        print(f"Source brand folder not found: {SOURCE}", file=sys.stderr)
        return 1

    ORIGINALS.mkdir(parents=True, exist_ok=True)
    for asset in sorted(SOURCE.glob("*.png")):
        shutil.copy2(asset, ORIGINALS / asset.name)
        print(f"preserved  {ORIGINALS / asset.name}")

    for source_name, output_name in (
        ("BENACTA Logo Pack -Dark.png", "benacta-primary-dark.png"),
        ("BENACTA Logo Pack -Light.png", "benacta-primary-light.png"),
    ):
        path = crop_lockup(source_name, output_name)
        with Image.open(path) as rendered:
            print(f"derived    {path}  {rendered.size[0]}x{rendered.size[1]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
