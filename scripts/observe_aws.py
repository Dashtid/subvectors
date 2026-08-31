"""Run corpus vectors against the real AWS IAM policy simulator.

The observed-promotion harness (docs/OBSERVED-PROMOTION.md). For each requested
vector it builds an IAM trust-policy Condition from the vector's OWN pattern,
presents the vector's OWN subject as the sts context value, asks
``aws iam simulate-custom-policy`` for a verdict, and compares it to the
vector's ``expect``. The corpus stays the single source of truth -- nothing is
re-typed, so the evidence maps 1:1 onto the vector it promotes.

AGREE  -> paste-ready ``observation`` block is printed; flip the vector's
          status to ``observed`` and add the block (schema enforces it).
DISAGREE -> that is a FINDING, not a flake: either the vector or the matcher
          is wrong about real AWS behavior. The run exits non-zero.

Scope: aws-stringlike / aws-stringequals vectors targeting ``sub`` (single or
multi-value pattern). The simulator creates no cloud resources; it needs only
``iam:SimulateCustomPolicy`` on any personal account.

Usage:
    python scripts/observe_aws.py                 # the curated default set
    python scripts/observe_aws.py <id> [<id> ..]  # specific vectors
    python scripts/observe_aws.py --dry-run       # print commands, call nothing
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

VECTORS_DIR = Path(__file__).resolve().parents[1] / "vectors"
CONTEXT_KEY = "token.actions.githubusercontent.com:sub"
_OPERATOR = {"aws-stringlike": "StringLike", "aws-stringequals": "StringEquals"}

# One simulator session promotes all of these (docs/OBSERVED-PROMOTION.md exps 1-3
# plus their control/neighbor vectors). Order follows the runbook.
DEFAULT_IDS = [
    # experiment 1 -- case sensitivity
    "gh-aws-case-mismatch-rejected",
    # experiment 2 -- '*' crosses ':' and '/'
    "gh-aws-org-wide-wildcard-repo",
    "gh-aws-repo-wide-wildcard-suffix",
    "gh-aws-pull-request-subject",
    "gh-aws-ref-wildcard-spans-nested-branch",
    # experiment 3 -- zero-width '*' and its neighbors
    "gh-aws-branch-wildcard-zero-width",
    "gh-aws-branch-prefix-collision",
    "gh-aws-single-char-wildcard",
    # controls / adjacent footguns
    "gh-aws-exact-branch-stringlike",
    "gh-aws-stringequals-treats-star-literally",
    "gh-aws-multivalue-loose-value-poisons-list",
]


def _load_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for path in sorted(VECTORS_DIR.glob("*.json")):
        for vector in json.loads(path.read_text(encoding="utf-8"))["vectors"]:
            index[vector["id"]] = vector
    return index


def _eligible(vector: dict) -> str | None:
    """Return a reason the vector cannot run here, or None if it can."""
    condition = vector["condition"]
    if condition["consumer"] not in _OPERATOR:
        return f"consumer {condition['consumer']!r} (harness covers aws-stringlike/stringequals)"
    if condition.get("claim", "sub") != "sub":
        return f"targets claim {condition['claim']!r} (harness covers sub only)"
    return None


def _build_request(vector: dict) -> dict:
    """The full simulate-custom-policy request, as one JSON document.

    Sent via ``--cli-input-json`` deliberately. AWS CLI v2 auto-parses any
    argument value that looks like JSON, and ``--policy-input-list`` is typed
    list<string> -- so an inline policy document is mis-parsed (and file://
    is mis-handled too; observed on the 2026-08-29 run). Wrapping the whole
    request in one JSON object, with the policy as an escaped string inside
    it, is the form that works.
    """
    condition = vector["condition"]
    operator = _OPERATOR[condition["consumer"]]
    pattern = condition["pattern"]
    values = pattern if isinstance(pattern, list) else [pattern]
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Resource": "*",
                "Condition": {operator: {CONTEXT_KEY: values}},
            }
        ],
    }
    return {
        "PolicyInputList": [json.dumps(policy)],
        "ActionNames": ["sts:AssumeRoleWithWebIdentity"],
        "ContextEntries": [
            {
                "ContextKeyName": CONTEXT_KEY,
                "ContextKeyType": "string",
                "ContextKeyValues": [vector["subject"]],
            }
        ],
    }


def _build_command(vector: dict) -> list[str]:
    return [
        "aws", "iam", "simulate-custom-policy",
        "--cli-input-json", json.dumps(_build_request(vector)),
        "--output", "json",
    ]


def _aws_version() -> str:
    out = subprocess.run(
        ["aws", "--version"], capture_output=True, text=True, check=False
    )
    return (out.stdout or out.stderr).strip().split(" ")[0] or "aws-cli/unknown"


def _observation_block(vector: dict, decision: str, aws_version: str) -> dict:
    condition = vector["condition"]
    operator = _OPERATOR[condition["consumer"]]
    return {
        "method": "aws-iam-policy-simulator",
        "date": datetime.date.today().isoformat(),
        "evidence": (
            f"simulate-custom-policy: {operator} {CONTEXT_KEY} "
            f"{json.dumps(condition['pattern'])} vs subject "
            f"{json.dumps(vector['subject'])} -> EvalDecision={decision} "
            f"({aws_version})"
        ),
        "tool_version": aws_version,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="*", help="vector ids (default: the curated set)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="print each aws command instead of executing it",
    )
    args = parser.parse_args(argv)
    ids = args.ids or DEFAULT_IDS

    index = _load_index()
    missing = [i for i in ids if i not in index]
    if missing:
        print(f"error: unknown vector id(s): {', '.join(missing)}", file=sys.stderr)
        return 2

    if not args.dry_run and shutil.which("aws") is None:
        print(
            "error: aws CLI not found - see docs/OBSERVED-PROMOTION.md 'Machine setup'",
            file=sys.stderr,
        )
        return 2

    aws_version = "" if args.dry_run else _aws_version()
    disagreements = 0
    for vector_id in ids:
        vector = index[vector_id]
        reason = _eligible(vector)
        if reason:
            print(f"[i] SKIP     {vector_id}: {reason}")
            continue
        command = _build_command(vector)
        if args.dry_run:
            print(f"[i] DRY-RUN  {vector_id}  expect={vector['expect']}")
            print("    " + subprocess.list2cmdline(command))
            continue
        run = subprocess.run(command, capture_output=True, text=True, check=False)
        if run.returncode != 0:
            print(f"[-] ERROR    {vector_id}: {run.stderr.strip()}", file=sys.stderr)
            disagreements += 1
            continue
        decision = json.loads(run.stdout)["EvaluationResults"][0]["EvalDecision"]
        agrees = (decision == "allowed") == (vector["expect"] == "match")
        if agrees:
            print(f"[+] AGREE    {vector_id}: EvalDecision={decision}")
            print("    paste into the vector alongside \"status\": \"observed\":")
            block = json.dumps(
                {"observation": _observation_block(vector, decision, aws_version)},
                indent=2,
            )
            print("    " + block.replace("\n", "\n    "))
        else:
            disagreements += 1
            print(
                f"[-] DISAGREE {vector_id}: expect={vector['expect']} but "
                f"EvalDecision={decision} - this is a FINDING; do not promote, "
                "investigate the vector (or the matcher) against real AWS"
            )
    return 1 if disagreements else 0


if __name__ == "__main__":
    raise SystemExit(main())
