"""
Render the Blueprint HTML master to PDF, then to page images for visual QA.

    python scripts/render_blueprint.py            # render PDF + QA page images
    python scripts/render_blueprint.py --pdf-only # render PDF only

The visual QA loop is mandatory before the PDF is considered done: render,
inspect every page, compare against the charter, fix, render again.

The page images are working artefacts and are written to `outputs/` (gitignored).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "docs" / "controlled-intelligence-blueprint.html"
PDF = ROOT / "docs" / "BENACTA_Controlled_Intelligence_Blueprint.pdf"
QA_DIR = ROOT / "outputs" / "blueprint-qa"

EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


def find_browser() -> str:
    for candidate in EDGE_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    for name in ("msedge", "chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("No Chromium-based browser found for print-to-PDF.")


def render_pdf() -> None:
    profile = Path(tempfile.gettempdir()) / "edge-benacta-blueprint"
    subprocess.run(
        [
            find_browser(),
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            f"--user-data-dir={profile}",
            "--no-pdf-header-footer",
            f"--print-to-pdf={PDF}",
            HTML.as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    stamp_metadata()
    print(f"PDF   {PDF.relative_to(ROOT)}  ({PDF.stat().st_size / 1024:.0f} KB)")


def stamp_metadata() -> None:
    """Chromium carries <title> across but not author, subject or keywords."""
    import pymupdf

    document = pymupdf.open(PDF)
    document.set_metadata(
        {
            "title": "BENACTA Controlled Intelligence Blueprint",
            "author": "Anas Benazzouz BENACTA",
            "subject": "How to introduce AI into enterprise decision-making "
            "without giving up control of the truth.",
            "keywords": "decision intelligence, enterprise AI, governed data, "
            "trust boundary, human-in-the-loop, BENACTA",
            "creator": "BENACTA",
        }
    )
    document.saveIncr()
    document.close()


def render_page_images(dpi: int = 130) -> None:
    import pymupdf

    QA_DIR.mkdir(parents=True, exist_ok=True)
    for stale in QA_DIR.glob("page-*.png"):
        stale.unlink()

    document = pymupdf.open(PDF)
    for index, page in enumerate(document, start=1):
        pixmap = page.get_pixmap(dpi=dpi)
        pixmap.save(QA_DIR / f"page-{index:02d}.png")
    box = document[0].mediabox
    print(
        f"PAGES {len(document)} at {box.width * 25.4 / 72:.0f} x "
        f"{box.height * 25.4 / 72:.0f} mm -> {QA_DIR.relative_to(ROOT)}"
    )
    document.close()


if __name__ == "__main__":
    render_pdf()
    if "--pdf-only" not in sys.argv:
        render_page_images()
