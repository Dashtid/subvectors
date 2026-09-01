"""Direct unit tests for the reference matcher's per-consumer semantics.

The vector corpus already exercises the matcher end-to-end; these pin the
individual operator rules so a regression names the exact broken semantic --
especially the AWS-vs-Azure contrast on the same '*' string, which is the whole
reason a shared corpus is worth maintaining.
"""

from __future__ import annotations

import pytest

from subvectors.matcher import SUPPORTED_CONSUMERS, UnsupportedConsumer, satisfies


def _cond(consumer: str, pattern: str) -> dict:
    return {"consumer": consumer, "pattern": pattern}


def test_aws_stringlike_star_is_multichar_and_not_path_aware() -> None:
    # '*' spans '/' and ':' -- this is why repo:org/* admits every repo in the org.
    assert satisfies(
        "repo:octo-org/any-repo:ref:refs/heads/main", _cond("aws-stringlike", "repo:octo-org/*")
    ) is True


def test_aws_stringlike_question_is_single_char() -> None:
    assert satisfies(
        "repo:o/r:ref:refs/heads/main", _cond("aws-stringlike", "repo:o/r:ref:refs/heads/mai?")
    ) is True
    assert satisfies(
        "repo:o/r:ref:refs/heads/ma", _cond("aws-stringlike", "repo:o/r:ref:refs/heads/mai?")
    ) is False


def test_aws_stringequals_treats_star_literally() -> None:
    assert satisfies(
        "repo:octo-org/repo:ref:refs/heads/main", _cond("aws-stringequals", "repo:octo-org/*")
    ) is False
    assert satisfies("repo:octo-org/*", _cond("aws-stringequals", "repo:octo-org/*")) is True


def test_azure_fic_exact_requires_exact_and_is_case_sensitive() -> None:
    pattern = "repo:octo-org/octo-repo:ref:refs/heads/main"
    assert satisfies(pattern, _cond("azure-fic-exact", pattern)) is True
    assert satisfies(
        "repo:Octo-Org/octo-repo:ref:refs/heads/main", _cond("azure-fic-exact", pattern)
    ) is False


def test_azure_fic_exact_has_no_wildcards_unlike_aws() -> None:
    # The same "repo:org/*" string is permissive on AWS StringLike but a literal
    # (matching nothing) on classic Azure FIC.
    star = "repo:octo-org/*"
    assert satisfies("repo:octo-org/any-repo:ref:refs/heads/main", _cond("aws-stringlike", star)) is True
    assert satisfies("repo:octo-org/any-repo:ref:refs/heads/main", _cond("azure-fic-exact", star)) is False


def test_unsupported_consumer_raises_not_returns_false() -> None:
    # A consumer the matcher doesn't implement must raise, never silently no-match.
    assert "aws-notarealoperator" not in SUPPORTED_CONSUMERS
    with pytest.raises(UnsupportedConsumer):
        satisfies("anything", _cond("aws-notarealoperator", "anything"))


def test_azure_fic_flexible_eq_is_exact_and_matches_is_anchored_glob() -> None:
    sub = "repo:octo-org/octo-repo:ref:refs/heads/main"
    assert satisfies(sub, _cond("azure-fic-flexible", f"claims['sub'] eq '{sub}'")) is True
    # matches is anchored: refs/heads/* admits any branch of this repo...
    assert satisfies(
        "repo:octo-org/octo-repo:ref:refs/heads/feature-x",
        _cond("azure-fic-flexible", "claims['sub'] matches 'repo:octo-org/octo-repo:ref:refs/heads/*'"),
    ) is True
    # ...but the literal prefix is anchored, so another repo does not match.
    assert satisfies(
        "repo:other-org/octo-repo:ref:refs/heads/main",
        _cond("azure-fic-flexible", "claims['sub'] matches 'repo:octo-org/octo-repo:ref:refs/heads/*'"),
    ) is False


def test_azure_fic_flexible_star_is_not_path_aware_like_aws() -> None:
    # The same over-broad wildcard that AWS StringLike honors and classic FIC treats
    # as a literal: flexible FIC's matches spans '/' and ':', so it is permissive.
    star = "claims['sub'] matches 'repo:octo-org/*'"
    assert satisfies("repo:octo-org/any-repo:ref:refs/heads/main", _cond("azure-fic-flexible", star)) is True


