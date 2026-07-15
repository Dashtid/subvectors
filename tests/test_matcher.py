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
    assert "azure-fic-flexible" not in SUPPORTED_CONSUMERS
    with pytest.raises(UnsupportedConsumer):
        satisfies("anything", _cond("azure-fic-flexible", "anything"))
