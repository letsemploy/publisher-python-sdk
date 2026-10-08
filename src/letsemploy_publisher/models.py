"""Typed models for the publisher GraphQL API.

Output types are frozen dataclasses built from GraphQL responses with
``from_dict``. Input types are dataclasses serialised with ``to_dict``; every
field is sent, so ``None`` explicitly clears a value on update.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# --- enums --------------------------------------------------------------------


class ExperienceLevel(str, Enum):
    DIRECTOR = "DIRECTOR"
    EXECUTIVE = "EXECUTIVE"
    JUNIOR = "JUNIOR"
    LEAD = "LEAD"
    MANAGER = "MANAGER"
    MID = "MID"
    SENIOR = "SENIOR"


class InvitationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    PENDING = "PENDING"
    REVOKED = "REVOKED"


class InviteOutcome(str, Enum):
    """What an invite attempt did.

    ``SENT`` is returned both when an invitation was created and when no account
    matched the address, so the API does not reveal which addresses exist.
    """

    ALREADY_INVITED = "ALREADY_INVITED"
    ALREADY_MEMBER = "ALREADY_MEMBER"
    SENT = "SENT"


class JobStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DRAFT = "DRAFT"
    INACTIVE = "INACTIVE"


class JobType(str, Enum):
    APPRENTICESHIP = "APPRENTICESHIP"
    CONTRACT = "CONTRACT"
    FREELANCE = "FREELANCE"
    INTERNSHIP = "INTERNSHIP"
    PERMANENT = "PERMANENT"
    TEMPORARY = "TEMPORARY"
    VOLUNTEER = "VOLUNTEER"


class MembershipRole(str, Enum):
    EDITOR = "EDITOR"
    OWNER = "OWNER"


class Presentation(str, Enum):
    DRAFT = "DRAFT"
    EXPIRED = "EXPIRED"
    INACTIVE = "INACTIVE"
    INCOMPLETE = "INCOMPLETE"
    PUBLISHED = "PUBLISHED"


class SalaryInterval(str, Enum):
    DAILY = "DAILY"
    HOURLY = "HOURLY"
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"
    YEARLY = "YEARLY"


class WorkType(str, Enum):
    HYBRID = "HYBRID"
    ON_SITE = "ON_SITE"
    REMOTE = "REMOTE"


def _enum(cls: type[Enum], value: Any) -> Any:
    return None if value is None else cls(value)


# --- output types -------------------------------------------------------------


@dataclass(frozen=True)
class UserError:
    """A rejected input or a broken rule. ``code`` is stable; ``message`` is for display."""

    code: str
    message: str
    field: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserError:
        return cls(code=data["code"], message=data["message"], field=data.get("field"))


@dataclass(frozen=True)
class Location:
    id: str
    city: str
    country: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Location:
        return cls(id=data["id"], city=data["city"], country=data["country"])


@dataclass(frozen=True)
class Tag:
    id: str
    name: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Tag:
        return cls(id=data["id"], name=data["name"])


@dataclass(frozen=True)
class Employer:
    id: str
    name: str
    slug: str
    headquarters: Location
    industry: str | None = None
    url: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Employer:
        return cls(
            id=data["id"],
            name=data["name"],
            slug=data["slug"],
            headquarters=Location.from_dict(data["headquarters"]),
            industry=data.get("industry"),
            url=data.get("url"),
        )


@dataclass(frozen=True)
class Job:
    id: str
    title: str
    url: str
    language: str
    job_type: JobType
    status: JobStatus
    """The stored lifecycle state."""
    presentation: Presentation
    """What the job presents as today: published, expired, incomplete, ..."""
    locations: list[Location] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str | None = None
    category: str | None = None
    reference_id: str | None = None
    experience_level: ExperienceLevel | None = None
    work_type: WorkType | None = None
    work_load_percent_min: int | None = None
    work_load_percent_max: int | None = None
    salary_currency: str | None = None
    salary_interval: SalaryInterval | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    apply_before: str | None = None
    published_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        return cls(
            id=data["id"],
            title=data["title"],
            url=data["url"],
            language=data["language"],
            job_type=JobType(data["jobType"]),
            status=JobStatus(data["status"]),
            presentation=Presentation(data["presentation"]),
            locations=[Location.from_dict(loc) for loc in data.get("locations") or []],
            tags=list(data.get("tags") or []),
            description=data.get("description"),
            category=data.get("category"),
            reference_id=data.get("referenceId"),
            experience_level=_enum(ExperienceLevel, data.get("experienceLevel")),
            work_type=_enum(WorkType, data.get("workType")),
            work_load_percent_min=data.get("workLoadPercentMin"),
            work_load_percent_max=data.get("workLoadPercentMax"),
            salary_currency=data.get("salaryCurrency"),
            salary_interval=_enum(SalaryInterval, data.get("salaryInterval")),
            salary_min=data.get("salaryMin"),
            salary_max=data.get("salaryMax"),
            start_date=data.get("startDate"),
            end_date=data.get("endDate"),
            apply_before=data.get("applyBefore"),
            published_at=data.get("publishedAt"),
        )


@dataclass(frozen=True)
class JobPage:
    """One page of jobs; ``page`` is zero-based."""

    content: list[Job]
    page: int
    size: int
    total_elements: int
    total_pages: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobPage:
        return cls(
            content=[Job.from_dict(job) for job in data["content"]],
            page=data["page"],
            size=data["size"],
            total_elements=data["totalElements"],
            total_pages=data["totalPages"],
        )


@dataclass(frozen=True)
class Feed:
    id: str
    name: str
    slug: str
    public_url: str
    """The public ojobpub.json URL."""
    jobs: list[Job] = field(default_factory=list)
    description: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Feed:
        return cls(
            id=data["id"],
            name=data["name"],
            slug=data["slug"],
            public_url=data["publicUrl"],
            jobs=[Job.from_dict(job) for job in data.get("jobs") or []],
            description=data.get("description"),
        )


@dataclass(frozen=True)
class Permalink:
    """A stable public URL whose feed can be switched."""

    id: str
    name: str
    url: str
    feed: Feed | None = None
    """What it publishes; ``None`` publishes the employer with no jobs."""
    description: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Permalink:
        feed = data.get("feed")
        return cls(
            id=data["id"],
            name=data["name"],
            url=data["url"],
            feed=Feed.from_dict(feed) if feed else None,
            description=data.get("description"),
        )


@dataclass(frozen=True)
class Member:
    user_id: str
    role: MembershipRole
    suspended: bool
    """A suspended member keeps their role but may not act on the employer."""
    display_name: str | None = None
    email: str | None = None
    suspended_at: str | None = None
    """When the suspension began, ISO-8601; ``None`` while active."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Member:
        return cls(
            user_id=data["userId"],
            role=MembershipRole(data["role"]),
            suspended=data["suspended"],
            display_name=data.get("displayName"),
            email=data.get("email"),
            suspended_at=data.get("suspendedAt"),
        )


