"""Guard the judgment catalog against the corpus.

`docs/JUDGMENT-CATALOG.md` is the controlled vocabulary for `judgment.patterns`.
Two invariants keep it honest:
  1. Every pattern tag used by a vector is documented in the catalog -- so the
     vocabulary cannot sprawl silently; a new tag must be filed under a family.
  2. Every vector id the catalog cites as an example actually exists -- so a
     rename cannot leave the catalog pointing at a ghost.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "JUDGMENT-CATALOG.md"
VECTORS_DIR = ROOT / "vectors"


def _corpus() -> tuple[set[str], set[str]]:
    tags: set[str] = set()
    ids: set[str] = set()
    for path in sorted(VECTORS_DIR.glob("*.json")):
        for vector in json.loads(path.read_text(encoding="utf-8"))["vectors"]:
            ids.add(vector["id"])
            judgment = vector.get("judgment")
            if judgment:
                tags.update(judgment.get("patterns", []))
    return tags, ids


def test_every_pattern_tag_is_documented() -> None:
    tags, _ = _corpus()
    text = CATALOG.read_text(encoding="utf-8")
    missing = sorted(t for t in tags if f"`{t}`" not in text)
    assert not missing, (
        "pattern tags used in the corpus but absent from docs/JUDGMENT-CATALOG.md "
        f"(file each under a family): {missing}"
    )


def test_catalog_example_vector_ids_exist() -> None:
    _, ids = _corpus()
    text = CATALOG.read_text(encoding="utf-8")
    # Backtick tokens shaped like a vector id (issuer/consumer prefix), not a pattern tag.
    referenced = set(re.findall(r"`((?:gh|gitlab|gl|tf)-[a-z0-9-]+)`", text))
    unknown = sorted(r for r in referenced if r not in ids)
    assert not unknown, f"judgment catalog cites vector ids not in the corpus: {unknown}"
