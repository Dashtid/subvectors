r"""A minimal CEL evaluator for GCP Workload Identity Federation attribute_conditions.

GCP does not string-match the token subject. A workload-identity-pool provider carries
an ``attribute_condition`` written in CEL (Common Expression Language); the credential is
accepted iff that expression evaluates to ``true`` over the token's claims. So the
correctness oracle for the ``gcp-cel`` consumer is a CEL evaluator, not a string matcher.

This implements the small, security-relevant subset of CEL that realistic GitHub -> GCP
attribute_conditions use, and nothing more (see the "not implemented" note below). The token
claims are exposed under the ``assertion`` namespace by dot notation, e.g.
``assertion.repository_owner_id == '1342004'``. A claim whose NAME is not a valid identifier
(dots or slashes, e.g. CircleCI's ``oidc.circleci.com/project-id``) is addressed by CEL map
indexing instead: ``assertion['oidc.circleci.com/project-id'] == '...'``.

Semantics that are easy to get wrong, pinned to primary sources:
- The condition is the accept/reject gate: true = accepted, false = rejected.
  https://docs.cloud.google.com/iam/docs/workload-identity-federation
- ``matches(re)`` is RE2 and matches a SUBSTRING (unanchored) -- so it uses re.search, and a
  pattern must use ^ / $ to anchor. https://github.com/google/cel-spec/blob/master/doc/langdef.md
- String literals follow the spec's ESCAPE production exactly, decoded in a single
  left-to-right pass. This matters more than it looks: a double quote needs no escape
  inside a single-quoted string, so a literal holding backslash-backslash-quote is
  legal -- and decoding it by sequential replacement lost the backslash outright until
  2026-09-02. An invalid escape such as ``\q`` is a parse error, as it is in CEL.
  ``r``-prefixed raw literals are supported (the idiomatic way to write a regex inside
  ``matches()``); the backslash is an ordinary character in them.
  https://github.com/google/cel-spec/blob/master/doc/langdef.md
- Token claim values relevant here are strings (issuers mint even numeric IDs and protection
  flags as quoted JSON strings, e.g. GitLab's "project_id": "20", "ref_protected": "false"),
  and the CEL JSON mapping keeps a JSON string a CEL string
  (langdef.md#json-data-conversion); comparisons are byte-exact and case-sensitive.
- Equality across types is CEL "heterogeneous equality": numeric types compare
  mathematically, and any other cross-type comparison is FALSE -- never an error
  (langdef.md#equality, the ``: false`` branch of the spec's own pseudo-code). So
  ``assertion.project_id == 20`` is false when the claim is the string "20", and the negation
  ``!= 20`` is true for EVERY string value -- the type-level trap the gitlab-gcp vectors pin.
  Python quirk guarded explicitly: bool is an int subclass in Python, but CEL bool is not a
  numeric type, so ``true == 1`` must not fall through to Python's ``True == 1``.

Honest scope cut: referencing a claim absent from ``claims`` raises CelError rather than
evaluating to false, keeping the oracle honest (a vector can never pass by being un-evaluated).
CEL's production error-absorption through commutative logic is only partially reproduced (via
Python short-circuit); vectors must supply every claim on an evaluated path.

Not implemented (deliberately -- not used in these conditions, and building them would imply
support we do not verify): ordering comparisons < <= > >=, ternary ?:, string concatenation,
arithmetic, timestamps, uint/double literals (int literals exist solely so the type-trap
vectors can express the mistaken ``== 20`` form), macros (.all/.exists/.map/.filter), and the
extract()/split() extensions that appear in attribute_MAPPING source expressions rather than
admission conditions, and the triple-quoted and ``b``-prefixed bytes STRING_LIT forms (both
are detected and refused by name rather than misread).
"""

from __future__ import annotations

import re

__all__ = ["CelError", "evaluate"]


class CelError(ValueError):
    """Raised on a parse error, an unknown function, or a reference to an absent claim."""


