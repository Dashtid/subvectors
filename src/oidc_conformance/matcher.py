"""Reference matcher for OIDC CI/CD trust-condition conformance vectors.

Correctness oracle only. Given an OIDC token *subject* (a concrete claim value
minted by an issuer) and a cloud consumer's trust *condition* (an admin-written
matching rule), decide whether the subject satisfies the condition. It answers
exactly one question: does subject S satisfy condition C?

It deliberately does NOT judge whether C is *safe*. That grade is human-authored
in each vector's ``judgment`` block, backed by a citation, and this matcher never
reads it. Keeping the two apart is the point: the match is mechanically
falsifiable; the safety grade is a documented claim.

Scope (v0.1): the AWS consumers. Azure FIC and GCP CEL are declared in the vector
schema and land in later tranches; an unsupported consumer raises rather than
silently returning False, so a vector can never pass by being unmatched.

Sources:
- AWS IAM condition operators (StringEquals / StringLike, wildcard semantics):
  https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html
"""

from __future__ import annotations

import re
from typing import Callable

__all__ = ["satisfies", "UnsupportedConsumer", "SUPPORTED_CONSUMERS"]


class UnsupportedConsumer(ValueError):
    """Raised when a vector names a consumer this matcher does not implement."""


def _stringlike_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile an AWS IAM ``StringLike`` pattern to an anchored regex.

    IAM ``StringLike`` recognizes two wildcards and nothing else:
      ``*`` matches zero or more characters,
      ``?`` matches exactly one character.
    Every other character is literal, and matching is case-sensitive. Crucially,
    the wildcards are NOT path-aware: ``*`` also spans ``/`` and ``:``, which is
    exactly why ``repo:org/*`` admits every repository in an org.
    """
    out: list[str] = []
    for ch in pattern:
        if ch == "*":
            out.append(".*")
        elif ch == "?":
            out.append(".")
        else:
            out.append(re.escape(ch))
    return re.compile("".join(out))


def _aws_stringlike(subject: str, pattern: str) -> bool:
    return _stringlike_to_regex(pattern).fullmatch(subject) is not None


def _aws_stringequals(subject: str, pattern: str) -> bool:
    # Exact, case-sensitive equality. ``*`` and ``?`` are literal here -- a
    # StringEquals condition of "repo:org/*" matches only the literal string
    # "repo:org/*", never a real subject.
    return subject == pattern


_CONSUMERS: dict[str, Callable[[str, str], bool]] = {
    "aws-stringlike": _aws_stringlike,
    "aws-stringequals": _aws_stringequals,
}

SUPPORTED_CONSUMERS = frozenset(_CONSUMERS)


def satisfies(subject: str, condition: dict) -> bool:
    """Return True iff ``subject`` satisfies ``condition``.

    ``condition`` is a vector's condition block: at minimum a ``consumer`` key
    (which matching semantics to apply) and a ``pattern`` (the admin-written
    rule). The optional ``claim`` key records which token claim the condition
    targets (default ``sub``) and does not affect matching in v0.1.
    """
    consumer = condition["consumer"]
    try:
        match_fn = _CONSUMERS[consumer]
    except KeyError as exc:
        raise UnsupportedConsumer(
            f"consumer {consumer!r} is declared in the schema but not yet "
            f"implemented; supported: {sorted(SUPPORTED_CONSUMERS)}"
        ) from exc
    return match_fn(subject, condition["pattern"])