def test_azure_fic_flexible_question_is_fixed_width_single_char() -> None:
    pat = "claims['sub'] matches 'repo:octo-org/octo-repo:ref:refs/heads/????'"
    assert satisfies("repo:octo-org/octo-repo:ref:refs/heads/main", _cond("azure-fic-flexible", pat)) is True
    # 'master' is six characters -- the four '?' cannot match it (fails closed).
    assert satisfies("repo:octo-org/octo-repo:ref:refs/heads/master", _cond("azure-fic-flexible", pat)) is False


def test_azure_fic_flexible_and_requires_every_clause() -> None:
    sub = "repo:octo-org/octo-repo:ref:refs/heads/main"
    expr = (
        "claims['sub'] eq 'repo:octo-org/octo-repo:ref:refs/heads/main' "
        "and claims['job_workflow_ref'] matches "
        "'octo-org/reusable/.github/workflows/*@refs/heads/main'"
    )
    ok = {"sub": sub, "job_workflow_ref": "octo-org/reusable/.github/workflows/deploy.yml@refs/heads/main"}
    assert satisfies(sub, _cond("azure-fic-flexible", expr), claims=ok) is True
    # Same caller sub, but the reusable workflow ran on a different ref -> block fails.
    wrong = {"sub": sub, "job_workflow_ref": "octo-org/reusable/.github/workflows/deploy.yml@refs/heads/dev"}
    assert satisfies(sub, _cond("azure-fic-flexible", expr), claims=wrong) is False


def test_azure_fic_flexible_rejects_claim_targeting_and_list_pattern() -> None:
    # Claims are addressed inside the expression; a 'claim' key is meaningless, and
    # a list pattern (an AWS multi-value shape) is not part of this language.
    with pytest.raises(ValueError):
        satisfies("x", {"consumer": "azure-fic-flexible", "claim": "aud", "pattern": "claims['sub'] eq 'x'"},
                  claims={"sub": "x", "aud": "y"})
    with pytest.raises(ValueError):
        satisfies("x", {"consumer": "azure-fic-flexible", "pattern": ["a", "b"]})


def test_aws_multivalue_pattern_is_logical_or() -> None:
    # Multiple values for one condition key: the request value must match ANY one.
    values = [
        "repo:octo-org/repo-a:ref:refs/heads/main",
        "repo:octo-org/repo-b:ref:refs/heads/main",
    ]
    assert satisfies("repo:octo-org/repo-b:ref:refs/heads/main", _cond("aws-stringequals", values)) is True
    assert satisfies("repo:octo-org/repo-c:ref:refs/heads/main", _cond("aws-stringequals", values)) is False


def test_aws_multivalue_one_loose_value_poisons_the_list() -> None:
    # OR semantics mean the loosest value sets the effective trust boundary.
    values = ["repo:octo-org/repo-a:ref:refs/heads/main", "repo:octo-org/*"]
    assert satisfies("repo:octo-org/anything:pull_request", _cond("aws-stringlike", values)) is True


def test_condition_claim_resolves_from_claims_map() -> None:
    condition = {"consumer": "aws-stringequals", "claim": "aud", "pattern": "sts.amazonaws.com"}
    claims = {"sub": "repo:o/r:ref:refs/heads/main", "aud": "sts.amazonaws.com"}
    assert satisfies("repo:o/r:ref:refs/heads/main", condition, claims=claims) is True
    claims_wrong_aud = {"sub": "repo:o/r:ref:refs/heads/main", "aud": "https://example.test"}
    assert satisfies("repo:o/r:ref:refs/heads/main", condition, claims=claims_wrong_aud) is False


def test_condition_on_absent_claim_does_not_match() -> None:
    # AWS: a positive operator (no ...IfExists) on a context key missing from the
    # request evaluates to false -- it must not raise and must not match.
    condition = {"consumer": "aws-stringequals", "claim": "aud", "pattern": "sts.amazonaws.com"}
    assert satisfies("repo:o/r:ref:refs/heads/main", condition) is False


def test_list_pattern_raises_for_non_aws_consumers() -> None:
    # Only AWS documents multi-value conditions; a list on Azure or GCP is a
    # vector-authoring error and must fail loudly, never silently mis-match.
    with pytest.raises(ValueError):
        satisfies("repo:o/r:ref:refs/heads/main", _cond("azure-fic-exact", ["a", "b"]))
    with pytest.raises(ValueError):
        satisfies("repo:o/r:ref:refs/heads/main", _cond("gcp-cel", ["a", "b"]))


def test_list_pattern_raises_even_when_targeted_claim_is_absent() -> None:
    # The loud failure must not be masked by the absent-claim short circuit:
    # pattern-shape validation happens before claim resolution.
    condition = {"consumer": "azure-fic-exact", "claim": "aud", "pattern": ["a", "b"]}
    with pytest.raises(ValueError):
        satisfies("repo:o/r:ref:refs/heads/main", condition)


