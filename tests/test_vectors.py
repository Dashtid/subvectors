"""Exercise the whole vector corpus: every suite file validates against the
schema, ids are unique, and the reference matcher reproduces each vector's
declared match result.

This is the falsifiable core: if a vector claims ``expect: match`` but the
matcher disagrees, one of them is wrong -- and that is a finding, not a flake.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

from subvectors.matcher import SUPPORTED_CONSUMERS, satisfies

VECTORS_DIR = Path(__file__).resolve().parents[1] / "vectors"
SCHEMA_PATH = VECTORS_DIR / "schema" / "vector-suite.schema.json"


def _suite_files() -> list[Path]:
    return sorted(VECTORS_DIR.glob("*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _all_vectors() -> list[tuple[str, dict]]:
    cases: list[tuple[str, dict]] = []
    for path in _suite_files():
        for vector in _load(path)["vectors"]:
            cases.append((path.name, vector))
    return cases


_SUITE_FILES = _suite_files()
_VECTOR_CASES = _all_vectors()
_VECTOR_IDS = [f"{name}::{v['id']}" for name, v in _VECTOR_CASES]


def test_corpus_is_not_empty() -> None:
    assert _SUITE_FILES, "no vector suite files found under vectors/"
    assert _VECTOR_CASES, "suite files contain no vectors"


@pytest.mark.parametrize("path", _SUITE_FILES, ids=[p.name for p in _SUITE_FILES])
def test_suite_validates_against_schema(path: Path) -> None:
    schema = _load(SCHEMA_PATH)
    jsonschema.validate(_load(path), schema)


def test_vector_ids_are_globally_unique() -> None:
    ids = [v["id"] for _, v in _VECTOR_CASES]
    seen: set[str] = set()
    dupes = sorted({i for i in ids if i in seen or seen.add(i)})
    assert not dupes, f"duplicate vector ids across the corpus: {dupes}"


# --- the 'observed' contract: the status must carry its proof, not just a label ---

_OBSERVED_BASE = {
    "id": "probe-observed-contract",
    "issuer": "github",
    "subject": "repo:octo-org/octo-repo:ref:refs/heads/main",
    "condition": {"consumer": "aws-stringlike", "pattern": "repo:octo-org/octo-repo:*"},
    "expect": "match",
    "sources": ["https://docs.aws.amazon.com/IAM/latest/UserGuide/"],
}
_OBSERVATION = {
    "method": "aws-iam-policy-simulator",
    "date": "2026-08-25",
    "evidence": "simulate-custom-policy StringLike repo:octo-org/octo-repo:* vs subject -> allowed",
}


def _validate_vector(vector: dict) -> None:
    schema = _load(SCHEMA_PATH)
    jsonschema.validate({"suite": "probe", "version": "0.0.0", "vectors": [vector]}, schema)


def test_observed_without_observation_is_rejected() -> None:
    with pytest.raises(jsonschema.ValidationError):
        _validate_vector({**_OBSERVED_BASE, "status": "observed"})


def test_observed_with_observation_validates() -> None:
    _validate_vector({**_OBSERVED_BASE, "status": "observed", "observation": _OBSERVATION})


def test_documented_may_not_carry_an_observation() -> None:
    with pytest.raises(jsonschema.ValidationError):
        _validate_vector({**_OBSERVED_BASE, "status": "documented", "observation": _OBSERVATION})


@pytest.mark.parametrize("name,vector", _VECTOR_CASES, ids=_VECTOR_IDS)
def test_matcher_reproduces_expected_result(name: str, vector: dict) -> None:
    consumer = vector["condition"]["consumer"]
    if consumer not in SUPPORTED_CONSUMERS:
        pytest.skip(f"consumer {consumer!r} not implemented in the reference matcher yet")

    got = satisfies(vector["subject"], vector["condition"], claims=vector.get("claims"))
    expected = vector["expect"] == "match"
    assert got is expected, (
        f"{vector['id']} ({name}): matcher returned {got}, vector declares "
        f"expect={vector['expect']!r}\n  subject:   {vector['subject']!r}\n"
        f"  condition: {vector['condition']}"
    )


def test_claims_carry_sub_equal_to_subject_when_present() -> None:
    # 'subject' is the canonical single-claim view; a vector that carries the full
    # 'claims' set must include 'sub' and it must agree with 'subject' -- a claims
    # map without 'sub' would shadow the subject and no-match for the wrong reason.
    for name, vector in _VECTOR_CASES:
        claims = vector.get("claims")
        if claims:
            assert "sub" in claims, f"{vector['id']} ({name}): a claims map must include 'sub'"
            assert claims["sub"] == vector["subject"], (
                f"{vector['id']} ({name}): claims['sub'] must equal 'subject'"
            )


def _targeted_claims(condition: dict) -> set[str]:
    # The claims a condition evaluates: its own 'claim' (default sub), or for the
    # aws-all composite, the union across its sub-conditions.
    if condition.get("consumer") == "aws-all":
        targeted: set[str] = set()
        for sub_condition in condition.get("of", []):
            targeted |= _targeted_claims(sub_condition)
        return targeted
    return {condition.get("claim", "sub")}


def test_non_sub_conditions_carry_a_claims_map() -> None:
    # A condition targeting a claim other than 'sub' (e.g. 'aud') resolves its value
    # from the vector's claims map. The map must be present so the token's claim set
    # is explicit; the targeted claim may be deliberately ABSENT from it (that is the
    # AWS absent-context-key vector: a positive operator on a missing key is a
    # mismatch), but a vector with no claims at all would no-match by accident.
    for name, vector in _VECTOR_CASES:
        non_sub = _targeted_claims(vector["condition"]) - {"sub"}
        if non_sub:
            assert vector.get("claims"), (
                f"{vector['id']} ({name}): condition targets claims {sorted(non_sub)} "
                f"but the vector carries no claims map to evaluate them against"
            )


# --- corpus self-consistency: three invariants an oracle cannot afford to break ---
#
# All three held when first checked by hand on 2026-09-03 (58 cross-references,
# zero contradictions, zero duplicates). They are pinned because nothing was
# testing them, and each rots silently: a rename leaves a dangling citation, a
# copy-paste leaves a twin, and a token that gets two answers makes the whole
# corpus unciteable. `tests/test_judgment_catalog.py` already guards the catalog
# in both directions; this is the same guarantee for the vectors themselves.

# Deliberately narrow: <issuer>-<consumer>-<rest>, with the consumer segment drawn
# from the real set. A looser "starts with gh-" would fire on innocent prose such as
# "the gh-actions runner", and a test that reddens on a sentence is a test people
# learn to switch off.
_ID_TOKEN = re.compile(
    r"\b(?:gh|gl|gitlab|tfc|az|circleci|bitbucket)-(?:aws|gcp|flex|fic|az)-[a-z0-9-]+"
)


def _prose(vector: dict) -> str:
    """Every place a vector may name a sibling."""
    judgment = vector.get("judgment") or {}
    observation = vector.get("observation") or {}
    return " ".join(
        [
            vector.get("description", ""),
            judgment.get("reason", ""),
            observation.get("evidence", ""),
        ]
    )


def test_cross_referenced_vector_ids_exist() -> None:
    """A vector that cites a sibling must cite one that is still there.

    Descriptions lean on each other heavily -- "contrast X", "the inverse of Y",
    "the repair for Z" -- and those citations are load-bearing prose in a
    published corpus, not editorial garnish. A rename that leaves one dangling
    points a reader at nothing.
    """
    ids = {v["id"] for _, v in _VECTOR_CASES}
    dangling: dict[str, set[str]] = {}
    for _, vector in _VECTOR_CASES:
        for referenced in _ID_TOKEN.findall(_prose(vector)):
            if referenced != vector["id"] and referenced not in ids:
                dangling.setdefault(vector["id"], set()).add(referenced)
    assert not dangling, f"vectors cite ids that are not in the corpus: {dangling}"


def _token_key(vector: dict) -> tuple[str, str, str, str]:
    """Everything the verdict is a function of: the token, and the condition."""
    return (
        vector["issuer"],
        vector["subject"],
        json.dumps(vector.get("claims"), sort_keys=True),
        json.dumps(vector["condition"], sort_keys=True),
    )


def test_no_two_vectors_disagree_on_the_same_token() -> None:
    """The corpus must not answer one question two ways.

    Same issuer, same subject, same claims, same condition -- the verdict is
    determined, so two vectors declaring different `expect` values would mean at
    least one is wrong and a consumer testing against both can never pass. Note
    that differing only in the `claims` map is NOT a contradiction: those are
    different tokens, which is exactly how the aud-mismatch and
    repository_id-mismatch pairs are built.
    """
    verdicts: dict[tuple[str, str, str, str], list[tuple[str, str]]] = {}
    for _, vector in _VECTOR_CASES:
        verdicts.setdefault(_token_key(vector), []).append((vector["id"], vector["expect"]))
    conflicts = {
        key: entries for key, entries in verdicts.items() if len({e for _, e in entries}) > 1
    }
    assert not conflicts, (
        "vectors give different verdicts for an identical token and condition: "
        f"{[[i for i, _ in v] for v in conflicts.values()]}"
    )


def test_no_vector_is_an_exact_duplicate_of_another() -> None:
    """Two vectors that agree on everything teach one thing, and cost two.

    A twin usually means a copy-paste that never got its point edited in. It also
    inflates the corpus's own headline number, which this repo's scoreboard
    explicitly treats as an input rather than a score.
    """
    seen: dict[tuple[str, str, str, str], list[str]] = {}
    for _, vector in _VECTOR_CASES:
        seen.setdefault((*_token_key(vector), vector["expect"]), []).append(vector["id"])
    twins = [group for group in seen.values() if len(group) > 1]
    assert not twins, f"vectors are exact duplicates of one another: {twins}"
