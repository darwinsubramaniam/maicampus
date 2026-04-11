"""Auto-update checker — queries GitHub Releases for new versions."""

from __future__ import annotations

import json
import platform
import threading
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

GITHUB_REPO = "darwinsubramaniam/maicampus"


# Read version from pyproject.toml (single source of truth)
def _get_app_version() -> str:
    try:
        from importlib.metadata import version

        return version("maicampus")
    except Exception:
        pass
    # Fallback: parse pyproject.toml directly
    try:
        import re
        from pathlib import Path

        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        match = re.search(r'version\s*=\s*"(.+?)"', pyproject.read_text())
        if match:
            return match.group(1)
    except Exception:
        pass
    return "0.0.0"


APP_VERSION = _get_app_version()
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse version string like '0.1.0' or 'v0.1.0' into comparable tuple."""
    return tuple(int(x) for x in v.lstrip("v").split("."))


def _classify_update(current: tuple[int, ...], latest: tuple[int, ...]) -> str:
    """Classify update as 'major', 'minor', or 'patch'."""
    if latest[0] > current[0]:
        return "major"
    elif len(latest) > 1 and len(current) > 1 and latest[1] > current[1]:
        return "minor"
    else:
        return "patch"


def _get_platform_asset_name() -> str:
    system = platform.system().lower()
    return {
        "darwin": "maicampus-macos.zip",
        "windows": "maicampus-windows.zip",
        "linux": "maicampus-linux.tar.gz",
    }.get(system, "")


def check_for_update(on_update_available: Callable[[str, str, str, str], None]):
    """
    Check GitHub for a newer release in a background thread.

    Calls on_update_available(new_version, download_url, release_notes, update_type)
    where update_type is 'major', 'minor', or 'patch'.
    Does nothing if already on latest or if check fails.
    """

    def _check():
        try:
            req = urllib.request.Request(
                RELEASES_URL,
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "MAiCampus"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            latest_tag = data.get("tag_name", "")
            if not latest_tag:
                return

            latest_version = _parse_version(latest_tag)
            current_version = _parse_version(APP_VERSION)

            if latest_version <= current_version:
                return

            update_type = _classify_update(current_version, latest_version)

            # Find download URL for this platform
            asset_name = _get_platform_asset_name()
            download_url = ""
            for asset in data.get("assets", []):
                if asset.get("name") == asset_name:
                    download_url = asset.get("browser_download_url", "")
                    break

            if not download_url:
                download_url = data.get("html_url", "")

            release_notes = data.get("body", "")[:500]
            on_update_available(latest_tag, download_url, release_notes, update_type)

        except Exception:
            pass

    threading.Thread(target=_check, daemon=True).start()
