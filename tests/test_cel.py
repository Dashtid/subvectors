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


def test_heterogeneous_equality_cross_type_is_false_not_error() -> None:
    # CEL runtime heterogeneous equality: comparing a string claim to an int or
    # bool literal is false, never an error (langdef.md#equality). This is the
    # type-level trap: repository_id is the STRING "260064828".
    assert evaluate("assertion.repository_id == 260064828", CLAIMS) is False
    assert evaluate("assertion.event_name == true", {"event_name": "true"}) is False


def test_heterogeneous_inequality_is_always_true_for_cross_type() -> None:
    # The dangerous dual of the trap: a != guard written with an int literal
    # excludes nothing -- not even the exact value the author meant to exclude.
    assert evaluate("assertion.repository_id != 260064828", CLAIMS) is True


def test_int_equality_within_type_still_works() -> None:
    assert evaluate("20 == 20", CLAIMS) is True
    assert evaluate("20 != 21", CLAIMS) is True


def test_bool_is_not_numeric_despite_python() -> None:
    # Python: True == 1. CEL: true is not a numeric type, so true == 1 is false.
    assert evaluate("true == 1", CLAIMS) is False
    assert evaluate("true != 1", CLAIMS) is True


def test_int_literal_out_of_int64_range_raises() -> None:
    # CEL int is 64-bit; real CEL rejects the literal at parse time, so the
    # oracle raises rather than rendering a verdict on an unconfigurable condition.
    with pytest.raises(CelError):
        evaluate("assertion.repository_id == 92233720368547758070", CLAIMS)


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


NAMESPACED = {
    "sub": "org/2a3b4c5d/project/76543210/user/aaaa1111",
    "oidc.circleci.com/project-id": "76543210-ba98-fedc-3210-edcba0987654",
    "oidc.circleci.com/vcs-ref": "refs/heads/main",
}


def test_bracket_indexing_addresses_namespaced_claim() -> None:
    # A claim whose name has dots/slashes is only reachable via assertion['name'].
    assert evaluate("assertion['oidc.circleci.com/project-id'] == '76543210-ba98-fedc-3210-edcba0987654'", NAMESPACED) is True
    assert evaluate("assertion['oidc.circleci.com/project-id'] == 'other'", NAMESPACED) is False


def test_bracket_indexing_composes_with_methods_and_logic() -> None:
    assert evaluate("assertion.sub.startsWith('org/2a3b4c5d/project/76543210/') && assertion['oidc.circleci.com/vcs-ref'] == 'refs/heads/main'", NAMESPACED) is True
    assert evaluate("assertion['oidc.circleci.com/vcs-ref'].endsWith('/main')", NAMESPACED) is True


def test_bracket_indexing_absent_claim_raises() -> None:
    with pytest.raises(CelError):
        evaluate("assertion['oidc.circleci.com/ssh-rerun'] == 'false'", NAMESPACED)


def test_bracket_indexing_and_dot_notation_agree_for_simple_names() -> None:
    assert evaluate("assertion['sub'] == assertion.sub", NAMESPACED) is True


def test_bracket_indexing_malformed_raises() -> None:
    for bad in ["assertion[] == 'x'", "assertion['a' == 'x'", "assertion[project] == 'x'", "assertion['a'] ['b']"]:
        with pytest.raises(CelError):
            evaluate(bad, NAMESPACED)


# ---------------------------------------------------------------------------
# String literal decoding (the spec's ESCAPE production).
#
# These are written against `evaluate`, not against the private `_unescape`, so
# they pin the behaviour a vector actually gets. The literals are deliberately
# spelled with explicit Python escapes rather than raw strings: getting confused
# about which layer a backslash belongs to is precisely how the bug below
# survived, and a test that is itself ambiguous proves nothing.
# ---------------------------------------------------------------------------

ESCAPE_CLAIMS = {"v": "x"}


def _decodes_to(literal: str, expected: str) -> bool:
    """True iff `literal` (a CEL literal, quotes included) decodes to `expected`."""
    return evaluate("assertion.v == " + literal, {"v": expected}) is True


