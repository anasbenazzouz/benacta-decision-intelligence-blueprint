"""
Vendor the two BENACTA charter type families into `assets/fonts/`.

    python scripts/vendor_fonts.py

Google Fonts ships both families as variable fonts. Chromium embeds a variable
instance into a PDF as a Type3 font, which searches and prints less reliably
than a CID subset, so each weight the Blueprint uses is baked into its own
static instance here. The result is committed; this script only needs to run
again if a weight is added or the upstream fonts are updated.

Charter roles:
  role 2 · ENTERPRISE Instrument Sans, the whole system (no Light weight)
  role 3 · EDITORIAL  Source Serif 4, statements and quotes only
  role 1 · HERITAGE   Libre Caslon Display: NOT vendored. It is reserved for
                        the logo, and the logo is never re-typeset the
                        supplied lockup artwork is used instead.
"""

from __future__ import annotations

import re
import shutil
import urllib.request
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

OUT = Path(__file__).resolve().parent.parent / "assets" / "fonts"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}

#: family query -> (local stem, weights to instance)
FAMILIES = {
    "Instrument+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400": (
        "InstrumentSans",
        (400, 500, 600, 700),
    ),
    "Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400;1,8..60,600": (
        "SourceSerif4",
        (400, 600),
    ),
}

#: Optical size to bake into faces that carry an opsz axis this document is
#: set at text sizes, not display sizes.
OPSZ = 11

OFL_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/instrumentsans/OFL.txt"


def download_latin_sources() -> dict[str, Path]:
    """Fetch the upstream latin-subset woff2 for each family and style."""
    sources: dict[str, Path] = {}
    for query, (stem, _) in FAMILIES.items():
        url = f"https://fonts.googleapis.com/css2?family={query}&display=block"
        css = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=60
        ).read().decode()
        for subset, block in re.findall(
            r"/\*\s*([\w\-\[\]]+)\s*\*/\s*(@font-face\s*\{.*?\})", css, re.S
        ):
            if subset != "latin":
                continue
            italic = re.search(r"font-style:\s*(\w+);", block).group(1) == "italic"
            href = re.search(r"url\((https://[^)]+)\)", block).group(1)
            key = f"{stem}-Italic" if italic else stem
            if key in sources:
                continue  # a variable face serves every weight
            path = OUT / f"_src-{key}.woff2"
            path.write_bytes(
                urllib.request.urlopen(
                    urllib.request.Request(href, headers=UA), timeout=60
                ).read()
            )
            sources[key] = path
    return sources


def emit_static(source: Path, stem: str, weights: tuple[int, ...]) -> None:
    probe = TTFont(source)
    is_variable = "fvar" in probe
    axes = {axis.axisTag for axis in probe["fvar"].axes} if is_variable else set()

    for weight in weights:
        destination = OUT / f"{stem}-{weight}.woff2"
        if not is_variable:
            # Upstream already ships a single static instance for this style.
            shutil.copyfile(source, destination)
        else:
            coordinates = {"wght": weight}
            if "opsz" in axes:
                coordinates["opsz"] = OPSZ
            instance = instancer.instantiateVariableFont(
                TTFont(source), coordinates, updateFontNames=True, inplace=False
            )
            instance.flavor = "woff2"
            instance.save(destination)
        print(f"  {destination.name:32} {destination.stat().st_size:>7} bytes")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.woff2"):
        stale.unlink()

    sources = download_latin_sources()
    for _, (stem, weights) in FAMILIES.items():
        emit_static(sources[stem], stem, weights)
        italic = sources.get(f"{stem}-Italic")
        if italic:
            emit_static(italic, f"{stem}-Italic", weights)

    for temporary in OUT.glob("_src-*.woff2"):
        temporary.unlink()

    ofl = OUT / "OFL.txt"
    if not ofl.exists():
        ofl.write_bytes(urllib.request.urlopen(OFL_URL, timeout=60).read())
    print(f"\n{len(list(OUT.glob('*.woff2')))} faces in {OUT.name}/ SIL Open Font License 1.1")


if __name__ == "__main__":
    main()
