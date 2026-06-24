"""Authentication for MAI Campus — Google SSO + per-user identity resolution."""

from auth.provider import (
    allowed_domains_label,
    build_google_provider,
    email_allowed,
    google_oauth_configured,
)
from auth.session import resolve_user_context

__all__ = [
    "allowed_domains_label",
    "build_google_provider",
    "email_allowed",
    "google_oauth_configured",
    "resolve_user_context",
]
