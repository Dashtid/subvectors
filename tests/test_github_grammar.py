"""Unit tests for the GitHub OIDC subject grammar (classic + immutable forms).

The immutable cases are the ones that matter: they are the format that becomes
mandatory for new repositories after 2026-07-15, and the format a classic-only
parser silently drops.
"""

from __future__ import annotations

from oidc_conformance.github import parse_repo_segment


def test_parses_classic_subject() -> None:
    seg = parse_repo_segment("repo:octo-org/octo-repo:ref:refs/heads/main")
    assert seg is not None
    assert (seg.owner, seg.repo) == ("octo-org", "octo-repo")
    assert seg.owner_id is None and seg.repo_id is None
    assert seg.immutable is False


def test_parses_immutable_subject() -> None:
    seg = parse_repo_segment("repo:octo-org@123456/octo-repo@7891011:ref:refs/heads/main")
    assert seg is not None
    assert (seg.owner, seg.repo) == ("octo-org", "octo-repo")
    assert (seg.owner_id, seg.repo_id) == ("123456", "7891011")
    assert seg.immutable is True


def test_parses_pull_request_suffix() -> None:
    seg = parse_repo_segment("repo:octo-org/octo-repo:pull_request")
    assert seg is not None
    assert (seg.owner, seg.repo) == ("octo-org", "octo-repo")


def test_non_repo_scoped_subject_is_none() -> None:
    # A subject scoped by a different leading claim is not a repo segment.
    assert parse_repo_segment("repository_owner:octo-org:ref:refs/heads/main") is None


def test_wildcard_in_repo_position_is_not_a_subject() -> None:
    # A wildcard in the owner/repo segment is a trust-policy pattern, not a
    # minted subject, so it does not parse as a repo segment.
    assert parse_repo_segment("repo:octo-org/*:ref:refs/heads/main") is None
    assert parse_repo_segment("repo:*/octo-repo:ref:refs/heads/main") is None


def test_parser_scope_is_the_owner_repo_segment_only() -> None:
    # parse_repo_segment inspects only the leading repo:owner/repo: segment.
    # A wildcard in the *suffix* (the claim part) is out of its scope: the
    # owner/repo are still concrete, so a RepoSegment is returned. Judging that
    # suffix wildcard is the matcher's job, not the grammar's.
    seg = parse_repo_segment("repo:octo-org/octo-repo:*")
    assert seg is not None
    assert (seg.owner, seg.repo) == ("octo-org", "octo-repo")