def test_gcp_cel_rejects_claim_targeting() -> None:
    # A CEL condition addresses claims inside the expression (assertion.<name>);
    # a 'claim' key on it would be silently meaningless, so it must raise.
    condition = {"consumer": "gcp-cel", "claim": "aud", "pattern": "assertion.sub == 'x'"}
    with pytest.raises(ValueError):
        satisfies("x", condition, claims={"sub": "x", "aud": "y"})


def test_claims_without_sub_is_seeded_from_subject() -> None:
    # A claims map lacking 'sub' must not shadow the subject argument: the
    # default sub condition still matches against 'subject'.
    condition = {"consumer": "aws-stringequals", "pattern": "repo:o/r:ref:refs/heads/main"}
    assert satisfies(
        "repo:o/r:ref:refs/heads/main", condition, claims={"aud": "sts.amazonaws.com"}
    ) is True


def _aud_and_sub(sub_pattern: str, sub_consumer: str = "aws-stringequals") -> dict:
    return {
        "consumer": "aws-all",
        "of": [
            {"consumer": "aws-stringequals", "claim": "aud", "pattern": "sts.amazonaws.com"},
            {"consumer": sub_consumer, "claim": "sub", "pattern": sub_pattern},
        ],
    }


def test_aws_all_requires_every_subcondition() -> None:
    # A Condition block is an AND: all context keys must resolve to true.
    subject = "repo:o/r:ref:refs/heads/main"
    condition = _aud_and_sub(subject)
    assert satisfies(subject, condition, claims={"sub": subject, "aud": "sts.amazonaws.com"}) is True
    # Right sub, wrong aud -> the block fails.
    assert satisfies(subject, condition, claims={"sub": subject, "aud": "https://github.com/o"}) is False
    # Right aud, wrong sub -> the block fails.
    assert satisfies(
        "repo:o/other:ref:refs/heads/main",
        condition,
        claims={"sub": "repo:o/other:ref:refs/heads/main", "aud": "sts.amazonaws.com"},
    ) is False


def test_aws_all_mixes_operators_and_value_lists() -> None:
    # StringEquals for aud alongside StringLike for sub (the documented AWS shape),
    # with values-OR list semantics still available inside the block.
    subject = "repo:o/r:pull_request"
    condition = _aud_and_sub("repo:o/r:*", sub_consumer="aws-stringlike")
    assert satisfies(subject, condition, claims={"sub": subject, "aud": "sts.amazonaws.com"}) is True
    listed = {
        "consumer": "aws-all",
        "of": [
            {"consumer": "aws-stringequals", "claim": "aud", "pattern": "sts.amazonaws.com"},
            {"consumer": "aws-stringequals", "claim": "sub", "pattern": ["repo:o/a:ref:refs/heads/main", "repo:o/b:ref:refs/heads/main"]},
        ],
    }
    assert satisfies(
        "repo:o/b:ref:refs/heads/main",
        listed,
        claims={"sub": "repo:o/b:ref:refs/heads/main", "aud": "sts.amazonaws.com"},
    ) is True


def test_aws_all_rejects_non_aws_subconditions() -> None:
    condition = {
        "consumer": "aws-all",
        "of": [
            {"consumer": "aws-stringequals", "claim": "sub", "pattern": "x"},
            {"consumer": "azure-fic-exact", "claim": "sub", "pattern": "x"},
        ],
    }
    with pytest.raises(ValueError):
        satisfies("x", condition)


def test_aws_all_rejects_non_aws_even_after_a_failing_subcondition() -> None:
    # The guard must validate the WHOLE block before evaluating any of it: a
    # failing first entry must not short-circuit past the invalid azure entry
    # (all() would return False and silently mask the authoring error).
    condition = {
        "consumer": "aws-all",
        "of": [
            {"consumer": "aws-stringequals", "claim": "sub", "pattern": "NOT-x"},
            {"consumer": "azure-fic-exact", "claim": "sub", "pattern": "x"},
        ],
    }
    with pytest.raises(ValueError):
        satisfies("x", condition)


# --- AWS set operators (ForAllValues / ForAnyValue) -----------------------
#
# The security story is entirely in the empty-set case. AWS: ForAllValues "also
# returns true if there are no context keys in the request"; ForAnyValue returns
# false "if the key does not exist". Same policy intent, same token, opposite
# verdict -- so on any claim a token may omit, the qualifier alone decides
# whether an Allow fails open or closed.

