"""A minimal CEL evaluator for GCP Workload Identity Federation attribute_conditions.

GCP does not string-match the token subject. A workload-identity-pool provider carries
an ``attribute_condition`` written in CEL (Common Expression Language); the credential is
accepted iff that expression evaluates to ``true`` over the token's claims. So the
correctness oracle for the ``gcp-cel`` consumer is a CEL evaluator, not a string matcher.

This implements the small, security-relevant subset of CEL that realistic GitHub -> GCP
attribute_conditions use, and nothing more (see the "not implemented" note below). The token
claims are exposed under the ``assertion`` namespace by dot notation, e.g.
``assertion.repository_owner_id == '1342004'``.

Semantics that are easy to get wrong, pinned to primary sources:
- The condition is the accept/reject gate: true = accepted, false = rejected.
  https://docs.cloud.google.com/iam/docs/workload-identity-federation
- ``matches(re)`` is RE2 and matches a SUBSTRING (unanchored) -- so it uses re.search, and a
  pattern must use ^ / $ to anchor. https://github.com/google/cel-spec/blob/master/doc/langdef.md
- Values are strings (even numeric IDs like repository_id are quoted strings); comparisons are
  byte-exact and case-sensitive.

Honest scope cut: referencing a claim absent from ``claims`` raises CelError rather than
evaluating to false, keeping the oracle honest (a vector can never pass by being un-evaluated).
CEL's production error-absorption through commutative logic is only partially reproduced (via
Python short-circuit); vectors must supply every claim on an evaluated path.

Not implemented (deliberately -- not used in these conditions, and building them would imply
support we do not verify): ordering comparisons < <= > >=, ternary ?:, string concatenation,
arithmetic, timestamps, macros (.all/.exists/.map/.filter), and the extract()/split() extensions
that appear in attribute_MAPPING source expressions rather than admission conditions.
"""

from __future__ import annotations

import re

__all__ = ["evaluate", "CelError"]


class CelError(ValueError):
    """Raised on a parse error, an unknown function, or a reference to an absent claim."""


_TOKEN_RE = re.compile(
    r"(?P<ws>\s+)"
    r"|(?P<str>'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"
    r"|(?P<op>==|!=|&&|\|\||!|\(|\)|\[|\]|,|\.)"
    r"|(?P<ident>[A-Za-z_][A-Za-z0-9_]*)"
)

_STRING_METHODS = frozenset({"startsWith", "endsWith", "contains", "matches"})


def _unescape(literal: str) -> str:
    body = literal[1:-1]
    return body.replace("\\\\", "\\").replace("\\'", "'").replace('\\"', '"')


