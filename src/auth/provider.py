"""Google OAuth provider wiring (Flet native ``GoogleOAuthProvider``).

Configured from the environment so no secrets live in the repo:

* ``MAICAMPUS_GOOGLE_CLIENT_ID`` / ``MAICAMPUS_GOOGLE_CLIENT_SECRET`` — OAuth client credentials.
* ``MAICAMPUS_GOOGLE_REDIRECT_URL`` — the registered redirect, e.g.
  ``http://localhost:8550/oauth_callback`` locally or ``https://<host>/oauth_callback`` in prod.
"""

from __future__ import annotations

import os

from flet.auth.providers import GoogleOAuthProvider

_DEFAULT_REDIRECT = "http://localhost:8550/oauth_callback"

# Comma-separated list of allowed email domains. Default restricts sign-in to UTM accounts;
# a value matches the exact domain OR any subdomain (so "utm.my" allows graduate.utm.my,
# live.utm.my, etc.). Set to empty/"*" to allow any Google account.
_ALLOWED_DOMAINS = [
    d.strip().lower()
    for d in os.environ.get("MAICAMPUS_ALLOWED_EMAIL_DOMAINS", "utm.my").split(",")
    if d.strip() and d.strip() != "*"
]


def google_oauth_configured() -> bool:
    """True when the Google client id/secret are present in the environment."""
    return bool(os.environ.get("MAICAMPUS_GOOGLE_CLIENT_ID") and os.environ.get("MAICAMPUS_GOOGLE_CLIENT_SECRET"))


def allowed_domains_label() -> str:
    """Human-readable allowed-domain hint for the access-denied screen (e.g. '@utm.my')."""
    return ", ".join(f"@{d}" for d in _ALLOWED_DOMAINS) or "any account"


def email_allowed(email: str) -> bool:
    """Server-side gate: is this email from an allowed (UTM) domain? Empty allowlist = allow all."""
    if not _ALLOWED_DOMAINS:
        return True
    parts = (email or "").lower().rsplit("@", 1)
    if len(parts) != 2:
        return False
    domain = parts[1]
    return any(domain == d or domain.endswith(f".{d}") for d in _ALLOWED_DOMAINS)


def build_google_provider() -> GoogleOAuthProvider:
    provider = GoogleOAuthProvider(
        client_id=os.environ["MAICAMPUS_GOOGLE_CLIENT_ID"],
        client_secret=os.environ["MAICAMPUS_GOOGLE_CLIENT_SECRET"],
        redirect_url=os.environ.get("MAICAMPUS_GOOGLE_REDIRECT_URL", _DEFAULT_REDIRECT),
    )
    # Always show Google's account chooser so users can switch accounts (e.g. from a personal
    # gmail to their UTM account). When sign-in is restricted to a single domain, hint Google to
    # pre-filter the chooser to that domain (`hd`). These ride along into the authorization URL.
    params: dict[str, str] = {"prompt": "select_account"}
    if len(_ALLOWED_DOMAINS) == 1:
        params["hd"] = _ALLOWED_DOMAINS[0]
    provider.authorization_params = params
    return provider
