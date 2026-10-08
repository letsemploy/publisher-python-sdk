# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Python client (`letsemploy_publisher`, distribution `letsemploy-publisher`) for the letsemploy publisher GraphQL API. Python ≥3.10, uv, ruff, httpx; hand-written (no codegen).

## Commands

```sh
uv sync                                   # install incl. dev group
uv run ruff format . && uv run ruff check .
uv run pytest                             # all tests
uv run pytest tests/test_client.py::test_user_errors_raise   # single test
uv run --python 3.14 --isolated --group dev pytest           # another Python
uv build
curl -o schema.graphql http://localhost:8080/graphql/schema  # refresh schema from a local server
```

CI runs ruff format check, ruff check and pytest on 3.10–3.14 with `uv sync --locked`, so commit `uv.lock` changes.

## Architecture

Three layers in `src/letsemploy_publisher/`:

- `models.py`: enums (`str, Enum`, not `StrEnum`, for 3.10), frozen output dataclasses with `from_dict` (camelCase → snake_case), and input dataclasses with `to_dict`.
- `_operations.py`: one builder per GraphQL root field, returning `Operation(query, variables, parse)`. It has no HTTP code. Shared selections live in `FRAGMENTS`; `_document()` appends the fragments an operation uses, following nested `...Name` spreads, so never hand-append fragments. Mutations go through `_mutation()`, which raises `UserErrorsError` if the payload has `userErrors` and otherwise returns the unwrapped entity (or `deletedId` / `InviteOutcome`).
- `client.py`: `PublisherClient` and `AsyncPublisherClient` share `_BaseClient` (auth header, env fallback, response → exception mapping). Every public method is a one-line `execute(ops.x(...))`, written out in both classes. A new operation therefore needs a builder in `_operations.py`, a method in **both** clients, and an entry in `tests/test_schema.py`'s `OPERATIONS`.

Null handling is deliberate:
- Top-level optional query arguments go through `_optional()`, so unset values are omitted and server defaults apply (e.g. `jobs(page: Int = 0)`).
- Input objects (`JobInput.to_dict()` etc.) always send every field. `update*` mutations replace the whole object, so `None` clears a field.
- `set_permalink_feed(id, None)` sends an explicit `feedId: null`, which means "publish no jobs".

Auth: Bearer service token; the employer is implied by the token and is never an argument. `token` and `url` fall back to `LETSEMPLOY_PUBLISHER_TOKEN` and `LETSEMPLOY_PUBLISHER_URL`; the default URL is `https://publisher.letsemploy.org/graphql`. A 401 or `UNAUTHENTICATED` raises `AuthenticationError`.

## Tests

- `tests/test_schema.py` validates every operation against the checked-in `schema.graphql` (graphql-core) and fails if any root Query/Mutation field has no operation. After refreshing the schema, failures here show what the client is missing.
- `tests/test_client.py` uses `httpx.MockTransport`; nothing calls a live server. Async tests run without decorators (`asyncio_mode = "auto"`).

## Release

Pushing a tag (`v1.2.3` or `1.2.3`) runs `.github/workflows/publish.yml`: it calls `ci.yml`, sets the version from the tag with `uv version --frozen` (only in CI, so `pyproject.toml` stays at `0.1.0`), builds, and publishes to PyPI through trusted publishing (environment `pypi`). Dependabot groups patch and minor updates. Patch-only PRs auto-merge through `dependabot-automerge.yml`, so actions are pinned to exact versions (e.g. `@v7.0.1`), not major tags.