def _tokenize(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if m is None:
            raise CelError(f"unexpected character at offset {pos}: {expr[pos:pos + 12]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        value = m.group()
        tokens.append((kind, _unescape(value) if kind == "str" else value))
    return tokens


class _Parser:
    """Recursive-descent parser. Precedence (loosest -> tightest): || , && , (== != in) , ! ,
    member/method access."""

    def __init__(self, tokens: list[tuple[str, str]], expr: str) -> None:
        self._toks = tokens
        self._expr = expr
        self._i = 0

    def _peek(self) -> tuple[str | None, str | None]:
        return self._toks[self._i] if self._i < len(self._toks) else (None, None)

    def _advance(self) -> tuple[str | None, str | None]:
        tok = self._peek()
        self._i += 1
        return tok

    def _at_op(self, value: str) -> bool:
        k, v = self._peek()
        return k == "op" and v == value

    def parse(self):
        node = self._parse_or()
        if self._i != len(self._toks):
            raise CelError(f"unexpected trailing tokens in: {self._expr!r}")
        return node

    def _parse_or(self):
        node = self._parse_and()
        while self._at_op("||"):
            self._advance()
            node = ("or", node, self._parse_and())
        return node

    def _parse_and(self):
        node = self._parse_relation()
        while self._at_op("&&"):
            self._advance()
            node = ("and", node, self._parse_relation())
        return node

    def _parse_relation(self):
        left = self._parse_unary()
        k, v = self._peek()
        if k == "op" and v in ("==", "!="):
            self._advance()
            return (v, left, self._parse_unary())
        if k == "ident" and v == "in":
            self._advance()
            return ("in", left, self._parse_list())
        return left

    def _parse_unary(self):
        if self._at_op("!"):
            self._advance()
            return ("not", self._parse_unary())
        return self._parse_operand()

    def _parse_operand(self):
        node = self._parse_primary()
        while self._at_op("."):
            self._advance()
            k, name = self._advance()
            if k != "ident":
                raise CelError("expected a method name after '.'")
            if not self._at_op("("):
                raise CelError(f"unsupported field access .{name} (only method calls follow a value)")
            self._advance()  # (
            ak, arg = self._advance()
            if ak != "str":
                raise CelError(f"method {name}() expects a single string-literal argument")
            if not self._at_op(")"):
                raise CelError(f"expected ')' to close {name}(...)")
            self._advance()  # )
            node = ("method", node, name, ("str", arg))
        return node

    def _parse_primary(self):
        k, v = self._peek()
        if k == "ident" and v == "assertion":
            self._advance()
            if not self._at_op("."):
                raise CelError("expected '.<claim>' after 'assertion'")
            self._advance()
            ck, claim = self._advance()
            if ck != "ident":
                raise CelError("expected a claim name after 'assertion.'")
            return ("claim", claim)
        if k == "str":
            self._advance()
            return ("str", v)
        if k == "ident" and v in ("true", "false"):
            self._advance()
            return ("bool", v == "true")
        if k == "op" and v == "(":
            self._advance()
            node = self._parse_or()
            if not self._at_op(")"):
                raise CelError("expected ')'")
            self._advance()
            return node
        raise CelError(f"unexpected token {v!r} in: {self._expr!r}")

    def _parse_list(self):
        if not self._at_op("["):
            raise CelError("expected '[' after 'in'")
        self._advance()
        items = []
        if not self._at_op("]"):
            while True:
                ik, iv = self._advance()
                if ik != "str":
                    raise CelError("list literals may contain only string literals")
                items.append(("str", iv))
                if self._at_op(","):
                    self._advance()
                    continue
                break
        if not self._at_op("]"):
            raise CelError("expected ']'")
        self._advance()
        return items


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    raise CelError(f"expected a boolean in a logical position, got {type(value).__name__}: {value!r}")


def _method(name: str, receiver, arg) -> bool:
    if name not in _STRING_METHODS:
        raise CelError(f"unsupported function {name}()")
    if not isinstance(receiver, str) or not isinstance(arg, str):
        raise CelError(f"{name}() operates on strings")
    if name == "startsWith":
        return receiver.startswith(arg)
    if name == "endsWith":
        return receiver.endswith(arg)
    if name == "contains":
        return arg in receiver
    # matches(): RE2, substring semantics -> re.search, not fullmatch.
    try:
        return re.search(arg, receiver) is not None
    except re.error as exc:
        raise CelError(f"invalid regex in matches(): {exc}") from exc


def _eval(node, claims: dict) -> object:
    kind = node[0]
    if kind == "str":
        return node[1]
    if kind == "bool":
        return node[1]
    if kind == "claim":
        name = node[1]
        if name not in claims:
            raise CelError(
                f"condition references assertion.{name} but the token has no such claim"
            )
        return claims[name]
    if kind == "not":
        return not _as_bool(_eval(node[1], claims))
    if kind == "and":
        return _as_bool(_eval(node[1], claims)) and _as_bool(_eval(node[2], claims))
    if kind == "or":
        return _as_bool(_eval(node[1], claims)) or _as_bool(_eval(node[2], claims))
    if kind in ("==", "!="):
        equal = _eval(node[1], claims) == _eval(node[2], claims)
        return equal if kind == "==" else not equal
    if kind == "in":
        needle = _eval(node[1], claims)
        return needle in [_eval(item, claims) for item in node[2]]
    if kind == "method":
        return _method(node[2], _eval(node[1], claims), _eval(node[3], claims))
    raise CelError(f"internal: unknown node {kind!r}")


def evaluate(expression: str, claims: dict) -> bool:
    """Evaluate a GCP WIF ``attribute_condition`` CEL expression against a token's claims.

    ``claims`` maps raw claim names to string values (addressable as ``assertion.<name>``).
    Returns the boolean admission decision. Raises :class:`CelError` on any parse error,
    unknown function, non-boolean result, or reference to a claim absent from ``claims``.
    """
    if not isinstance(expression, str):
        raise CelError("expression must be a string")
    tokens = _tokenize(expression)
    if not tokens:
        raise CelError("empty expression")
    ast = _Parser(tokens, expression).parse()
    return _as_bool(_eval(ast, claims))
