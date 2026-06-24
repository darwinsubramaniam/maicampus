"""Brand the Flet web client's loading screen (replaces the default pulsing Flet logo).

Flet's web app is served from the `flet_web` package's bundled `web/` directory. `flet_web`
honours the ``FLET_WEB_PATH`` env var to serve an alternative directory, so at build time we
copy the (version-matched) web client and swap the boot loader for a MAI Campus one — a teal
CSS spinner + wordmark instead of the Flet logo. Flet's own `patch_index.py` only edits the
base href / app-config / title meta, so the loading markup we inject here is left intact.

Usage:  python scripts/customize_web.py <dest_web_dir>
Then run the app with  FLET_WEB_PATH=<dest_web_dir>.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import flet_web

_LOADING_HTML = """<div id="loading">
    <style>
      body { inset: 0; overflow: hidden; margin: 0; padding: 0; position: fixed; }
      #loading {
        position: fixed; inset: 0; display: flex; flex-direction: column;
        align-items: center; justify-content: center; gap: 20px;
        background: #0F1514; color: #E0E3E1;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        transition: opacity .45s ease;
      }
      #loading.init_done { opacity: 0; pointer-events: none; }
      #loading .ring {
        width: 56px; height: 56px; border-radius: 50%;
        border: 4px solid rgba(0, 137, 123, .22); border-top-color: #26A69A;
        animation: mc-spin 1s linear infinite;
      }
      #loading .brand { font-size: 24px; font-weight: 700; letter-spacing: -.4px; }
      #loading .sub { font-size: 13px; opacity: .55; margin-top: -10px; }
      @keyframes mc-spin { to { transform: rotate(360deg); } }
      @media (prefers-color-scheme: light) {
        #loading { background: #FAFCFB; color: #1A1C1B; }
        #loading .ring { border-color: rgba(0, 137, 123, .18); border-top-color: #00897B; }
      }
    </style>
    <div class="ring"></div>
    <div class="brand">MAI Campus</div>
    <div class="sub">Loading your campus companion…</div>
  </div>
  """

# Matches the whole default loading <div> up to (but not including) the flutter bootstrap script.
_LOADING_RE = re.compile(
    r'<div id="loading">.*?</div>\s*(?=<script src="flutter_bootstrap\.js")', re.DOTALL
)


def main(dest: str) -> None:
    src_web = Path(flet_web.get_package_web_dir())
    dest_web = Path(dest)
    if dest_web.exists():
        shutil.rmtree(dest_web)
    shutil.copytree(src_web, dest_web)

    index_path = dest_web / "index.html"
    html = index_path.read_text(encoding="utf-8")

    html, n = _LOADING_RE.subn(_LOADING_HTML, html)
    if n == 0:
        raise SystemExit("customize_web: could not find the Flet loading <div> to replace")

    html = html.replace("<title>Flet</title>", "<title>MAI Campus</title>")
    html = html.replace('content="Flet application."', 'content="MAI Campus"')
    html = html.replace(
        '<meta name="apple-mobile-web-app-title" content="Flet">',
        '<meta name="apple-mobile-web-app-title" content="MAI Campus">',
    )

    index_path.write_text(html, encoding="utf-8")
    print(f"customize_web: branded loading screen written to {index_path}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/app/web")
