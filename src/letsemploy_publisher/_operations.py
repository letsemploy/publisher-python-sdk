"""GraphQL documents and response parsers, independent of the HTTP layer.

Each builder returns an :class:`Operation`; the sync and async clients only
differ in how they send it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from .errors import UserErrorsError
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
    UserError,
)

T = TypeVar("T")

FRAGMENTS: dict[str, str] = {
    "LocationFields": """
fragment LocationFields on Location { id city country }""",
    "EmployerFields": """
fragment EmployerFields on Employer {
  id name slug industry url
  headquarters { ...LocationFields }
}""",
    "JobFields": """
fragment JobFields on Job {
  id title url language jobType status presentation
  description category referenceId experienceLevel workType
  workLoadPercentMin workLoadPercentMax
  salaryCurrency salaryInterval salaryMin salaryMax
  startDate endDate applyBefore publishedAt tags
  locations { ...LocationFields }
}""",
    "FeedFields": """
fragment FeedFields on Feed {
  id name slug description publicUrl
  jobs { ...JobFields }
}""",
    "PermalinkFields": """
fragment PermalinkFields on Permalink {
  id name description url
  feed { ...FeedFields }
}""",
    "MemberFields": """
fragment MemberFields on Member { userId displayName email role suspended suspendedAt }""",
    "InvitationFields": """
fragment InvitationFields on Invitation { id invitedBy inviteeEmail role status }""",
}

_SPREAD = re.compile(r"\.\.\.(\w+)")


def _document(operation: str) -> str:
    """Append every fragment the operation uses, transitively."""
    needed: list[str] = []
    pending = _SPREAD.findall(operation)
    while pending:
        name = pending.pop()
        if name not in needed:
            needed.append(name)
            pending.extend(_SPREAD.findall(FRAGMENTS[name]))
    return operation.strip() + "".join(FRAGMENTS[n] for n in sorted(needed))


@dataclass(frozen=True)
class Operation(Generic[T]):
    query: str
    variables: dict[str, Any]
    parse: Callable[[dict[str, Any]], T]


def _payload(data: dict[str, Any], field: str) -> dict[str, Any]:
    payload = data[field]
    errors = payload.get("userErrors") or []
    if errors:
        raise UserErrorsError([UserError.from_dict(e) for e in errors])
    return payload


def _mutation(
    query: str,
    variables: dict[str, Any],
    field: str,
    parse: Callable[[dict[str, Any]], T],
) -> Operation[T]:
    return Operation(_document(query), variables, lambda d: parse(_payload(d, field)))


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _optional(**variables: Any) -> dict[str, Any]:
    """Leave out unset optional arguments so server-side defaults apply."""
    return {k: _value(v) for k, v in variables.items() if v is not None}


# --- queries ------------------------------------------------------------------


def employer() -> Operation[Employer]:
    return Operation(
        _document("query Employer { employer { ...EmployerFields } }"),
        {},
        lambda d: Employer.from_dict(d["employer"]),
    )


def job(id: str) -> Operation[Job | None]:
    return Operation(
        _document("query Job($id: ID!) { job(id: $id) { ...JobFields } }"),
        {"id": id},
        lambda d: Job.from_dict(d["job"]) if d["job"] else None,
    )


def jobs(
    *,
    page: int = 0,
    size: int = 20,
    q: str | None = None,
    job_type: JobType | None = None,
    presentation: Presentation | None = None,
) -> Operation[JobPage]:
    return Operation(
        _document(
            """
