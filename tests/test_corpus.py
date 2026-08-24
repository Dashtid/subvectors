"""The corpus loader must agree exactly with the vectors/ tree on disk."""

from pathlib import Path

import pytest

from subvectors import corpus

REPO_VECTORS = Path(__file__).resolve().parents[1] / "vectors"


def test_suite_names_match_the_tree() -> None:
    on_disk = sorted(p.stem for p in REPO_VECTORS.glob("*.json"))
    assert corpus.suite_names() == on_disk


def test_every_suite_loads_and_names_itself() -> None:
    for name in corpus.suite_names():
        suite = corpus.load_suite(name)
        assert suite["suite"] == name
        assert suite["vectors"], f"{name} has no vectors"


def test_unknown_suite_raises() -> None:
    with pytest.raises(FileNotFoundError, match="no such suite"):
        corpus.load_suite("no-such-suite")


def test_schema_is_reachable() -> None:
    assert "$schema" in corpus.load_schema()


def test_corpus_license_travels_with_the_data() -> None:
    # The corpus is CC0 while the package is Apache-2.0; the vectors' own
    # LICENSE must stay next to the data wherever the tree lands (repo root
    # in a checkout, subvectors/vectors in the wheel).
    assert (corpus._vectors_root() / "LICENSE").is_file()
