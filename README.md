# letsemploy-publisher

Python client for the letsemploy publisher GraphQL API. Requires Python 3.10+.

The employer is implied by the service token, so it is never passed as an argument.

## Install

```sh
uv add letsemploy-publisher
```

## Usage

```python
from letsemploy_publisher import JobInput, JobType, PublisherClient, UserErrorsError

with PublisherClient(token="...") as client:
    print(client.employer().name)

    for job in client.iter_jobs():  # walks every page
        print(job.id, job.title, job.presentation)

    bern = client.locations(q="Bern")[0]
    try:
        job = client.create_job(
            JobInput(
                title="Python Engineer",
                url="https://example.com/jobs/python",
                language="de",
                job_type=JobType.PERMANENT,
                location_ids=[bern.id],
            )
        )
        client.activate_job(job.id)
    except UserErrorsError as exc:
        for error in exc.user_errors:
            print(error.field, error.code, error.message)
```

`token` and `url` fall back to the `LETSEMPLOY_PUBLISHER_TOKEN` and
`LETSEMPLOY_PUBLISHER_URL` environment variables; the URL defaults to
`https://publisher.letsemploy.org/graphql`.

An async client with the same methods is available:

```python
from letsemploy_publisher import AsyncPublisherClient

async with AsyncPublisherClient() as client:
    feeds = await client.feeds()
```

### Errors

All exceptions derive from `PublisherError`:

| Exception             | Raised when                                                         |
| --------------------- | ------------------------------------------------------------------- |
| `UserErrorsError`     | A mutation returned `userErrors`; see `.user_errors`.               |
| `AuthenticationError` | The token is missing or invalid (`UNAUTHENTICATED`).                |
| `GraphQLError`        | The response has a top-level `errors` array; see `.errors`, `.code`. |
| `TransportError`      | Network failure, timeout or an unexpected HTTP response.            |

### Inputs and updates

`updateJob`, `updateFeed`, `updatePermalink` and `updateEmployer` replace the
whole object: every field of the input dataclass is sent, so a field left as
`None` is cleared.

## Development

```sh
uv sync
uv run ruff format .
uv run ruff check .
uv run pytest
```

The tests validate every query and mutation against `schema.graphql` and check
that every root field of the schema is covered. When the API changes, refresh
the schema and run the tests:

```sh
curl -o schema.graphql http://localhost:8080/graphql/schema
uv run pytest
```
