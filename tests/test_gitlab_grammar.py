"""Unit tests for the GitLab OIDC subject grammar (default + immutable forms).

The immutable case is the project_id-led sub produced by reconfiguring
ci_id_token_sub_claim_components -- GitLab's only in-sub rename-proof form, since
project_id/namespace_id are otherwise separate claims, not embedded in the sub.
"""

from __future__ import annotations

from subvectors.gitlab import parse_subject


def test_parses_default_branch_subject() -> None:
    seg = parse_subject("project_path:mygroup/myproject:ref_type:branch:ref:main")
    assert seg is not None
    assert seg.project_path == "mygroup/myproject"
    assert (seg.namespace_path, seg.project) == ("mygroup", "myproject")
    assert (seg.ref_type, seg.ref) == ("branch", "main")
    assert seg.project_id is None
    assert seg.immutable is False


def test_parses_tag_subject() -> None:
    seg = parse_subject("project_path:mygroup/myproject:ref_type:tag:ref:v1.0.0")
    assert seg is not None
    assert (seg.ref_type, seg.ref) == ("tag", "v1.0.0")


def test_parses_nested_subgroup_path() -> None:
    seg = parse_subject("project_path:mygroup/subgroup/deepproject:ref_type:branch:ref:main")
    assert seg is not None
    assert seg.project_path == "mygroup/subgroup/deepproject"
    assert (seg.namespace_path, seg.project) == ("mygroup/subgroup", "deepproject")


def test_parses_immutable_projectid_subject() -> None:
    seg = parse_subject("project_id:20:ref_type:branch:ref:main")
    assert seg is not None
    assert seg.project_id == "20"
    assert seg.project_path is None
    assert (seg.namespace_path, seg.project) == (None, None)
    assert seg.immutable is True
    assert (seg.ref_type, seg.ref) == ("branch", "main")


def test_ref_may_contain_slash() -> None:
    seg = parse_subject("project_path:mygroup/myproject:ref_type:branch:ref:release/1.0")
    assert seg is not None
    assert seg.ref == "release/1.0"


def test_wildcard_in_path_is_not_a_subject() -> None:
    assert parse_subject("project_path:mygroup/*:ref_type:branch:ref:main") is None


def test_wildcard_in_ref_is_not_a_subject() -> None:
    assert parse_subject("project_path:mygroup/myproject:ref_type:branch:ref:*") is None


def test_wildcard_in_ref_type_is_not_a_subject() -> None:
    assert parse_subject("project_path:mygroup/myproject:ref_type:*:ref:main") is None


def test_github_subject_is_none() -> None:
    # A GitHub repo: subject is not a GitLab subject.
    assert parse_subject("repo:octo-org/octo-repo:ref:refs/heads/main") is None


def test_unknown_ref_type_is_none() -> None:
    # ref_type is exactly branch|tag; anything else is not the documented shape.
    assert parse_subject("project_path:mygroup/myproject:ref_type:merge:ref:main") is None
