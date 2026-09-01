"""Offline coverage for scripts/promote.py.

The script edits vectors/*.json in place with text surgery -- the suites are
hand-formatted (one-line `judgment` objects) and a json round-trip would reflow
every file. Text surgery is fast and diff-friendly and exactly the kind of thing
that silently corrupts a corpus, so the invariants are pinned here: the edit
lands in the right vector, the file still parses, an existing observation is
replaced rather than duplicated, and a DISAGREE transcript is never promoted.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("_subvectors_promote", ROOT / "scripts" / "promote.py")
promote = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(promote)

SUITE = ROOT / "vectors" / "github-aws.json"
OBSERVATION = {
    "method": "aws-iam-policy-simulator",
    "date": "2026-09-01",
    "evidence": "test evidence",
    "tool_version": "aws-cli/9.9.9",
    "transcript": "observations/2026-09-01/x.json",
}


def _record(**overrides: object) -> dict:
    base = {
        "mode": "simulate-custom-policy",
        "vector_id": "gh-aws-org-wide-wildcard-repo",
        "operator": "StringLike",
        "pattern": "repo:octo-org/*",
        "subject": "repo:octo-org/unrelated-repo:ref:refs/heads/main",
        "decision": "allowed",
        "agrees": True,
        "tool_version": "aws-cli/2.36.33",
        "transcript": "observations/2026-09-01/gh-aws-org-wide-wildcard-repo.json",
        "recorded_utc": "2026-09-01T10:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_span_selects_only_the_named_vector() -> None:
    text = SUITE.read_text(encoding="utf-8")
    start, end = promote._vector_span(text, "gh-aws-org-wide-wildcard-repo")
    chunk = text[start:end]
    assert '"id": "gh-aws-org-wide-wildcard-repo"' in chunk
    assert chunk.count('      "id": "') == 1, "span leaked into a neighbouring vector"


def test_apply_sets_status_and_keeps_the_file_parseable() -> None:
    text = SUITE.read_text(encoding="utf-8")
    out = promote._apply(text, "gh-aws-environment-subject-exact", OBSERVATION)
    data = json.loads(out)  # must not corrupt the suite
    vector = next(v for v in data["vectors"] if v["id"] == "gh-aws-environment-subject-exact")
    assert vector["status"] == "observed"
    assert vector["observation"] == OBSERVATION


def test_apply_replaces_an_existing_observation_rather_than_duplicating() -> None:
    text = SUITE.read_text(encoding="utf-8")
    out = promote._apply(text, "gh-aws-org-wide-wildcard-repo", OBSERVATION)
    start, end = promote._vector_span(out, "gh-aws-org-wide-wildcard-repo")
    assert out[start:end].count('"observation"') == 1
    data = json.loads(out)
    vector = next(v for v in data["vectors"] if v["id"] == "gh-aws-org-wide-wildcard-repo")
    assert vector["observation"]["tool_version"] == "aws-cli/9.9.9"


def test_apply_leaves_other_vectors_untouched() -> None:
    text = SUITE.read_text(encoding="utf-8")
    out = promote._apply(text, "gh-aws-environment-subject-exact", OBSERVATION)
    before = {v["id"]: v for v in json.loads(text)["vectors"]}
    after = {v["id"]: v for v in json.loads(out)["vectors"]}
    assert before.keys() == after.keys()
    changed = [k for k in before if before[k] != after[k]]
    assert changed == ["gh-aws-environment-subject-exact"]


def test_bump_touches_only_the_suite_version() -> None:
    text = SUITE.read_text(encoding="utf-8")
    out = promote._bump(text, "9.9.9")
    assert json.loads(out)["version"] == "9.9.9"
    assert json.loads(out)["vectors"] == json.loads(text)["vectors"]


def test_evidence_carries_operator_decision_and_transcript() -> None:
    evidence = promote._evidence(_record())
    assert "StringLike" in evidence
    assert "EvalDecision=allowed" in evidence
    assert "observations/2026-09-01/gh-aws-org-wide-wildcard-repo.json" in evidence


def test_find_suite_locates_the_owning_file() -> None:
    assert promote._find_suite("gh-aws-org-wide-wildcard-repo") == SUITE
    assert promote._find_suite("no-such-vector") is None


def _write_run(tmp_path: Path, *records: dict) -> Path:
    run_dir = tmp_path / "2026-09-01"
    run_dir.mkdir(parents=True)
    for record in records:
        name = Path(record["transcript"]).stem
        (run_dir / f"{name}.json").write_text(json.dumps(record), encoding="utf-8")
    return run_dir


def test_disagreement_is_never_promoted(tmp_path: Path, capsys) -> None:
    """A DISAGREE is the one signal the harness exists to produce."""
    run_dir = _write_run(tmp_path, _record(agrees=False, decision="implicitDeny"))
    code = promote.main([str(run_dir), "--dry-run"])
    assert code == 1
    err = capsys.readouterr().err
    assert "DISAGREE" in err and "FINDING" in err


def test_errored_run_is_never_promoted(tmp_path: Path, capsys) -> None:
    run_dir = _write_run(tmp_path, _record(agrees=None, decision=None))
    assert promote.main([str(run_dir), "--dry-run"]) == 1
    assert "errored" in capsys.readouterr().err


def test_creation_probes_are_skipped(tmp_path: Path, capsys) -> None:
    """They are not 1:1 with a vector, so they are written by hand."""
    run_dir = _write_run(
        tmp_path,
        {"mode": "iam-create-role", "accepted": True,
         "transcript": "observations/2026-09-01/create-role-x.json"},
    )
    assert promote.main([str(run_dir), "--dry-run"]) == 0
    assert "nothing to promote" in capsys.readouterr().err


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    before = SUITE.read_text(encoding="utf-8")
    run_dir = _write_run(tmp_path, _record())
    assert promote.main([str(run_dir), "--dry-run", "--suite-version", "9.9.9"]) == 0
    assert SUITE.read_text(encoding="utf-8") == before


def test_hand_written_evidence_survives_a_rerun(tmp_path: Path, capsys) -> None:
    """Today's enriched prose must not be clobbered by tomorrow's run."""
    run_dir = _write_run(tmp_path, _record())
    promote.main([str(run_dir), "--dry-run"])
    out = capsys.readouterr().out
    assert "kept hand-written evidence" in out
    assert "gh-aws-org-wide-wildcard-repo" in out


def test_missing_run_directory_exits_two(tmp_path: Path) -> None:
    assert promote.main([str(tmp_path / "nope"), "--dry-run"]) == 2
