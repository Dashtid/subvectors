"""Exercise the whole vector corpus: every suite file validates against the
schema, ids are unique, and the reference matcher reproduces each vector's
declared match result.

This is the falsifiable core: if a vector claims ``expect: match`` but the
matcher disagrees, one of them is wrong -- and that is a finding, not a flake.
"""

from __future__ import annotations

import json
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


@pytest.mark.parametrize("name,vector", _VECTOR_CASES, ids=_VECTOR_IDS)
def test_matcher_reproduces_expected_result(name: str, vector: dict) -> None:
    consumer = vector["condition"]["consumer"]
    if consumer not in SUPPORTED_CONSUMERS:
        pytest.skip(f"consumer {consumer!r} not implemented in the reference matcher yet")

    got = satisfies(vector["subject"], vector["condition"])
    expected = vector["expect"] == "match"
    assert got is expected, (
        f"{vector['id']} ({name}): matcher returned {got}, vector declares "
        f"expect={vector['expect']!r}\n  subject:   {vector['subject']!r}\n"
        f"  condition: {vector['condition']}"
    )
