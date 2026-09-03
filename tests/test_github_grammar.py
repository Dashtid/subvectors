"""Unit tests for the GitHub OIDC subject grammar (classic + immutable forms).

The immutable cases are the ones that matter: they are the format that becomes
mandatory for new repositories after 2026-07-15, and the format a classic-only
parser silently drops.

The one-sided cases guard the other edge: GitHub appends ``@id`` to both the
owner and the repo or to neither, so a subject carrying exactly one id is a
shape GitHub never mints. It parses (the ids present are still reported), but
it is not immutable -- the same verdict subcheck reaches when it labels that
shape ``malformed``.
"""

from __future__ import annotations

from subvectors.github import parse_repo_segment


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


def test_owner_id_only_is_malformed_not_immutable() -> None:
    # An id on the owner alone is a shape GitHub never mints: the subject is
    # malformed, not immutable. It still parses, and the one id that is
    # present is still reported -- only the immutable verdict is withheld.
    seg = parse_repo_segment("repo:octo-org@123456/octo-repo:ref:refs/heads/main")
    assert seg is not None
    assert (seg.owner, seg.repo) == ("octo-org", "octo-repo")
    assert (seg.owner_id, seg.repo_id) == ("123456", None)
    assert seg.immutable is False


def test_repo_id_only_is_malformed_not_immutable() -> None:
    # The mirror case: an id on the repo alone is equally malformed. Both
    # one-sided forms must agree, or a consumer could be told a half-migrated
    # subject is rename-proof when nothing pins the owner.
    seg = parse_repo_segment("repo:octo-org/octo-repo@7891011:ref:refs/heads/main")
    assert seg is not None
    assert (seg.owner, seg.repo) == ("octo-org", "octo-repo")
    assert (seg.owner_id, seg.repo_id) == (None, "7891011")
    assert seg.immutable is False


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


# --- the repo-only customized sub (documented, and previously rejected) ------
#
# GitHub's sub-customization docs give include_claim_keys: ["repo"] as the
# template for granting "cloud access to all the workflows in a specific
# repository, across all branches/tags and environments". That mints a bare
# `repo:ORG/REPO` with no context segment. parse_repo_segment required a
# trailing colon and returned None for it until 2026-09-02 -- rejecting a
# subject GitHub documents how to produce.


def test_repo_only_subject_parses():
    segment = parse_repo_segment("repo:octo-org/octo-repo")
    assert segment is not None
    assert (segment.owner, segment.repo) == ("octo-org", "octo-repo")
    assert segment.immutable is False


def test_repo_only_immutable_subject_parses():
    segment = parse_repo_segment("repo:octo-org@123456/octo-repo@456789")
    assert segment is not None
    assert (segment.owner_id, segment.repo_id) == ("123456", "456789")
    assert segment.immutable is True


def test_repo_only_and_contextful_subjects_agree_on_the_segment():
    bare = parse_repo_segment("repo:octo-org/octo-repo")
    full = parse_repo_segment("repo:octo-org/octo-repo:ref:refs/heads/main")
    assert (bare.owner, bare.repo) == (full.owner, full.repo)


def test_a_wildcard_in_the_owner_or_repo_position_is_still_rejected():
    """The optional context segment must not let owner/repo patterns through."""
    assert parse_repo_segment("repo:octo-org/*") is None
    assert parse_repo_segment("repo:*/octo-repo") is None


def test_a_wildcard_after_the_repo_segment_still_yields_the_segment():
    """Deliberate, and narrower than the module docstring used to claim.

    `repo:octo-org/octo-repo:*` is a trust-policy pattern, not a minted subject
    -- but its owner/repo half is concrete, and a consumer grading the most
    common dangerous pattern in the corpus wants to know which repository it
    names. Pinned so the narrowing is a decision, not a drift.
    """
    segment = parse_repo_segment("repo:octo-org/octo-repo:*")
    assert segment is not None
    assert (segment.owner, segment.repo) == ("octo-org", "octo-repo")


def test_the_immutable_customized_sub_parses_without_a_context_segment() -> None:
    """Two rules meet here, and the corpus depends on both holding at once.

    GitHub's `include_claim_keys: ["repo"]` mints a bare `repo:ORG/REPO`, and on an
    immutable repository "owner_id and repo_id are always included in the repo
    segment ... even when you customize claims" -- so the customized subject of an
    immutable repo is `repo:OWNER@OWNER-ID/REPO@REPO-ID` with nothing after it.
    That shape only parses because the context segment is optional, which is a
    separate fix (2026-09-02); pinned here so neither change can quietly undo the
    other. Vector: gh-aws-immutable-custom-sub-keeps-the-ids.
    """
    segment = parse_repo_segment("repo:octo-org@123456/octo-repo@456789")
    assert segment is not None
    assert (segment.owner, segment.repo) == ("octo-org", "octo-repo")
    assert (segment.owner_id, segment.repo_id) == ("123456", "456789")
    assert segment.immutable


def test_a_renamed_repository_keeps_its_ids_and_changes_its_name() -> None:
    """A rename after 2026-07-15 flips the format and moves the NAME only.

    The repo id is what a rename cannot touch, which is the whole argument for
    pinning repository_id over a name. Vector:
    gh-aws-rename-flips-format-and-breaks-the-policy.
    """
    before = parse_repo_segment("repo:octo-org@123456/octo-repo@7891011:ref:refs/heads/main")
    after = parse_repo_segment("repo:octo-org@123456/octo-repo-renamed@7891011:ref:refs/heads/main")
    assert before is not None and after is not None
    assert before.repo != after.repo
    assert before.repo_id == after.repo_id == "7891011"
    assert before.owner_id == after.owner_id == "123456"
