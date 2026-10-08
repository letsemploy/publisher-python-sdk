"""Exceptions raised by the publisher client."""

from __future__ import annotations

from typing import Any

from .models import UserError


class PublisherError(Exception):
    """Base class for every error raised by this package."""


class TransportError(PublisherError):
    """The request failed below GraphQL: network error, timeout or unexpected HTTP status."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GraphQLError(PublisherError):
    """The server answered with a top-level ``errors`` array."""

    def __init__(self, errors: list[dict[str, Any]], status_code: int | None = None) -> None:
        self.errors = errors
        self.status_code = status_code
        self.code: str | None = (errors[0].get("extensions") or {}).get("code") if errors else None
        super().__init__("; ".join(e.get("message", "unknown error") for e in errors))


class AuthenticationError(GraphQLError):
    """The service token is missing or not valid (``UNAUTHENTICATED``)."""


class UserErrorsError(PublisherError):
    """A mutation was rejected; ``user_errors`` holds the reasons."""

    def __init__(self, user_errors: list[UserError]) -> None:
        self.user_errors = user_errors
        super().__init__(
            "; ".join(
                f"{e.field}: {e.message} ({e.code})" if e.field else f"{e.message} ({e.code})"
                for e in user_errors
            )
        )
