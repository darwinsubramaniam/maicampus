"""Render the MAI Campus student user manual to PDF.

Pipeline: ``manual.md`` (Markdown) -> HTML (python-markdown) -> PDF (WeasyPrint), styled by
``style.css``. Image ``src`` paths and the stylesheet are resolved relative to this folder.

Usage::

    uv run python docs/user-manual/build_pdf.py
"""

from __future__ import annotations

from pathlib import Path

import markdown
from weasyprint import HTML

HERE = Path(__file__).resolve().parent
MD = HERE / "manual.md"
CSS = HERE / "style.css"
OUT = HERE / "MAiCampus-User-Manual.pdf"

_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>MAI Campus User Manual</title></head>
<body>{body}</body></html>"""


def build() -> Path:
    body = markdown.markdown(
        MD.read_text(encoding="utf-8"),
        extensions=["extra", "attr_list", "sane_lists", "smarty"],
    )
    html = _TEMPLATE.format(body=body)
    HTML(string=html, base_url=str(HERE)).write_pdf(str(OUT), stylesheets=[str(CSS)])
    print(f"[pdf] wrote {OUT.relative_to(HERE.parents[1])}", flush=True)
    return OUT


if __name__ == "__main__":
    build()
