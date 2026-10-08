"""Sync and async clients for the publisher GraphQL API."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from types import TracebackType
from typing import Any, TypeVar

import httpx

from . import _operations as ops
from .errors import AuthenticationError, GraphQLError, PublisherError, TransportError
from .models import (
    Employer,
    EmployerInput,
    Feed,
    FeedInput,
    Invitation,
    InviteOutcome,
    Job,
    JobInput,
    JobPage,
    JobType,
    Location,
    Member,
    MembershipRole,
    Permalink,
    PermalinkInput,
    Presentation,
    Tag,
)

__all__ = ["AsyncPublisherClient", "PublisherClient"]

T = TypeVar("T")

DEFAULT_URL = "https://publisher.letsemploy.org/graphql"
TOKEN_ENV = "LETSEMPLOY_PUBLISHER_TOKEN"
URL_ENV = "LETSEMPLOY_PUBLISHER_URL"
DEFAULT_TIMEOUT = 30.0


class _BaseClient:
    def __init__(self, token: str | None, url: str | None) -> None:
        token = token or os.environ.get(TOKEN_ENV)
        if not token:
            raise PublisherError(f"No service token given: pass token= or set {TOKEN_ENV}.")
        self.url = url or os.environ.get(URL_ENV) or DEFAULT_URL
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    @staticmethod
    def _body(op: ops.Operation[Any]) -> dict[str, Any]:
        return {"query": op.query, "variables": op.variables}

    @staticmethod
    def _handle(response: httpx.Response, op: ops.Operation[T]) -> T:
        try:
            body = response.json()
        except ValueError:
            body = None

        if isinstance(body, dict) and body.get("errors"):
            error_cls = GraphQLError
            codes = {(e.get("extensions") or {}).get("code") for e in body["errors"]}
            if response.status_code == 401 or "UNAUTHENTICATED" in codes:
                error_cls = AuthenticationError
            raise error_cls(body["errors"], status_code=response.status_code)

        if response.is_error or not isinstance(body, dict) or body.get("data") is None:
            raise TransportError(
                f"Unexpected response: HTTP {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
            )
        return op.parse(body["data"])


class PublisherClient(_BaseClient):
    """Synchronous client. The employer is implied by the service token.

    >>> with PublisherClient(token="...") as client:
    ...     print(client.employer().name)

    ``token`` and ``url`` fall back to the ``LETSEMPLOY_PUBLISHER_TOKEN`` and
    ``LETSEMPLOY_PUBLISHER_URL`` environment variables. Pass ``http_client``
    to supply your own :class:`httpx.Client` (proxies, retries, ...).
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(token, url)
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)

    def execute(self, op: ops.Operation[T]) -> T:
        try:
            response = self._http.post(self.url, json=self._body(op), headers=self._headers)
        except httpx.HTTPError as exc:
            raise TransportError(str(exc)) from exc
        return self._handle(response, op)

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> PublisherClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # --- queries --------------------------------------------------------------

    def employer(self) -> Employer:
        """The employer this token belongs to."""
        return self.execute(ops.employer())

    def job(self, id: str) -> Job | None:
        return self.execute(ops.job(id))

    def jobs(
        self,
        *,
        page: int = 0,
        size: int = 20,
        q: str | None = None,
        job_type: JobType | None = None,
        presentation: Presentation | None = None,
    ) -> JobPage:
        """One page of jobs (zero-based ``page``)."""
        return self.execute(
            ops.jobs(page=page, size=size, q=q, job_type=job_type, presentation=presentation)
        )

    def iter_jobs(
        self,
        *,
        size: int = 100,
        q: str | None = None,
        job_type: JobType | None = None,
        presentation: Presentation | None = None,
    ) -> Iterator[Job]:
        """Yield every matching job, fetching pages as needed."""
        page = 0
        while True:
            result = self.jobs(
                page=page, size=size, q=q, job_type=job_type, presentation=presentation
            )
            yield from result.content
            page += 1
            if page >= result.total_pages or not result.content:
                return

    def feeds(self) -> list[Feed]:
        return self.execute(ops.feeds())

    def locations(self, q: str | None = None) -> list[Location]:
        """The employer's own locations, whose ids ``JobInput.location_ids`` accepts."""
        return self.execute(ops.locations(q))

    def tags(self, q: str | None = None) -> list[Tag]:
        """The employer's own tags, whose ids ``JobInput.tag_ids`` accepts."""
        return self.execute(ops.tags(q))

    def members(self) -> list[Member]:
        return self.execute(ops.members())

    def pending_invitations(self) -> list[Invitation]:
        return self.execute(ops.pending_invitations())

    def permalinks(self) -> list[Permalink]:
        return self.execute(ops.permalinks())

    # --- mutations ------------------------------------------------------------

    def update_employer(self, input: EmployerInput) -> Employer:
        return self.execute(ops.update_employer(input))

    def create_job(self, input: JobInput) -> Job:
        return self.execute(ops.create_job(input))

    def update_job(self, id: str, input: JobInput) -> Job:
        return self.execute(ops.update_job(id, input))

    def activate_job(self, id: str) -> Job:
        return self.execute(ops.activate_job(id))

    def deactivate_job(self, id: str) -> Job:
        return self.execute(ops.deactivate_job(id))

    def delete_job(self, id: str) -> str:
        """Delete a job; returns the deleted id."""
        return self.execute(ops.delete_job(id))

    def create_feed(self, input: FeedInput) -> Feed:
        return self.execute(ops.create_feed(input))

    def update_feed(self, id: str, input: FeedInput) -> Feed:
        return self.execute(ops.update_feed(id, input))

    def add_job_to_feed(self, feed_id: str, job_id: str) -> Feed:
        return self.execute(ops.add_job_to_feed(feed_id, job_id))

    def remove_job_from_feed(self, feed_id: str, job_id: str) -> Feed:
        return self.execute(ops.remove_job_from_feed(feed_id, job_id))

    def create_permalink(self, input: PermalinkInput) -> Permalink:
        return self.execute(ops.create_permalink(input))

    def update_permalink(self, id: str, input: PermalinkInput) -> Permalink:
        return self.execute(ops.update_permalink(id, input))

    def set_permalink_feed(self, id: str, feed_id: str | None) -> Permalink:
        """Switch what the permalink publishes; ``None`` publishes no jobs."""
        return self.execute(ops.set_permalink_feed(id, feed_id))

    def delete_permalink(self, id: str) -> str:
        """The URL stops working (404) for everyone. To publish nothing, set no feed instead."""
        return self.execute(ops.delete_permalink(id))

    def invite_member(self, email: str, role: MembershipRole) -> InviteOutcome:
        return self.execute(ops.invite_member(email, role))

    def revoke_invitation(self, id: str) -> str:
        return self.execute(ops.revoke_invitation(id))

    def change_member_role(self, user_id: str, role: MembershipRole) -> Member:
        return self.execute(ops.change_member_role(user_id, role))

    def suspend_member(self, user_id: str) -> Member:
        """Keep the membership and role but grant nothing until reinstated."""
        return self.execute(ops.suspend_member(user_id))

    def reinstate_member(self, user_id: str) -> Member:
        return self.execute(ops.reinstate_member(user_id))

    def remove_member(self, user_id: str) -> str:
        return self.execute(ops.remove_member(user_id))


