"""Unit tests for the minimal CEL evaluator (the gcp-cel correctness oracle).

The GCP vector corpus exercises the evaluator end-to-end; these pin each operator and
string function individually -- including the ones no shipped vector uses yet (||, !,
endsWith, contains) -- and the load-bearing semantics that are easy to get wrong:
matches() is unanchored (substring), and an absent claim raises rather than reading false.
"""

from __future__ import annotations

import pytest

from subvectors.cel import CelError, evaluate

CLAIMS = {
    "sub": "repo:octo-org/octo-repo:ref:refs/heads/main",
    "repository": "octo-org/octo-repo",
    "repository_owner": "octo-org",
    "repository_id": "260064828",
    "repository_owner_id": "1342004",
    "ref": "refs/heads/main",
    "event_name": "push",
}


def test_equality_and_inequality() -> None:
    assert evaluate("assertion.repository_owner == 'octo-org'", CLAIMS) is True
    assert evaluate("assertion.repository_owner == 'other'", CLAIMS) is False
    assert evaluate("assertion.repository_owner != 'other'", CLAIMS) is True


def test_and_or_not_and_precedence() -> None:
    assert evaluate("assertion.ref == 'refs/heads/main' && assertion.event_name == 'push'", CLAIMS) is True
    assert evaluate("assertion.ref == 'refs/heads/dev' || assertion.event_name == 'push'", CLAIMS) is True
    assert evaluate("!(assertion.event_name == 'pull_request')", CLAIMS) is True
    # unary ! binds tighter than == : !a == b parses as (!a) == b, a type error here.
    with pytest.raises(CelError):
        evaluate("!assertion.event_name == 'push'", CLAIMS)


def test_in_list() -> None:
    assert evaluate("assertion.repository_owner_id in ['1342004', '9999999']", CLAIMS) is True
    assert evaluate("assertion.repository_owner_id in ['9999999']", CLAIMS) is False


def test_string_functions() -> None:
    assert evaluate("assertion.ref.startsWith('refs/heads/')", CLAIMS) is True
    assert evaluate("assertion.ref.endsWith('/main')", CLAIMS) is True
    assert evaluate("assertion.ref.contains('heads')", CLAIMS) is True
    assert evaluate("assertion.repository.startsWith('other/')", CLAIMS) is False


def test_matches_is_unanchored_substring() -> None:
    # RE2 matches() succeeds on a SUBSTRING -- so an unanchored pattern is permissive.
    assert evaluate("assertion.ref.matches('heads/main')", CLAIMS) is True
    assert evaluate("assertion.ref.matches('^refs/heads/main$')", CLAIMS) is True
    # A leading tag pattern without ^ still matches because 'refs/tags/' is a substring... of
    # a tag ref; on this branch ref it correctly does not.
    assert evaluate("assertion.ref.matches('^refs/tags/')", CLAIMS) is False
    # Without the anchor, a crafted ref could smuggle the substring:
    assert evaluate("assertion.ref.matches('refs/heads')", {**CLAIMS, "ref": "x/refs/heads/y"}) is True


def test_absent_claim_raises_not_false() -> None:
    with pytest.raises(CelError):
        evaluate("assertion.environment == 'prod'", CLAIMS)


def test_unknown_function_raises() -> None:
    with pytest.raises(CelError):
        evaluate("assertion.ref.beginsWith('refs/')", CLAIMS)


def test_parse_errors_raise() -> None:
    for bad in ["assertion.ref ==", "assertion.ref = 'x'", "(assertion.ref == 'x'", "assertion..ref == 'x'"]:
        with pytest.raises(CelError):
            evaluate(bad, CLAIMS)


def test_non_boolean_result_raises() -> None:
    # A bare claim (string) is not a valid condition result.
    with pytest.raises(CelError):
        evaluate("assertion.repository", CLAIMS)


def test_grouping_overrides_precedence() -> None:
    # (a || b) && c  vs  a || (b && c)
    claims = {**CLAIMS, "event_name": "pull_request"}
    assert evaluate("(assertion.ref == 'refs/heads/main' || assertion.event_name == 'push') && assertion.repository == 'octo-org/octo-repo'", claims) is True
    assert evaluate("assertion.event_name == 'push' || assertion.ref == 'refs/heads/dev' && assertion.repository == 'x'", claims) is False