_ENV_ALL = {
    "consumer": "aws-stringequals",
    "claim": "environment",
    "qualifier": "ForAllValues",
    "pattern": "Production",
}
_ENV_ANY = {**_ENV_ALL, "qualifier": "ForAnyValue"}
_SUBJECT = "repo:octo-org/octo-repo:ref:refs/heads/main"


def test_forallvalues_passes_vacuously_when_the_claim_is_absent():
    """The fail-open, pinned. This is the whole finding."""
    assert satisfies(_SUBJECT, _ENV_ALL, {"sub": _SUBJECT}) is True


def test_foranyvalue_fails_closed_when_the_claim_is_absent():
    assert satisfies(_SUBJECT, _ENV_ANY, {"sub": _SUBJECT}) is False


def test_plain_operator_fails_closed_on_the_same_absent_claim():
    """Without a qualifier an absent key is a mismatch -- the contrast that matters."""
    plain = {"consumer": "aws-stringequals", "claim": "environment", "pattern": "Production"}
    assert satisfies(_SUBJECT, plain, {"sub": _SUBJECT}) is False


def test_both_qualifiers_agree_when_the_claim_is_present_and_listed():
    claims = {"sub": _SUBJECT, "environment": "Production"}
    assert satisfies(_SUBJECT, _ENV_ALL, claims) is True
    assert satisfies(_SUBJECT, _ENV_ANY, claims) is True


def test_both_qualifiers_agree_when_the_claim_is_present_and_unlisted():
    claims = {"sub": _SUBJECT, "environment": "Sandbox"}
    assert satisfies(_SUBJECT, _ENV_ALL, claims) is False
    assert satisfies(_SUBJECT, _ENV_ANY, claims) is False


def test_a_qualifier_does_not_tighten_a_policy_value_list():
    """The misreading: the qualifier ranges over REQUEST values, not policy values.

    A poisoned OR-list stays poisoned under either qualifier -- the loosest value
    still sets the boundary.
    """
    poisoned = [_SUBJECT, "repo:octo-org/*"]
    for qualifier in ("ForAllValues", "ForAnyValue"):
        condition = {"consumer": "aws-stringlike", "qualifier": qualifier, "pattern": poisoned}
        assert satisfies("repo:octo-org/anything:pull_request", condition) is True


def test_forallvalues_requires_every_request_value_to_match():
    """Proper set semantics for a genuinely multivalued request context key."""
    condition = {
        "consumer": "aws-stringequals",
        "claim": "groups",
        "qualifier": "ForAllValues",
        "pattern": ["a", "b"],
    }
    assert satisfies(_SUBJECT, condition, {"sub": _SUBJECT, "groups": ["a", "b"]}) is True
    assert satisfies(_SUBJECT, condition, {"sub": _SUBJECT, "groups": ["a"]}) is True
    assert satisfies(_SUBJECT, condition, {"sub": _SUBJECT, "groups": ["a", "c"]}) is False


def test_foranyvalue_requires_one_request_value_to_match():
    condition = {
        "consumer": "aws-stringequals",
        "claim": "groups",
        "qualifier": "ForAnyValue",
        "pattern": ["a", "b"],
    }
    assert satisfies(_SUBJECT, condition, {"sub": _SUBJECT, "groups": ["a", "c"]}) is True
    assert satisfies(_SUBJECT, condition, {"sub": _SUBJECT, "groups": ["c", "d"]}) is False


def test_qualifier_on_a_non_aws_consumer_is_rejected():
    """Only IAM has set semantics; anything else is a vector-authoring error."""
    condition = {"consumer": "azure-fic-exact", "qualifier": "ForAllValues", "pattern": "x"}
    with pytest.raises(ValueError, match="set semantics"):
        satisfies(_SUBJECT, condition)


def test_unknown_qualifier_is_rejected():
    condition = {"consumer": "aws-stringequals", "qualifier": "ForSomeValues", "pattern": "x"}
    with pytest.raises(ValueError, match="unknown qualifier"):
        satisfies(_SUBJECT, condition)


def test_an_absent_claim_clause_contributes_nothing_to_an_and_block():
    """A ForAllValues clause cannot strengthen an aws-all block on an absent claim."""
    condition = {
        "consumer": "aws-all",
        "of": [
            {"consumer": "aws-stringequals", "claim": "aud", "pattern": "sts.amazonaws.com"},
            _ENV_ALL,
        ],
    }
    claims = {"sub": _SUBJECT, "aud": "sts.amazonaws.com"}
    assert satisfies(_SUBJECT, condition, claims) is True