query Jobs($page: Int, $size: Int, $q: String, $jobType: JobType, $presentation: Presentation) {
  jobs(page: $page, size: $size, q: $q, jobType: $jobType, presentation: $presentation) {
    content { ...JobFields }
    page size totalElements totalPages
  }
}"""
        ),
        _optional(page=page, size=size, q=q, jobType=job_type, presentation=presentation),
        lambda d: JobPage.from_dict(d["jobs"]),
    )


def feeds() -> Operation[list[Feed]]:
    return Operation(
        _document("query Feeds { feeds { ...FeedFields } }"),
        {},
        lambda d: [Feed.from_dict(f) for f in d["feeds"]],
    )


def locations(q: str | None = None) -> Operation[list[Location]]:
    return Operation(
        _document("query Locations($q: String) { locations(q: $q) { ...LocationFields } }"),
        _optional(q=q),
        lambda d: [Location.from_dict(loc) for loc in d["locations"]],
    )


def tags(q: str | None = None) -> Operation[list[Tag]]:
    return Operation(
        _document("query Tags($q: String) { tags(q: $q) { id name } }"),
        _optional(q=q),
        lambda d: [Tag.from_dict(t) for t in d["tags"]],
    )


def members() -> Operation[list[Member]]:
    return Operation(
        _document("query Members { members { ...MemberFields } }"),
        {},
        lambda d: [Member.from_dict(m) for m in d["members"]],
    )


def pending_invitations() -> Operation[list[Invitation]]:
    return Operation(
        _document("query PendingInvitations { pendingInvitations { ...InvitationFields } }"),
        {},
        lambda d: [Invitation.from_dict(i) for i in d["pendingInvitations"]],
    )


def permalinks() -> Operation[list[Permalink]]:
    return Operation(
        _document("query Permalinks { permalinks { ...PermalinkFields } }"),
        {},
        lambda d: [Permalink.from_dict(p) for p in d["permalinks"]],
    )


# --- mutations: employer ------------------------------------------------------


def update_employer(input: EmployerInput) -> Operation[Employer]:
    return _mutation(
        """
mutation UpdateEmployer($input: EmployerInput!) {
  updateEmployer(input: $input) { employer { ...EmployerFields } userErrors { code field message } }
}""",
        {"input": input.to_dict()},
        "updateEmployer",
        lambda p: Employer.from_dict(p["employer"]),
    )


# --- mutations: jobs ----------------------------------------------------------

_JOB_PAYLOAD = "{ job { ...JobFields } userErrors { code field message } }"
_DELETE_PAYLOAD = "{ deletedId userErrors { code field message } }"


def _job(p: dict[str, Any]) -> Job:
    return Job.from_dict(p["job"])


def _deleted_id(p: dict[str, Any]) -> str:
    return p["deletedId"]


def create_job(input: JobInput) -> Operation[Job]:
    return _mutation(
        f"mutation CreateJob($input: JobInput!) {{ createJob(input: $input) {_JOB_PAYLOAD} }}",
        {"input": input.to_dict()},
        "createJob",
        _job,
    )


def update_job(id: str, input: JobInput) -> Operation[Job]:
    return _mutation(
        "mutation UpdateJob($id: ID!, $input: JobInput!) "
        f"{{ updateJob(id: $id, input: $input) {_JOB_PAYLOAD} }}",
        {"id": id, "input": input.to_dict()},
        "updateJob",
        _job,
    )


def activate_job(id: str) -> Operation[Job]:
    return _mutation(
        f"mutation ActivateJob($id: ID!) {{ activateJob(id: $id) {_JOB_PAYLOAD} }}",
        {"id": id},
        "activateJob",
        _job,
    )


def deactivate_job(id: str) -> Operation[Job]:
    return _mutation(
        f"mutation DeactivateJob($id: ID!) {{ deactivateJob(id: $id) {_JOB_PAYLOAD} }}",
        {"id": id},
        "deactivateJob",
        _job,
    )


def delete_job(id: str) -> Operation[str]:
    return _mutation(
        f"mutation DeleteJob($id: ID!) {{ deleteJob(id: $id) {_DELETE_PAYLOAD} }}",
        {"id": id},
        "deleteJob",
        _deleted_id,
    )


# --- mutations: feeds ---------------------------------------------------------

_FEED_PAYLOAD = "{ feed { ...FeedFields } userErrors { code field message } }"


def _feed(p: dict[str, Any]) -> Feed:
    return Feed.from_dict(p["feed"])


def create_feed(input: FeedInput) -> Operation[Feed]:
    return _mutation(
        f"mutation CreateFeed($input: FeedInput!) {{ createFeed(input: $input) {_FEED_PAYLOAD} }}",
        {"input": input.to_dict()},
        "createFeed",
        _feed,
    )


def update_feed(id: str, input: FeedInput) -> Operation[Feed]:
    return _mutation(
        "mutation UpdateFeed($id: ID!, $input: FeedInput!) "
        f"{{ updateFeed(id: $id, input: $input) {_FEED_PAYLOAD} }}",
        {"id": id, "input": input.to_dict()},
        "updateFeed",
        _feed,
    )


def add_job_to_feed(feed_id: str, job_id: str) -> Operation[Feed]:
    return _mutation(
        "mutation AddJobToFeed($feedId: ID!, $jobId: ID!) "
        f"{{ addJobToFeed(feedId: $feedId, jobId: $jobId) {_FEED_PAYLOAD} }}",
        {"feedId": feed_id, "jobId": job_id},
        "addJobToFeed",
        _feed,
    )


def remove_job_from_feed(feed_id: str, job_id: str) -> Operation[Feed]:
    return _mutation(
        "mutation RemoveJobFromFeed($feedId: ID!, $jobId: ID!) "
        f"{{ removeJobFromFeed(feedId: $feedId, jobId: $jobId) {_FEED_PAYLOAD} }}",
        {"feedId": feed_id, "jobId": job_id},
        "removeJobFromFeed",
        _feed,
    )


# --- mutations: permalinks ----------------------------------------------------

_PERMALINK_PAYLOAD = "{ permalink { ...PermalinkFields } userErrors { code field message } }"


def _permalink(p: dict[str, Any]) -> Permalink:
    return Permalink.from_dict(p["permalink"])


def create_permalink(input: PermalinkInput) -> Operation[Permalink]:
    return _mutation(
        "mutation CreatePermalink($input: PermalinkInput!) "
        f"{{ createPermalink(input: $input) {_PERMALINK_PAYLOAD} }}",
        {"input": input.to_dict()},
        "createPermalink",
        _permalink,
    )


def update_permalink(id: str, input: PermalinkInput) -> Operation[Permalink]:
    return _mutation(
        "mutation UpdatePermalink($id: ID!, $input: PermalinkInput!) "
        f"{{ updatePermalink(id: $id, input: $input) {_PERMALINK_PAYLOAD} }}",
        {"id": id, "input": input.to_dict()},
        "updatePermalink",
        _permalink,
    )


def set_permalink_feed(id: str, feed_id: str | None) -> Operation[Permalink]:
    return _mutation(
        "mutation SetPermalinkFeed($id: ID!, $feedId: ID) "
        f"{{ setPermalinkFeed(id: $id, feedId: $feedId) {_PERMALINK_PAYLOAD} }}",
        {"id": id, "feedId": feed_id},
        "setPermalinkFeed",
        _permalink,
    )


def delete_permalink(id: str) -> Operation[str]:
    return _mutation(
        f"mutation DeletePermalink($id: ID!) {{ deletePermalink(id: $id) {_DELETE_PAYLOAD} }}",
        {"id": id},
        "deletePermalink",
        _deleted_id,
    )


# --- mutations: members -------------------------------------------------------

_MEMBER_PAYLOAD = "{ member { ...MemberFields } userErrors { code field message } }"


def _member(p: dict[str, Any]) -> Member:
    return Member.from_dict(p["member"])


def invite_member(email: str, role: MembershipRole) -> Operation[InviteOutcome]:
    return _mutation(
        """
