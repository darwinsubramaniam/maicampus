"""One-shot orchestrator: (re)capture every screen, then render the PDF.

    uv run python docs/user-manual/build.py

Equivalent to running each ``capture.py`` flow followed by ``build_pdf.py``. As more screens
are added, register their flow name in ``FLOWS`` and they'll be included automatically.
"""

from __future__ import annotations

import build_pdf
import capture

# Capture flows to run, in document order. Extend as new screens are added.
FLOWS = ["login", "chat", "chat_examples", "calendar", "booking", "settings"]


def main() -> None:
    for name in FLOWS:
        print(f"\n=== capture: {name} ===", flush=True)
        getattr(capture, name)()
    print("\n=== render pdf ===", flush=True)
    build_pdf.build()


if __name__ == "__main__":
    main()