# Raw (``r``-prefixed) alternatives come FIRST so ``r'x'`` tokenizes as one raw
# string rather than the identifier ``r`` followed by a string. A raw literal has
# no escape rule at all -- per STRING_LIT its body is "any character except the
# delimiter, CR or LF" -- so a backslash inside one cannot escape the closing
# quote, and the alternatives are written to say exactly that.
_TOKEN_RE = re.compile(
    r"(?P<ws>\s+)"
    r"|(?P<str>[rR]'[^'\r\n]*'"
    r"|[rR]\"[^\"\r\n]*\""
    r"|'(?:[^'\\\r\n]|\\.)*'"
    r"|\"(?:[^\"\\\r\n]|\\.)*\")"
    r"|(?P<num>\d+)"
    r"|(?P<op>==|!=|&&|\|\||!|\(|\)|\[|\]|,|\.)"
    r"|(?P<ident>[A-Za-z_][A-Za-z0-9_]*)"
)

# Both are real STRING_LIT forms this oracle deliberately refuses. Detected before
# tokenizing so they get a named refusal: without this, a triple-quoted literal
# shreds into an empty string plus an identifier and surfaces as "unexpected
# trailing tokens", which describes the symptom and not the cause.
_TRIPLE_QUOTED_RE = re.compile(r"[rRbB]{0,2}(?:'''|\"\"\")")
_BYTES_LIT_RE = re.compile(r"(?:[bB][rR]?|[rR][bB])['\"]")

_STRING_METHODS = frozenset({"startsWith", "endsWith", "contains", "matches"})

# ESCAPE, first alternative: the punctuation marks and whitespace codes that stand
# for themselves or for a control character.
# fmt: off
# Two rows, one per escape family, so the table reads against the CEL grammar.
# The formatter would put each of the twelve entries on a line of its own.
_SIMPLE_ESCAPES = {
    "a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v",
    "\\": "\\", "?": "?", '"': '"', "'": "'", "`": "`",
}
# fmt: on
_HEXDIGITS = frozenset("0123456789abcdefABCDEF")
_OCTDIGITS = frozenset("01234567")


def _decode_codepoint(body: str, start: int, count: int, base: int, literal: str) -> str:
    """Read a fixed-width numeric escape and return the character it names."""
    digits = body[start : start + count]
    allowed = _HEXDIGITS if base == 16 else _OCTDIGITS
    if len(digits) != count or any(d not in allowed for d in digits):
        raise CelError(
            f"malformed numeric escape in string literal {literal!r}: "
            f"expected {count} base-{base} digits, got {digits!r}"
        )
    value = int(digits, base)
    # \U can name a value above the Unicode range, and CEL strings are sequences
    # of code points -- so that is a parse error too, not a silent replacement char.
    if value > 0x10FFFF:
        raise CelError(f"escape names a value outside Unicode in {literal!r}: {digits!r}")
    return chr(value)


def _unescape(literal: str) -> str:
    r"""Decode a CEL string literal, scanning it once, left to right.

    Scanning is not a style preference here. The previous implementation ran three
    sequential ``str.replace`` passes, and a later pass could consume a backslash an
    earlier one had just produced. A double quote needs no escape inside a
    single-quoted string, so a literal holding backslash-backslash-quote is legal and
    means backslash-quote; replacing ``\\`` first produced backslash-quote, which the
    later ``\"`` pass then ate, silently returning a bare quote. A single pass cannot
    re-read its own output.

    Raises CelError on any invalid escape, matching CEL, where "a backslash outside
    of a valid escape sequence ... will result in a parse error". Accepting one would
    let this oracle evaluate an expression that GCP itself would refuse to save.
    """
    if literal[0] in "rR":
        # Raw literal: the backslash is an ordinary character. No decoding at all.
        return literal[2:-1]
    body = literal[1:-1]
    out: list[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= len(body):
            raise CelError(f"string literal ends with a dangling backslash: {literal!r}")
        code = body[i + 1]
        if code in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[code])
            i += 2
        elif code in "xX":
            out.append(_decode_codepoint(body, i + 2, 2, 16, literal))
            i += 4
        elif code == "u":
            out.append(_decode_codepoint(body, i + 2, 4, 16, literal))
            i += 6
        elif code == "U":
            out.append(_decode_codepoint(body, i + 2, 8, 16, literal))
            i += 10
        elif code in "0123":
            # Octal is three digits INCLUDING the leading one, range 000-377.
            out.append(_decode_codepoint(body, i + 1, 3, 8, literal))
            i += 4
        else:
            raise CelError(f"invalid escape sequence \\{code} in string literal {literal!r}")
    return "".join(out)


