"""Reference matcher for OIDC CI/CD trust-condition conformance vectors.

Correctness oracle only. Given an OIDC token *subject* (a concrete claim value
minted by an issuer) and a cloud consumer's trust *condition* (an admin-written
matching rule), decide whether the subject satisfies the condition. It answers
exactly one question: does subject S satisfy condition C?

It deliberately does NOT judge whether C is *safe*. That grade is human-authored
in each vector's ``judgment`` block, backed by a citation, and this matcher never
reads it. Keeping the two apart is the point: the match is mechanically
falsifiable; the safety grade is a documented claim.

Scope: the AWS consumers (StringLike / StringEquals), classic Azure FIC (exact match),
and GCP Workload Identity Federation (CEL attribute_condition, evaluated by cel.py). The
preview "flexible FIC" expression language (azure-fic-flexible) is declared in the vector
schema and lands in a later tranche; an unsupported consumer raises rather than silently
returning False, so a vector can never pass by being unmatched.

AWS conditions may target a claim other than ``sub`` (``condition["claim"]``, e.g. ``aud``)
and may carry a LIST of pattern values: IAM evaluates multiple values for one condition key
with logical OR, and a condition on a context key absent from the request does not match
(for positive operators without ``...IfExists``). Both behaviors are AWS-specific; the Azure
and GCP consumers reject list patterns rather than guessing semantics.

Sources:
- AWS IAM condition operators (StringEquals / StringLike, wildcard semantics):
  https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html
- AWS multi-value conditions (multiple values for one key = logical OR):
  https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-logic-multiple-context-keys-or-values.html
- AWS missing context keys ("A context key that is not present in the request is
  considered a mismatch"):
  https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition.html
- Azure FIC subject matching (exact, no wildcards, silent failure on mismatch):
  https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-considerations
- GCP WIF attribute_condition (CEL accept/reject gate): see src/subvectors/cel.py
"""

from __future__ import annotations

import re
from typing import Callable

from . import cel

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

    Wording caveat: AWS phrases ``*`` as a "multi-character match wildcard" /
    "any combination of characters" and never says "zero or more" verbatim;
    zero-width matching (``main*`` matching ``main``) is the standard reading of
    "any combination", encoded here and flagged in the corresponding vector.
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


def _azure_fic_exact(subject: str, pattern: str) -> bool:
    # Classic Azure federated identity credentials compare the configured
    # subject to the token's sub with an EXACT string match. Wildcards are not
    # supported in any FIC property value -- "*" is a literal character, so a
    # subject like "repo:org/*" matches no real token and the exchange fails
    # SILENTLY, with no error. (Wildcard/expression matching is a separate,
    # preview-only "flexible FIC" consumer -- azure-fic-flexible, not yet here.)
    return subject == pattern


_CONSUMERS: dict[str, Callable[[str, str], bool]] = {
    "aws-stringlike": _aws_stringlike,
    "aws-stringequals": _aws_stringequals,
    "azure-fic-exact": _azure_fic_exact,
}

# Only AWS documents list-valued conditions (logical OR across the values). A list
# pattern on any other consumer is a vector-authoring error and must fail loudly.
_LIST_PATTERN_CONSUMERS = frozenset({"aws-stringlike", "aws-stringequals"})

# gcp-cel is handled separately (it needs the full claim set, not just the subject).
SUPPORTED_CONSUMERS = frozenset(_CONSUMERS) | {"gcp-cel"}


def satisfies(subject: str, condition: dict, claims: dict | None = None) -> bool:
    """Return True iff ``subject`` satisfies ``condition``.

    ``condition`` is a vector's condition block: at minimum a ``consumer`` key
    (which matching semantics to apply) and a ``pattern`` (the admin-written rule).

    String consumers (AWS, Azure) match one claim value: ``condition["claim"]``
    names the targeted claim (default ``sub``), resolved from ``claims``. When
    ``claims`` is omitted it defaults to ``{"sub": subject}``, so subject-only
    vectors and existing callers are unaffected. A condition targeting a claim
    absent from the token does NOT match (AWS: a positive operator without
    ``...IfExists`` on a missing context key evaluates to false).

    For the AWS consumers, ``pattern`` may be a list of values: IAM evaluates
    multiple values for a single condition key with logical OR, so ONE
    over-permissive value admits everything it matches regardless of how tight
    the other values are.

    The ``gcp-cel`` consumer evaluates ``pattern`` as a CEL attribute_condition
    over the full ``claims`` set.
    """
    consumer = condition["consumer"]
    if claims is None:
        claims = {"sub": subject}
    pattern = condition["pattern"]
    if consumer == "gcp-cel":
        if not isinstance(pattern, str):
            raise ValueError(
                f"consumer {consumer!r} takes a single CEL expression string, "
                f"got {type(pattern).__name__}"
            )
        return cel.evaluate(pattern, claims)
    try:
        match_fn = _CONSUMERS[consumer]
    except KeyError as exc:
        raise UnsupportedConsumer(
            f"consumer {consumer!r} is declared in the schema but not yet "
            f"implemented; supported: {sorted(SUPPORTED_CONSUMERS)}"
        ) from exc
    value = claims.get(condition.get("claim", "sub"))
    if value is None:
        return False
    if isinstance(pattern, str):
        return match_fn(value, pattern)
    if consumer not in _LIST_PATTERN_CONSUMERS:
        raise ValueError(
            f"consumer {consumer!r} matches a single string; list patterns are "
            f"only defined for AWS conditions (logical OR)"
        )
    return any(match_fn(value, p) for p in pattern)
