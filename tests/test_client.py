import json

import httpx
import pytest

from letsemploy_publisher import (
    AsyncPublisherClient,
    AuthenticationError,
    GraphQLError,
    JobInput,
    JobStatus,
    JobType,
    PermalinkInput,
    Presentation,
    PublisherClient,
    PublisherError,
    TransportError,
    UserErrorsError,
)

LOCATION = {"id": "l1", "city": "Bern", "country": "CH"}
JOB = {
    "id": "j1",
    "title": "Engineer",
    "url": "https://example.com/j1",
    "language": "de",
    "jobType": "PERMANENT",
    "status": "ACTIVE",
    "presentation": "PUBLISHED",
    "locations": [LOCATION],
    "tags": ["python"],
    "salaryInterval": "YEARLY",
    "salaryMin": 90000.0,
    "experienceLevel": None,
}


def make_client(handler) -> PublisherClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return PublisherClient(token="secret", url="https://api.test/graphql", http_client=http)


def data(payload):
    return lambda request: httpx.Response(200, json={"data": payload})


def test_sends_bearer_token_and_variables():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": {"job": JOB}})

    job = make_client(handler).job("j1")

    assert seen["auth"] == "Bearer secret"
    assert seen["body"]["variables"] == {"id": "j1"}
    assert job.job_type is JobType.PERMANENT
    assert job.status is JobStatus.ACTIVE
    assert job.locations[0].city == "Bern"
    assert job.salary_min == 90000.0
    assert job.experience_level is None


def test_missing_job_returns_none():
    assert make_client(data({"job": None})).job("nope") is None


def test_jobs_omits_unset_optional_arguments():
    seen = {}

    def handler(request):
        seen["vars"] = json.loads(request.content)["variables"]
        page = {"content": [], "page": 0, "size": 20, "totalElements": 0, "totalPages": 0}
        return httpx.Response(200, json={"data": {"jobs": page}})

    make_client(handler).jobs(presentation=Presentation.PUBLISHED)
    assert seen["vars"] == {"page": 0, "size": 20, "presentation": "PUBLISHED"}


def test_iter_jobs_walks_all_pages():
    pages = []

    def handler(request):
        page = json.loads(request.content)["variables"]["page"]
        pages.append(page)
        content = [{**JOB, "id": f"j{page}"}]
        body = {"content": content, "page": page, "size": 1, "totalElements": 3, "totalPages": 3}
        return httpx.Response(200, json={"data": {"jobs": body}})

    ids = [job.id for job in make_client(handler).iter_jobs(size=1)]
    assert ids == ["j0", "j1", "j2"]
    assert pages == [0, 1, 2]


def test_job_input_serialises_enums_and_keeps_nulls():
    seen = {}

    def handler(request):
        seen["input"] = json.loads(request.content)["variables"]["input"]
        return httpx.Response(200, json={"data": {"createJob": {"job": JOB, "userErrors": []}}})

    make_client(handler).create_job(
        JobInput(
            title="Engineer",
            url="https://example.com/j1",
            language="de",
            job_type=JobType.PERMANENT,
            location_ids=["l1"],
        )
    )
    assert seen["input"]["jobType"] == "PERMANENT"
    assert seen["input"]["locationIds"] == ["l1"]
    assert "description" in seen["input"] and seen["input"]["description"] is None


def test_set_permalink_feed_sends_explicit_null():
    seen = {}

    def handler(request):
        seen["vars"] = json.loads(request.content)["variables"]
        permalink = {"id": "p1", "name": "Main", "url": "https://x/ojobpub.json", "feed": None}
        payload = {"permalink": permalink, "userErrors": []}
        return httpx.Response(200, json={"data": {"setPermalinkFeed": payload}})

    permalink = make_client(handler).set_permalink_feed("p1", None)
    assert seen["vars"] == {"id": "p1", "feedId": None}
    assert permalink.feed is None


def test_user_errors_raise():
    payload = {
        "createPermalink": {
            "permalink": None,
            "userErrors": [{"code": "REQUIRED", "field": "name", "message": "Name is required"}],
        }
    }
    with pytest.raises(UserErrorsError) as exc:
        make_client(data(payload)).create_permalink(PermalinkInput(name=""))
    assert exc.value.user_errors[0].code == "REQUIRED"
    assert "name: Name is required" in str(exc.value)


def test_unauthenticated_raises_authentication_error():
    body = {
        "errors": [
            {"message": "That token is not valid.", "extensions": {"code": "UNAUTHENTICATED"}}
        ]
    }
    client = make_client(lambda r: httpx.Response(401, json=body))
    with pytest.raises(AuthenticationError) as exc:
        client.employer()
    assert exc.value.code == "UNAUTHENTICATED"
    assert exc.value.status_code == 401


def test_graphql_errors_raise():
    body = {"errors": [{"message": "boom"}], "data": None}
    with pytest.raises(GraphQLError, match="boom"):
        make_client(lambda r: httpx.Response(200, json=body)).feeds()


def test_non_json_response_raises_transport_error():
    with pytest.raises(TransportError) as exc:
        make_client(lambda r: httpx.Response(502, text="Bad Gateway")).feeds()
    assert exc.value.status_code == 502


def test_network_error_raises_transport_error():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(TransportError, match="refused"):
        make_client(handler).feeds()


def test_token_from_environment(monkeypatch):
    monkeypatch.setenv("LETSEMPLOY_PUBLISHER_TOKEN", "from-env")
    monkeypatch.setenv("LETSEMPLOY_PUBLISHER_URL", "https://env.test/graphql")
    client = PublisherClient()
    assert client.url == "https://env.test/graphql"
    assert client._headers["Authorization"] == "Bearer from-env"
    client.close()


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("LETSEMPLOY_PUBLISHER_TOKEN", raising=False)
    with pytest.raises(PublisherError, match="token"):
        PublisherClient()


async def test_async_client():
    page = {"content": [JOB], "page": 0, "size": 20, "totalElements": 1, "totalPages": 1}
    http = httpx.AsyncClient(transport=httpx.MockTransport(data({"jobs": page})))
    async with AsyncPublisherClient(token="secret", http_client=http) as client:
        jobs = [job async for job in client.iter_jobs()]
    assert [job.id for job in jobs] == ["j1"]
