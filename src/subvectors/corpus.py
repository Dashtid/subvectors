"""Access to the vector corpus itself — the product this package exists to carry.

The wheel force-includes the repository's ``vectors/`` tree at
``subvectors/vectors`` (see ``[tool.hatch.build.targets.wheel.force-include]``),
so an installed consumer can pin a versioned corpus instead of hand-vendoring
JSON files. In a source checkout the same tree lives at the repository root;
the loader serves both layouts so the test suite and an installed wheel read
identical bytes.

Zero runtime dependencies, like everything else here: consumers keep their own
matching code and load these vectors at test time.
"""

from __future__ import annotations

import json
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path


def _vectors_root() -> Traversable | Path:
    packaged = resources.files(__package__) / "vectors"
    if packaged.is_dir():
        return packaged
    checkout = Path(__file__).resolve().parents[2] / "vectors"
    if checkout.is_dir():
        return checkout
    raise FileNotFoundError(
        "vector corpus not found: neither packaged subvectors/vectors nor a "
        "repository-root vectors/ directory exists"
    )


def suite_names() -> list[str]:
    """Sorted names of every suite in the corpus (file stems of vectors/*.json)."""
    return sorted(
        entry.name[: -len(".json")]
        for entry in _vectors_root().iterdir()
        if entry.name.endswith(".json")
    )


def load_suite(name: str) -> dict:
    """One suite by name, parsed. Raises FileNotFoundError for unknown names."""
    suite = _vectors_root() / f"{name}.json"
    if not suite.is_file():
        raise FileNotFoundError(f"no such suite: {name!r} (see suite_names())")
    return json.loads(suite.read_text(encoding="utf-8"))


def load_schema() -> dict:
    """The JSON Schema every suite file conforms to (vectors/schema/)."""
    schema = _vectors_root() / "schema" / "vector-suite.schema.json"
    return json.loads(schema.read_text(encoding="utf-8"))