def _tokenize(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(expr):
        if _TRIPLE_QUOTED_RE.match(expr, pos):
            raise CelError(
                "triple-quoted string literals are not supported: an attribute_condition "
                "is a single-line field and no realistic one uses them"
            )
        if _BYTES_LIT_RE.match(expr, pos):
            raise CelError(
                "bytes literals (b'...') are not supported: bytes is a distinct CEL type "
                "and these conditions compare string claims"
            )
        m = _TOKEN_RE.match(expr, pos)
        if m is None:
            raise CelError(f"unexpected character at offset {pos}: {expr[pos : pos + 12]!r}")
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
                raise CelError(
                    f"unsupported field access .{name} (only method calls follow a value)"
                )
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
            if self._at_op("."):
                self._advance()
                ck, claim = self._advance()
                if ck != "ident":
                    raise CelError("expected a claim name after 'assertion.'")
                return ("claim", claim)
            if self._at_op("["):
                # Map indexing: the only way to address a claim whose NAME contains
                # characters not valid in a CEL identifier (dots, slashes), e.g.
                # CircleCI's 'oidc.circleci.com/project-id'. This is CEL map access
                # by a string key -- GCP's own condition CEL uses the same form for
                # special-character keys (e.g. assertion.attributes['https://.../SAML/...']).
                self._advance()  # [
                sk, name = self._advance()
                if sk != "str":
                    raise CelError("assertion[...] index must be a single quoted claim name")
                if not self._at_op("]"):
                    raise CelError("expected ']' to close assertion[...]")
                self._advance()  # ]
                return ("claim", name)
            raise CelError("expected '.<claim>' or ['<claim>'] after 'assertion'")
        if k == "str":
            self._advance()
            return ("str", v)
        if k == "num":
            self._advance()
            value = int(v)
            # CEL int is 64-bit; real CEL rejects an out-of-range literal at
            # parse time, so the oracle must not silently evaluate one.
            if value > 2**63 - 1:
                raise CelError(f"integer literal out of int64 range: {v}")
            return ("int", value)
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
    raise CelError(
        f"expected a boolean in a logical position, got {type(value).__name__}: {value!r}"
    )


def _cel_equal(a, b) -> bool:
    """CEL runtime heterogeneous equality (langdef.md#equality).

    Numeric types compare mathematically on a continuous number line (int is the
    only numeric type implemented here); any other cross-type comparison is
    false, never an error. bool is checked FIRST because Python's bool is an int
    subclass, while CEL's bool is not numeric: ``true == 1`` is false in CEL but
    ``True == 1`` is True in Python.
    """
    a_is_bool, b_is_bool = isinstance(a, bool), isinstance(b, bool)
    if a_is_bool or b_is_bool:
        return a_is_bool and b_is_bool and a is b
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    if type(a) is not type(b):
        return False
    return a == b


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
    if kind == "int":
        return node[1]
    if kind == "claim":
        name = node[1]
        if name not in claims:
            raise CelError(f"condition references assertion.{name} but the token has no such claim")
        return claims[name]
    if kind == "not":
        return not _as_bool(_eval(node[1], claims))
    if kind == "and":
        return _as_bool(_eval(node[1], claims)) and _as_bool(_eval(node[2], claims))
    if kind == "or":
        return _as_bool(_eval(node[1], claims)) or _as_bool(_eval(node[2], claims))
    if kind in ("==", "!="):
        equal = _cel_equal(_eval(node[1], claims), _eval(node[2], claims))
        return equal if kind == "==" else not equal
    if kind == "in":
        needle = _eval(node[1], claims)
        return any(_cel_equal(needle, _eval(item, claims)) for item in node[2])
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
