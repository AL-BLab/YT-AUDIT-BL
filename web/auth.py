"""Authentication helpers for Google IAP and local development mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from flask import current_app, request

from web.models import User


@dataclass
class AuthIdentity:
    email: str
    display_name: str


def parse_iap_email(raw_header: str) -> Optional[str]:
    """Parse IAP header format: accounts.google.com:user@example.com."""
    if not raw_header:
        return None
    value = raw_header.strip()
    if ":" in value:
        return value.split(":", 1)[1].strip().lower()
    return value.lower()


def get_authenticated_email() -> Optional[str]:
    """Resolve authenticated email from IAP headers or local dev fallback."""
    iap_header = request.headers.get("X-Goog-Authenticated-User-Email", "")
    forwarded_email = request.headers.get("X-Forwarded-Email", "")

    email = parse_iap_email(iap_header) or parse_iap_email(forwarded_email)
    if email:
        return email

    return current_app.config.get("DEV_AUTH_EMAIL")


def get_or_create_user(db_session, email: str) -> User:
    user = db_session.query(User).filter(User.email == email).one_or_none()
    if user:
        return user

    display_name = email.split("@", 1)[0].replace(".", " ").title()
    user = User(email=email, display_name=display_name)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
