"""Apply a run's transcripts to the corpus: flip vectors to `observed`.

The mechanical half of docs/OBSERVED-PROMOTION.md. Point it at the directory
`scripts/observe_aws.py` just wrote and it edits `vectors/*.json` in place --
sets `status`, writes the `observation` block, links the transcript, and bumps
each touched suite's version.

It does the bookkeeping, not the thinking. The generated `evidence` is a factual
one-liner; the sentence explaining what the result MEANS is yours to add, and
this script will not overwrite it on a later run (see --overwrite-evidence).

Refuses to promote on a DISAGREE or errored transcript. A disagreement is a
finding about the vector or the matcher, and promoting past it would launder the
one signal the harness exists to produce.

Usage:
    python scripts/promote.py observations/2026-08-31 --dry-run
    python scripts/promote.py observations/2026-08-31 --suite-version 0.5.0
    python scripts/promote.py observations/2026-08-31 --overwrite-evidence
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VECTORS_DIR = REPO_ROOT / "vectors"
CONTEXT_KEY = "token.actions.githubusercontent.com:sub"


def _suite_paths() -> list[Path]:
    return sorted(VECTORS_DIR.glob("*.json"))


def _find_suite(vector_id: str) -> Path | None:
    for path in _suite_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        if any(v["id"] == vector_id for v in data["vectors"]):
            return path
    return None


def _evidence(record: dict) -> str:
    """The factual baseline. Enrich it by hand; a re-run will not clobber it."""
    pattern = json.dumps(record["pattern"])
    return (
        f"simulate-custom-policy: {record['operator']} {CONTEXT_KEY} {pattern} vs subject "
        f"{json.dumps(record['subject'])} -> EvalDecision={record['decision']} "
        f"({record['tool_version']}). Raw request and response: {record['transcript']}"
    )


def _vector_span(text: str, vector_id: str) -> tuple[int, int]:
    anchor = f'      "id": "{vector_id}",'
    i = text.index(anchor)
    start = text.rindex("\n    {\n", 0, i) + 1
    end = re.compile(r"\n    \},?\n").search(text, i).end()
    return start, end


def _render_block(observation: dict) -> str:
    body = json.dumps(observation, indent=2, ensure_ascii=False)
    body = "\n".join("      " + line if line else line for line in body.splitlines())
    return '      "observation": ' + body.lstrip()


def _apply(text: str, vector_id: str, observation: dict) -> str:
    start, end = _vector_span(text, vector_id)
    chunk = text[start:end]
    chunk = re.sub(r'\n      "observation": \{.*?\n      \},', "", chunk, flags=re.DOTALL)
    chunk, n = re.subn(
        r'\n      "status": "(?:documented|observed)",',
        '\n      "status": "observed",\n' + _render_block(observation) + ",",
        chunk,
    )
    if n != 1:
        raise SystemExit(f"error: {vector_id}: expected exactly one status line, found {n}")
    return text[:start] + chunk + text[end:]


def _bump(text: str, new_version: str) -> str:
    updated, n = re.subn(r'("version": )"[^"]+"', rf'\1"{new_version}"', text, count=1)
    if n != 1:
        raise SystemExit("error: could not find the suite version line")
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path, help="observations/<date> from an observe_aws run")
    parser.add_argument("--suite-version", help="new version for every touched suite")
    parser.add_argument("--dry-run", action="store_true", help="report, change nothing")
    parser.add_argument(
        "--overwrite-evidence", action="store_true",
        help="replace hand-written evidence prose with the generated baseline",
    )
    args = parser.parse_args(argv)

    run_dir = args.run_dir if args.run_dir.is_absolute() else REPO_ROOT / args.run_dir
    if not run_dir.is_dir():
        print(f"error: no such run directory: {run_dir}", file=sys.stderr)
        return 2

    records, blocked = [], []
    for path in sorted(run_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("mode") != "simulate-custom-policy":
            continue  # creation probes are not 1:1 with a vector; write those by hand
        try:
            record["transcript"] = path.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            # A run directory outside the repo cannot yield the repo-relative path
            # the schema requires; only a record that already carries one is usable.
            if "transcript" not in record:
                print(
                    f"error: {path} is outside the repo, so no repo-relative transcript "
                    "path can be derived -- move the run directory under observations/",
                    file=sys.stderr,
                )
                return 2
        (records if record.get("agrees") else blocked).append(record)

    for record in blocked:
        reason = "errored" if record.get("decision") is None else "DISAGREE"
        print(
            f"[-] {reason:8} {record['vector_id']}: not promoted -- this is a FINDING, "
            "investigate the vector or the matcher",
            file=sys.stderr,
        )
    if not records:
        print("[i] nothing to promote", file=sys.stderr)
        return 1 if blocked else 0

    by_suite: dict[Path, list[dict]] = {}
    for record in records:
        suite = _find_suite(record["vector_id"])
        if suite is None:
            print(f"error: {record['vector_id']} is not in any suite", file=sys.stderr)
            return 2
        by_suite.setdefault(suite, []).append(record)

    kept_prose = []
    for suite, suite_records in by_suite.items():
        text = suite.read_text(encoding="utf-8")
        data = json.loads(text)
        existing = {v["id"]: v for v in data["vectors"]}
        for record in suite_records:
            vector = existing[record["vector_id"]]
            previous = vector.get("observation", {}).get("evidence")
            generated = _evidence(record)
            if previous and previous != generated and not args.overwrite_evidence:
                evidence = previous
                kept_prose.append(record["vector_id"])
            else:
                evidence = generated
            observation = {
                "method": "aws-iam-policy-simulator",
                "date": record["recorded_utc"][:10],
                "evidence": evidence,
                "tool_version": record["tool_version"],
                "transcript": record["transcript"],
            }
            was = vector.get("status")
            text = _apply(text, record["vector_id"], observation)
            print(f"[+] {was:10} -> observed  {record['vector_id']}")
        if args.suite_version:
            text = _bump(text, args.suite_version)
        json.loads(text)  # never write a file that stopped parsing
        if not args.dry_run:
            suite.write_text(text, encoding="utf-8", newline="\n")

    if kept_prose:
        print(
            f"[i] kept hand-written evidence on {len(kept_prose)} vector(s): "
            f"{', '.join(kept_prose)}\n"
            "    date, tool_version and transcript were refreshed. Re-read the prose against "
            "the new run, or pass --overwrite-evidence to reset it.",
        )
    if args.dry_run:
        print("[i] dry run -- nothing written")
    else:
        print(
            "[i] next: python scripts/coverage.py --write && python -m pytest -q, then enrich "
            "the evidence prose before committing"
        )
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