@dataclass(frozen=True)
class Invitation:
    id: str
    invited_by: str
    role: MembershipRole
    status: InvitationStatus
    invitee_email: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Invitation:
        return cls(
            id=data["id"],
            invited_by=data["invitedBy"],
            role=MembershipRole(data["role"]),
            status=InvitationStatus(data["status"]),
            invitee_email=data.get("inviteeEmail"),
        )


# --- input types --------------------------------------------------------------


def _value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_value(v) for v in value]
    return value


@dataclass
class JobInput:
    title: str
    url: str
    language: str
    job_type: JobType
    description: str | None = None
    category: str | None = None
    reference_id: str | None = None
    experience_level: ExperienceLevel | None = None
    work_type: WorkType | None = None
    work_load_percent_min: int | None = None
    work_load_percent_max: int | None = None
    salary_currency: str | None = None
    salary_interval: SalaryInterval | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    apply_before: str | None = None
    location_ids: list[str] | None = None
    """Ids of the employer's own locations, see ``client.locations()``."""
    tag_ids: list[str] | None = None
    """Ids of the employer's own tags, see ``client.tags()``."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "language": self.language,
            "jobType": _value(self.job_type),
            "description": self.description,
            "category": self.category,
            "referenceId": self.reference_id,
            "experienceLevel": _value(self.experience_level),
            "workType": _value(self.work_type),
            "workLoadPercentMin": self.work_load_percent_min,
            "workLoadPercentMax": self.work_load_percent_max,
            "salaryCurrency": self.salary_currency,
            "salaryInterval": _value(self.salary_interval),
            "salaryMin": self.salary_min,
            "salaryMax": self.salary_max,
            "startDate": self.start_date,
            "endDate": self.end_date,
            "applyBefore": self.apply_before,
            "locationIds": _value(self.location_ids),
            "tagIds": _value(self.tag_ids),
        }


@dataclass
class EmployerInput:
    name: str
    slug: str | None = None
    industry: str | None = None
    url: str | None = None
    headquarters_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "slug": self.slug,
            "industry": self.industry,
            "url": self.url,
            "headquartersId": self.headquarters_id,
        }


@dataclass
class FeedInput:
    name: str
    slug: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "slug": self.slug, "description": self.description}


@dataclass
class PermalinkInput:
    name: str
    description: str | None = None
    feed_id: str | None = None
    """``None`` publishes no jobs."""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "feedId": self.feed_id}
