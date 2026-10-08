"""Every operation the client sends must validate against the API schema.

Refresh the schema with:  curl -o schema.graphql http://localhost:8080/graphql/schema
"""

from pathlib import Path

import pytest
from graphql import build_schema, parse, validate

from letsemploy_publisher import EmployerInput, FeedInput, JobInput, JobType, MembershipRole
from letsemploy_publisher import _operations as ops

SCHEMA = build_schema((Path(__file__).parent.parent / "schema.graphql").read_text())

JOB = JobInput(title="t", url="https://x", language="en", job_type=JobType.PERMANENT)

OPERATIONS = {
    "employer": ops.employer(),
    "job": ops.job("1"),
    "jobs": ops.jobs(q="x", job_type=JobType.CONTRACT),
    "feeds": ops.feeds(),
    "locations": ops.locations(),
    "tags": ops.tags("x"),
    "members": ops.members(),
    "pending_invitations": ops.pending_invitations(),
    "permalinks": ops.permalinks(),
    "update_employer": ops.update_employer(EmployerInput(name="n")),
    "create_job": ops.create_job(JOB),
    "update_job": ops.update_job("1", JOB),
    "activate_job": ops.activate_job("1"),
    "deactivate_job": ops.deactivate_job("1"),
    "delete_job": ops.delete_job("1"),
    "create_feed": ops.create_feed(FeedInput(name="f")),
    "update_feed": ops.update_feed("1", FeedInput(name="f")),
    "add_job_to_feed": ops.add_job_to_feed("1", "2"),
    "remove_job_from_feed": ops.remove_job_from_feed("1", "2"),
    "create_permalink": ops.create_permalink(ops.PermalinkInput(name="p")),
    "update_permalink": ops.update_permalink("1", ops.PermalinkInput(name="p")),
    "set_permalink_feed": ops.set_permalink_feed("1", None),
    "delete_permalink": ops.delete_permalink("1"),
    "invite_member": ops.invite_member("a@b.c", MembershipRole.EDITOR),
    "revoke_invitation": ops.revoke_invitation("1"),
    "change_member_role": ops.change_member_role("1", MembershipRole.OWNER),
    "suspend_member": ops.suspend_member("1"),
    "reinstate_member": ops.reinstate_member("1"),
    "remove_member": ops.remove_member("1"),
}


@pytest.mark.parametrize("name", OPERATIONS)
def test_operation_is_valid(name: str) -> None:
    errors = validate(SCHEMA, parse(OPERATIONS[name].query))
    assert not errors, errors


def test_every_root_field_is_covered() -> None:
    used = set()
    for op in OPERATIONS.values():
        document = parse(op.query)
        for definition in document.definitions:
            if hasattr(definition, "operation"):
                used |= {sel.name.value for sel in definition.selection_set.selections}
    expected = set(SCHEMA.query_type.fields) | set(SCHEMA.mutation_type.fields)
    assert expected - used == set()