class AsyncPublisherClient(_BaseClient):
    """Asynchronous client; same methods as :class:`PublisherClient`, awaited.

    >>> async with AsyncPublisherClient(token="...") as client:
    ...     print((await client.employer()).name)
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(token, url)
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)

    async def execute(self, op: ops.Operation[T]) -> T:
        try:
            response = await self._http.post(self.url, json=self._body(op), headers=self._headers)
        except httpx.HTTPError as exc:
            raise TransportError(str(exc)) from exc
        return self._handle(response, op)

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncPublisherClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    # --- queries --------------------------------------------------------------

    async def employer(self) -> Employer:
        """The employer this token belongs to."""
        return await self.execute(ops.employer())

    async def job(self, id: str) -> Job | None:
        return await self.execute(ops.job(id))

    async def jobs(
        self,
        *,
        page: int = 0,
        size: int = 20,
        q: str | None = None,
        job_type: JobType | None = None,
        presentation: Presentation | None = None,
    ) -> JobPage:
        """One page of jobs (zero-based ``page``)."""
        return await self.execute(
            ops.jobs(page=page, size=size, q=q, job_type=job_type, presentation=presentation)
        )

    async def iter_jobs(
        self,
        *,
        size: int = 100,
        q: str | None = None,
        job_type: JobType | None = None,
        presentation: Presentation | None = None,
    ) -> AsyncIterator[Job]:
        """Yield every matching job, fetching pages as needed."""
        page = 0
        while True:
            result = await self.jobs(
                page=page, size=size, q=q, job_type=job_type, presentation=presentation
            )
            for job in result.content:
                yield job
            page += 1
            if page >= result.total_pages or not result.content:
                return

    async def feeds(self) -> list[Feed]:
        return await self.execute(ops.feeds())

    async def locations(self, q: str | None = None) -> list[Location]:
        """The employer's own locations, whose ids ``JobInput.location_ids`` accepts."""
        return await self.execute(ops.locations(q))

    async def tags(self, q: str | None = None) -> list[Tag]:
        """The employer's own tags, whose ids ``JobInput.tag_ids`` accepts."""
        return await self.execute(ops.tags(q))

    async def members(self) -> list[Member]:
        return await self.execute(ops.members())

    async def pending_invitations(self) -> list[Invitation]:
        return await self.execute(ops.pending_invitations())

    async def permalinks(self) -> list[Permalink]:
        return await self.execute(ops.permalinks())

    # --- mutations ------------------------------------------------------------

    async def update_employer(self, input: EmployerInput) -> Employer:
        return await self.execute(ops.update_employer(input))

    async def create_job(self, input: JobInput) -> Job:
        return await self.execute(ops.create_job(input))

    async def update_job(self, id: str, input: JobInput) -> Job:
        return await self.execute(ops.update_job(id, input))

    async def activate_job(self, id: str) -> Job:
        return await self.execute(ops.activate_job(id))

    async def deactivate_job(self, id: str) -> Job:
        return await self.execute(ops.deactivate_job(id))

    async def delete_job(self, id: str) -> str:
        """Delete a job; returns the deleted id."""
        return await self.execute(ops.delete_job(id))

    async def create_feed(self, input: FeedInput) -> Feed:
        return await self.execute(ops.create_feed(input))

    async def update_feed(self, id: str, input: FeedInput) -> Feed:
        return await self.execute(ops.update_feed(id, input))

    async def add_job_to_feed(self, feed_id: str, job_id: str) -> Feed:
        return await self.execute(ops.add_job_to_feed(feed_id, job_id))

    async def remove_job_from_feed(self, feed_id: str, job_id: str) -> Feed:
        return await self.execute(ops.remove_job_from_feed(feed_id, job_id))

    async def create_permalink(self, input: PermalinkInput) -> Permalink:
        return await self.execute(ops.create_permalink(input))

    async def update_permalink(self, id: str, input: PermalinkInput) -> Permalink:
        return await self.execute(ops.update_permalink(id, input))

    async def set_permalink_feed(self, id: str, feed_id: str | None) -> Permalink:
        """Switch what the permalink publishes; ``None`` publishes no jobs."""
        return await self.execute(ops.set_permalink_feed(id, feed_id))

    async def delete_permalink(self, id: str) -> str:
        """The URL stops working (404) for everyone. To publish nothing, set no feed instead."""
        return await self.execute(ops.delete_permalink(id))

    async def invite_member(self, email: str, role: MembershipRole) -> InviteOutcome:
        return await self.execute(ops.invite_member(email, role))

    async def revoke_invitation(self, id: str) -> str:
        return await self.execute(ops.revoke_invitation(id))

    async def change_member_role(self, user_id: str, role: MembershipRole) -> Member:
        return await self.execute(ops.change_member_role(user_id, role))

    async def suspend_member(self, user_id: str) -> Member:
        """Keep the membership and role but grant nothing until reinstated."""
        return await self.execute(ops.suspend_member(user_id))

    async def reinstate_member(self, user_id: str) -> Member:
        return await self.execute(ops.reinstate_member(user_id))

    async def remove_member(self, user_id: str) -> str:
        return await self.execute(ops.remove_member(user_id))