def test_escaped_backslash_before_an_unescaped_quote_keeps_its_backslash() -> None:
    """Regression: sequential str.replace ate a backslash it had just produced.

    A double quote needs no escape inside a single-quoted CEL string, so
    '  a \\ " b  ' is a legal literal meaning a, backslash, quote, b. Decoding by
    replacing \\\\ -> \\ first and \\" -> " second turned the freshly written
    backslash into the start of a new escape and dropped it, silently returning
    a, quote, b. A matcher oracle that loses a character can pass a vector for
    the wrong reason, so this is pinned in both quote directions.
    """
    assert _decodes_to("'a\\\\\"b'", 'a\\"b')
    assert _decodes_to('"a\\\\\'b"', "a\\'b")
    # The all-escaped spelling was correct before the fix and must stay correct.
    assert _decodes_to("'a\\\\\\'b'", "a\\'b")


def test_punctuation_and_whitespace_escapes_decode() -> None:
    assert _decodes_to("'a\\nb'", "a\nb")
    assert _decodes_to("'a\\tb'", "a\tb")
    assert _decodes_to("'a\\rb'", "a\rb")
    assert _decodes_to("'\\a\\b\\f\\v'", "\a\b\f\v")
    assert _decodes_to("'\\?'", "?")
    assert _decodes_to("'\\`'", "`")
    assert _decodes_to("'\\\\'", "\\")


def test_numeric_escapes_decode() -> None:
    """\\xHH, \\XHH, \\uHHHH, \\UHHHHHHHH and three-digit octal all name a code point."""
    assert _decodes_to("'\\x41'", "A")
    assert _decodes_to("'\\X41'", "A")
    assert _decodes_to("'\\u0041'", "A")
    assert _decodes_to("'\\U0001F600'", "\U0001F600")
    assert _decodes_to("'\\101'", "A")
    assert _decodes_to("'\\000'", "\x00")


def test_an_invalid_escape_is_a_parse_error() -> None:
    """CEL: "a backslash outside of a valid escape sequence ... will result in a
    parse error". Accepting one would let this oracle evaluate an expression that
    GCP itself would refuse to save."""
    for bad in [
        "assertion.v == '\\q'",          # not an escape at all
        "assertion.v == '\\x4'",         # \\x wants exactly two hex digits
        "assertion.v == '\\u00'",        # \\u wants exactly four
        "assertion.v == '\\999'",        # 9 is not an octal digit
        "assertion.v == '\\U00110000'",  # above the Unicode range
        "assertion.v == 'a\\'",          # dangling backslash
    ]:
        with pytest.raises(CelError):
            evaluate(bad, ESCAPE_CLAIMS)


def test_raw_string_literals_do_not_decode_escapes() -> None:
    """r'...' is the idiomatic way to write a regex inside matches()."""
    assert _decodes_to("r'a\\d+'", "a\\d+")
    assert _decodes_to("R'a\\d+'", "a\\d+")
    # A regex written raw and one written with doubled backslashes must agree.
    claims = {"ref": "refs/heads/main"}
    assert evaluate(r"assertion.ref.matches(r'^refs/heads/\w+$')", claims) is True
    assert evaluate("assertion.ref.matches('^refs/heads/\\\\w+$')", claims) is True


def test_triple_quoted_and_bytes_literals_are_refused_by_name() -> None:
    """Both are real STRING_LIT forms; refusing them by name beats misreading them."""
    for expr, wanted in [
        ("assertion.v == '''x'''", "triple-quoted"),
        ('assertion.v == """x"""', "triple-quoted"),
        ("assertion.v == b'x'", "bytes"),
        ("assertion.v == br'x'", "bytes"),
    ]:
        with pytest.raises(CelError) as exc:
            evaluate(expr, ESCAPE_CLAIMS)
        assert wanted in str(exc.value)


def test_a_decoded_escape_reaches_the_comparison() -> None:
    """End to end: the decoded value, not the source text, is what gets compared."""
    assert evaluate("assertion.sep == '\\t'", {"sep": "\t"}) is True
    assert evaluate("assertion.sep == '\\t'", {"sep": "\\t"}) is False
