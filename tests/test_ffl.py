"""Unit tests for the flexible-FIC expression evaluator (the azure-fic-flexible oracle).

The GitHub vector corpus exercises the evaluator end-to-end; these pin each operator
and the load-bearing semantics: matches() is an ANCHORED glob (not a substring), '?'
is exactly one character, '*' spans separators, 'and' requires every clause, and a
reference to an absent claim raises rather than reading false.
"""

from __future__ import annotations

import pytest

from subvectors.ffl import FflError, evaluate

SUB = "repo:octo-org/octo-repo:ref:refs/heads/main"
CLAIMS = {
    "sub": SUB,
    "job_workflow_ref": "octo-org/reusable/.github/workflows/deploy.yml@refs/heads/main",
}


def test_eq_is_exact_and_case_sensitive() -> None:
    assert evaluate(f"claims['sub'] eq '{SUB}'", CLAIMS) is True
    assert evaluate("claims['sub'] eq 'repo:octo-org/octo-repo:ref:refs/heads/dev'", CLAIMS) is False
    # A case difference in the owner is a mismatch.
    assert evaluate("claims['sub'] eq 'repo:Octo-Org/octo-repo:ref:refs/heads/main'", CLAIMS) is False


def test_matches_star_is_multichar_and_not_path_aware() -> None:
    # '*' spans '/' and ':' -- so repo:octo-org/* admits every repo and ref in the org.
    assert evaluate("claims['sub'] matches 'repo:octo-org/*'", CLAIMS) is True
    assert evaluate("claims['sub'] matches 'repo:octo-org/octo-repo:ref:refs/heads/*'", CLAIMS) is True


def test_matches_is_anchored_not_a_substring() -> None:
    # The pattern must match the WHOLE claim: a bare 'main' does not match a full sub.
    assert evaluate("claims['sub'] matches 'main'", CLAIMS) is False
    # A leading wildcard is required to match a suffix.
    assert evaluate("claims['sub'] matches '*refs/heads/main'", CLAIMS) is True
    # An anchored prefix for a different repo does not match.
    assert evaluate("claims['sub'] matches 'repo:other-org/*'", CLAIMS) is False


def test_matches_question_is_exactly_one_character() -> None:
    assert evaluate("claims['sub'] matches 'repo:octo-org/octo-repo:ref:refs/heads/????'", CLAIMS) is True
    # 'main' is four characters; three '?' cannot match it, five cannot either.
    assert evaluate("claims['sub'] matches 'repo:octo-org/octo-repo:ref:refs/heads/???'", CLAIMS) is False
    assert evaluate("claims['sub'] matches 'repo:octo-org/octo-repo:ref:refs/heads/?????'", CLAIMS) is False


def test_matches_mixed_star_and_question() -> None:
    claims = {"sub": "repo:octo-org/octo-repo-42:ref:refs/heads/main"}
    assert evaluate("claims['sub'] matches 'repo:octo-org/octo-repo-*:ref:refs/heads/????'", claims) is True


def test_and_requires_every_clause() -> None:
    both = (
        f"claims['sub'] eq '{SUB}' and claims['job_workflow_ref'] matches "
        "'octo-org/reusable/.github/workflows/*@refs/heads/main'"
    )
    assert evaluate(both, CLAIMS) is True
    # Second clause fails (wrong ref) -> whole expression false.
    wrong = {**CLAIMS, "job_workflow_ref": "octo-org/reusable/.github/workflows/deploy.yml@refs/heads/dev"}
    assert evaluate(both, wrong) is False
    # First clause fails -> false, and the second clause is still parsed (no crash).
    assert evaluate(both, {**CLAIMS, "sub": "repo:octo-org/octo-repo:ref:refs/heads/dev"}) is False


def test_single_quote_escape_by_doubling() -> None:
    claims = {"sub": "value-with-a-'-quote"}
    assert evaluate("claims['sub'] eq 'value-with-a-''-quote'", claims) is True


def test_absent_claim_raises_not_false() -> None:
    with pytest.raises(FflError):
        evaluate("claims['environment'] eq 'prod'", CLAIMS)
    # An 'and' whose second clause references a missing claim raises even if the
    # first clause already determined falsity would be moot -- the clause is parsed
    # and evaluated, so the missing reference surfaces.
    with pytest.raises(FflError):
        evaluate(f"claims['sub'] eq '{SUB}' and claims['nope'] eq 'x'", CLAIMS)


def test_unknown_operator_raises() -> None:
    with pytest.raises(FflError):
        evaluate("claims['sub'] contains 'main'", CLAIMS)
    with pytest.raises(FflError):
        evaluate("claims['sub'] ne 'x'", CLAIMS)


def test_or_is_not_supported() -> None:
    # The language has only 'and'; 'or' must not be silently accepted.
    with pytest.raises(FflError):
        evaluate(f"claims['sub'] eq '{SUB}' or claims['sub'] eq 'x'", CLAIMS)


def test_parse_errors_raise() -> None:
    for bad in [
        "claims['sub'] eq",                       # missing comparand
        "claims['sub'] matches main",             # unquoted comparand
        "claims[sub] eq 'x'",                     # unquoted claim name
        "claims['sub'] eq 'x' claims['sub'] eq 'y'",  # two clauses, no 'and'
        "sub eq 'x'",                             # missing claims[...] lookup
        "",                                       # empty
    ]:
        with pytest.raises(FflError):
            evaluate(bad, CLAIMS)


def test_non_string_expression_raises() -> None:
    with pytest.raises(FflError):
        evaluate(["claims['sub'] eq 'x'"], CLAIMS)
