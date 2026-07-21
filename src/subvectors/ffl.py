"""A minimal evaluator for Azure Entra "flexible federated identity credential"
matching expressions -- the ``azure-fic-flexible`` consumer. PREVIEW feature.

Classic Azure FIC (azure-fic-exact) compares the token ``sub`` to a fixed string.
Flexible FIC replaces the ``subject`` property with a ``claimsMatchingExpression``
object ``{value, languageVersion}`` (the two are mutually exclusive; ``languageVersion``
is always ``1``). The credential is accepted iff ``value`` -- a restricted expression
in Microsoft's "flexible federated identity credential expression language" -- evaluates
to true over the token's claims. So the correctness oracle is a small expression
evaluator, not a string matcher.

Grammar (the whole language -- there is nothing else):

    expression := clause ( 'and' clause )*
    clause     := "claims['" NAME "']" SP operator SP "'" comparand "'"
    operator   := 'eq' | 'matches'

- ``claims['<name>']`` is the claim lookup; each part is separated by a single space.
- ``eq`` is exact, case-sensitive string equality against the named claim.
- ``matches`` is wildcard matching: ``?`` matches a single character, ``*`` matches
  multiple characters. Modeled here as an ANCHORED full-claim match (the entire claim
  value must match the pattern) -- every documented example is a full-subject pattern,
  and a substring match would make the control meaningless. ``*`` -> ``.*`` and ``?``
  -> ``.``, so like AWS StringLike the wildcards are not path-aware (they span ``/``
  and ``:``). Case sensitivity and zero-width ``*`` follow the classic-FIC / AWS
  reading where the preview doc is silent ("multi-character", not "zero or more").
- ``and`` is the only boolean combinator (no ``or``, no parentheses).
- Single quotes escape by doubling (``''`` -> a literal ``'``).

Per-issuer support (the token claims an expression may reference), from the same page:
GitHub -> ``sub`` and ``job_workflow_ref``; GitLab -> ``sub`` only; Terraform Cloud ->
``sub`` only. Flexible FIC is application-object-only and configurable via Microsoft
Graph or the Azure portal only (no CLI/PowerShell/Terraform provider surface yet).

Honest scope cut (as in cel.py): referencing a claim absent from ``claims`` raises
FflError rather than evaluating to false, so a vector can never pass by being
un-evaluated. This evaluator does NOT enforce the per-issuer claim/operator allow-list
(that is a configuration-validity concern, not a match-semantics one) or the
subject/claimsMatchingExpression mutual exclusion; it evaluates a well-formed
``value`` expression against a claim set.

Source (preview; page updated 2026-06-15):
https://learn.microsoft.com/en-us/entra/workload-id/workload-identities-flexible-federated-identity-credentials
"""

from __future__ import annotations

import re

__all__ = ["evaluate", "FflError"]


class FflError(ValueError):
    """Raised on a parse error, an unknown operator, or a reference to an absent claim."""


_TOKEN_RE = re.compile(
    r"(?P<ws>\s+)"
    r"|(?P<str>'(?:[^']|'')*')"
    r"|(?P<lbracket>\[)"
    r"|(?P<rbracket>\])"
    r"|(?P<ident>[A-Za-z_][A-Za-z0-9_]*)"
)

_OPERATORS = frozenset({"eq", "matches"})


def _tokenize(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if m is None:
            raise FflError(f"unexpected character at offset {pos}: {expr[pos:pos + 12]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        value = m.group()
        if kind == "str":
            value = value[1:-1].replace("''", "'")
        tokens.append((kind, value))
    return tokens


def _matches(value: str, pattern: str) -> bool:
    """``matches``: anchored, case-sensitive glob. ``*`` -> ``.*``, ``?`` -> ``.``."""
    out: list[str] = []
    for ch in pattern:
        if ch == "*":
            out.append(".*")
        elif ch == "?":
            out.append(".")
        else:
            out.append(re.escape(ch))
    return re.compile("".join(out)).fullmatch(value) is not None


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]], claims: dict, expr: str) -> None:
        self._toks = tokens
        self._claims = claims
        self._expr = expr
        self._i = 0

    def _peek(self) -> tuple[str | None, str | None]:
        return self._toks[self._i] if self._i < len(self._toks) else (None, None)

    def _advance(self) -> tuple[str | None, str | None]:
        tok = self._peek()
        self._i += 1
        return tok

    def parse(self) -> bool:
        result = self._clause()
        while True:
            k, v = self._peek()
            if k is None:
                break
            if k == "ident" and v == "and":
                self._advance()
                # Every clause is parsed (tokens consumed) before combining, so a
                # later invalid clause is a parse error, not silently short-circuited.
                clause_value = self._clause()
                result = result and clause_value
            else:
                raise FflError(f"expected 'and' or end of expression, got {v!r} in: {self._expr!r}")
        return result

    def _clause(self) -> bool:
        k, v = self._advance()
        if not (k == "ident" and v == "claims"):
            raise FflError(f"expected a claims[...] lookup, got {v!r}")
        k, _ = self._advance()
        if k != "lbracket":
            raise FflError("expected '[' after 'claims'")
        k, name = self._advance()
        if k != "str":
            raise FflError("expected a quoted claim name in claims['...']")
        k, _ = self._advance()
        if k != "rbracket":
            raise FflError("expected ']' after the claim name")
        k, op = self._advance()
        if k != "ident" or op not in _OPERATORS:
            raise FflError(f"unsupported operator {op!r}; expected 'eq' or 'matches'")
        k, comparand = self._advance()
        if k != "str":
            raise FflError(f"operator {op} expects a single-quoted comparand")
        if name not in self._claims:
            raise FflError(
                f"expression references claims['{name}'] but the token has no such claim"
            )
        value = self._claims[name]
        if op == "eq":
            return value == comparand
        return _matches(value, comparand)


def evaluate(expression: str, claims: dict) -> bool:
    """Evaluate a flexible-FIC ``claimsMatchingExpression`` value against a claim set.

    ``claims`` maps raw claim names to string values (addressable as
    ``claims['<name>']``). Returns the boolean admission decision. Raises
    :class:`FflError` on any parse error, unknown operator, or reference to a claim
    absent from ``claims``.
    """
    if not isinstance(expression, str):
        raise FflError("expression must be a string")
    tokens = _tokenize(expression)
    if not tokens:
        raise FflError("empty expression")
    return _Parser(tokens, claims, expression).parse()