mutation InviteMember($email: String!, $role: MembershipRole!) {
  inviteMember(email: $email, role: $role) { outcome userErrors { code field message } }
}""",
        {"email": email, "role": _value(role)},
        "inviteMember",
        lambda p: InviteOutcome(p["outcome"]),
    )


def revoke_invitation(id: str) -> Operation[str]:
    return _mutation(
        f"mutation RevokeInvitation($id: ID!) {{ revokeInvitation(id: $id) {_DELETE_PAYLOAD} }}",
        {"id": id},
        "revokeInvitation",
        _deleted_id,
    )


def change_member_role(user_id: str, role: MembershipRole) -> Operation[Member]:
    return _mutation(
        "mutation ChangeMemberRole($userId: ID!, $role: MembershipRole!) "
        f"{{ changeMemberRole(userId: $userId, role: $role) {_MEMBER_PAYLOAD} }}",
        {"userId": user_id, "role": _value(role)},
        "changeMemberRole",
        _member,
    )


def suspend_member(user_id: str) -> Operation[Member]:
    return _mutation(
        "mutation SuspendMember($userId: ID!) "
        f"{{ suspendMember(userId: $userId) {_MEMBER_PAYLOAD} }}",
        {"userId": user_id},
        "suspendMember",
        _member,
    )


def reinstate_member(user_id: str) -> Operation[Member]:
    return _mutation(
        "mutation ReinstateMember($userId: ID!) "
        f"{{ reinstateMember(userId: $userId) {_MEMBER_PAYLOAD} }}",
        {"userId": user_id},
        "reinstateMember",
        _member,
    )


def remove_member(user_id: str) -> Operation[str]:
    return _mutation(
        "mutation RemoveMember($userId: ID!) "
        f"{{ removeMember(userId: $userId) {_DELETE_PAYLOAD} }}",
        {"userId": user_id},
        "removeMember",
        _deleted_id,
    )
