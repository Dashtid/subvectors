"""Integrity guard: an `observed` vector's transcript must back the vector.

The corpus asks scanners to be falsifiable, so its own provenance has to be too.
Prose evidence can quietly drift from the vector it sits on -- the pattern gets
edited, the observation does not, and nothing notices. These tests make the
committed transcript the arbiter: if a vector says it was confirmed against live
AWS, the raw record must exist, must be about THAT vector, and must carry the
verdict the vector claims.

They also re-check the safety property on every commit rather than on the day a
run happens: no AWS account id may appear anywhere under observations/.

Deliberately NOT enforced: that `evidence` prose repeats the transcript path.
`observation.transcript` is the machine-readable pointer and the thing this file
checks; requiring the same string inside the prose too would police style, not
integrity, and would fight every hand-edit of an evidence paragraph.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VECTORS_DIR = ROOT / "vectors"
OBSERVATIONS_DIR = ROOT / "observations"

_ACCOUNT_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")
_OPERATOR = {"aws-stringlike": "StringLike", "aws-stringequals": "StringEquals"}


def _vectors() -> list[dict]:
    out: list[dict] = []
    for path in sorted(VECTORS_DIR.glob("*.json")):
        out.extend(json.loads(path.read_text(encoding="utf-8"))["vectors"])
    return out


def _observed_with_transcript() -> list[dict]:
    return [
        v
        for v in _vectors()
        if v.get("status") == "observed" and "transcript" in v.get("observation", {})
    ]


def _transcript_files() -> list[Path]:
    return sorted(OBSERVATIONS_DIR.glob("*/*.json"))


def _transcript_mode(vector: dict) -> str:
    path = ROOT / vector["observation"]["transcript"]
    if not path.is_file():
        return ""
    return json.loads(path.read_text(encoding="utf-8")).get("mode", "")


def _simulator_backed() -> list[dict]:
    """Vectors whose transcript is one simulate-custom-policy call: 1:1 with the vector.

    Selected at collection rather than skipped at run time, so the suite reports
    what it checked instead of ten skips (a creation probe or an issuer-side
    claims dump backs a vector too, but through its own guard below).
    """
    return [
        v for v in _observed_with_transcript() if _transcript_mode(v) == "simulate-custom-policy"
    ]


def test_at_least_one_observed_vector_is_transcript_backed() -> None:
    """Guards the guard: if this file silently matched nothing it would prove nothing."""
    assert _observed_with_transcript(), "no observed vector carries a transcript"
    assert _simulator_backed(), "no observed vector is backed by a simulator transcript"


@pytest.mark.parametrize("vector", _observed_with_transcript(), ids=lambda v: v["id"])
def test_transcript_file_exists(vector: dict) -> None:
    path = ROOT / vector["observation"]["transcript"]
    assert path.is_file(), f"{vector['id']} cites a transcript that is not in the repo: {path}"


@pytest.mark.parametrize("vector", _simulator_backed(), ids=lambda v: v["id"])
def test_transcript_is_about_this_vector(vector: dict) -> None:
    """The record must describe the same condition and subject the vector asserts.

    This is the drift guard: editing a vector's pattern without re-running leaves
    an observation that no longer proves what it claims.
    """
    record = json.loads((ROOT / vector["observation"]["transcript"]).read_text(encoding="utf-8"))
    assert record["vector_id"] == vector["id"]
    assert record["pattern"] == vector["condition"]["pattern"], "pattern drifted from its evidence"
    assert record["subject"] == vector["subject"], "subject drifted from its evidence"
    assert record["operator"] == _OPERATOR[vector["condition"]["consumer"]]


@pytest.mark.parametrize("vector", _simulator_backed(), ids=lambda v: v["id"])
def test_transcript_verdict_matches_the_vector(vector: dict) -> None:
    record = json.loads((ROOT / vector["observation"]["transcript"]).read_text(encoding="utf-8"))
    assert record["agrees"] is True, f"{vector['id']} is promoted on a DISAGREE or errored run"
    expected_allowed = vector["expect"] == "match"
    assert (record["decision"] == "allowed") == expected_allowed


# A GitHub token's check_run_id is already 12 digits and run_id will be. In a
# github-actions-oidc-claims transcript they are the token's own claims, kept
# verbatim, and they are GitHub ids by construction. Everything else in the file
# is still scanned -- the exemption is two named keys, not the mode.
_GITHUB_ID_CLAIMS = ("check_run_id", "run_id")


def _scannable_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    record = json.loads(text)
    if record.get("mode") != "github-actions-oidc-claims":
        return text
    claims = dict(record.get("claims", {}))
    for key in _GITHUB_ID_CLAIMS:
        claims.pop(key, None)
    record["claims"] = claims
    return json.dumps(record)


@pytest.mark.parametrize("path", _transcript_files(), ids=lambda p: p.name)
def test_no_account_id_in_any_transcript(path: Path) -> None:
    """Re-checked every commit, not only on the day of a run."""
    text = _scannable_text(path)
    assert not _ACCOUNT_RE.search(text), f"{path} leaks what looks like an AWS account id"


@pytest.mark.parametrize("path", _transcript_files(), ids=lambda p: p.name)
def test_transcript_is_well_formed(path: Path) -> None:
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record.get("recorded_utc"), f"{path} has no recorded_utc"
    assert record.get("mode"), f"{path} has no mode"
    assert record.get("tool_version"), f"{path} has no tool_version"


def test_creation_probes_record_their_operator() -> None:
    """The 2026-08-30 defect, guarded permanently.

    A creation probe whose operator was not captured cannot support a claim: under
    StringLike a bare '*' is scoped-to-all, under StringEquals it is an inert
    literal, and the finding flips on which one ran.
    """
    for path in _transcript_files():
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("mode") != "iam-create-role":
            continue
        assert "operator" in record, f"{path} does not record its condition operator"
        assert "trust_policy" in record, f"{path} does not record the policy it sent"
        if record.get("accepted"):
            cleanup = record.get("cleanup", {})
            assert cleanup.get("verified_absent"), (
                f"{path} created a role without a verified deletion"
            )


def _observed_by_github_claims() -> list[dict]:
    return [
        v
        for v in _observed_with_transcript()
        if v["observation"]["method"] == "github-actions-oidc-claims"
    ]


@pytest.mark.parametrize("vector", _observed_by_github_claims(), ids=lambda v: v["id"])
def test_github_claims_transcript_backs_the_vector(vector: dict) -> None:
    """Issuer-side observations: the minted token must carry the shape the vector asserts.

    The vector keeps the corpus's octo-org placeholders; the transcript holds a
    real repository's token. What must agree is the part under test: the
    subject's context segment (everything after repo:OWNER/REPO), and for every
    other claim the vector pins, whether the value carries '@' ids -- the
    2026-10-08 finding being that job_workflow_ref carries none while sub in the
    same token carries two.
    """
    record = json.loads((ROOT / vector["observation"]["transcript"]).read_text(encoding="utf-8"))
    assert record["mode"] == "github-actions-oidc-claims"
    assert vector["id"] in record["vector_ids"], "transcript does not list this vector"
    claims = record["claims"]
    assert vector["subject"].split(":", 2)[2] == claims["sub"].split(":", 2)[2], (
        "subject context segment drifted from the minted token"
    )
    for name, value in (vector.get("claims") or {}).items():
        if name == "sub":
            continue
        assert name in claims, f"the minted token carries no {name} claim"
        assert value.count("@") == claims[name].count("@"), f"{name}: '@' shape differs"
