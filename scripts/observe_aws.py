"""Run corpus vectors against real AWS and record an auditable transcript.

The observed-promotion harness (docs/OBSERVED-PROMOTION.md). Two modes:

**Simulator** (default, creates nothing). For each requested vector it builds an
IAM trust-policy Condition from the vector's OWN pattern, presents the vector's
OWN subject as the sts context value, asks ``aws iam simulate-custom-policy``
for a verdict, and compares it to the vector's ``expect``. The corpus stays the
single source of truth -- nothing is re-typed, so the evidence maps 1:1 onto the
vector it promotes.

**Creation probe** (``--creation-probe``, creates and deletes a real role).
Records whether ``iam:CreateRole`` ACCEPTS a GitHub-OIDC trust policy, which is
a different question from whether the policy would ever match. Experiment 4 in
the runbook.

AGREE  -> paste-ready ``observation`` block is printed; flip the vector's
          status to ``observed`` and add the block (schema enforces it).
DISAGREE -> that is a FINDING, not a flake: either the vector or the matcher
          is wrong about real AWS behavior. The run exits non-zero.

**Every call writes a transcript** under ``observations/<date>/`` holding the
exact request document, the verbatim response, the argv, the CLI version and
the derived verdict. `observation.evidence` is prose and prose loses detail: the
2026-08-30 creation probe was recorded without its condition operator, and the
strength of the finding turned on exactly that (github-aws 0.3.3 had to narrow
the claim). A transcript makes the record complete by construction, so a reader
can audit a promoted vector without re-running anything and without an AWS
account. Account IDs are scrubbed before anything is written to disk.

Usage:
    python scripts/observe_aws.py                 # the curated default set
    python scripts/observe_aws.py <id> [<id> ..]  # specific vectors
    python scripts/observe_aws.py --dry-run       # print commands, call nothing

    # experiment 4 -- creates a role, always deletes it, records the operator
    python scripts/observe_aws.py --creation-probe <id>
    python scripts/observe_aws.py --creation-probe \
        --operator StringLike --values 'repo:acme/x' --values '*'
    python scripts/observe_aws.py --creation-probe --no-condition
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
VECTORS_DIR = REPO_ROOT / "vectors"
OBSERVATIONS_DIR = REPO_ROOT / "observations"
CONTEXT_KEY = "token.actions.githubusercontent.com:sub"
GH_ISSUER = "token.actions.githubusercontent.com"
_OPERATOR = {"aws-stringlike": "StringLike", "aws-stringequals": "StringEquals"}
CREATION_OPERATORS = ("StringLike", "StringEquals", "StringEqualsIgnoreCase")

# A bare 12-digit run is an AWS account id. ARNs embed one, so scrubbing the
# number scrubs the ARN too. Transcripts are committed; account ids are not.
_ACCOUNT_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")
_ACCOUNT_PLACEHOLDER = "<ACCOUNT-ID>"

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


def scrub(value: Any) -> Any:
    """Replace AWS account ids anywhere in a JSON-ish structure.

    Applied to every transcript before it touches disk. The corpus is public and
    .gitignore already forbids committing real cloud data; this makes the
    transcripts safe to commit rather than something to remember to sanitize.
    """
    if isinstance(value, str):
        return _ACCOUNT_RE.sub(_ACCOUNT_PLACEHOLDER, value)
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    return value


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


def _trust_policy(operator: str | None, values: list[str], principal: str) -> dict:
    """A GitHub-OIDC assume-role trust policy.

    ``operator=None`` builds the condition-less form -- the 2023 bug class AWS's
    creation-time guardrail is documented to reject.
    """
    statement: dict[str, Any] = {
        "Effect": "Allow",
        "Principal": {"Federated": principal},
        "Action": "sts:AssumeRoleWithWebIdentity",
    }
    if operator is not None:
        statement["Condition"] = {operator: {CONTEXT_KEY: values}}
    return {"Version": "2012-10-17", "Statement": [statement]}


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


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _parse_json(text: str) -> Any:
    """Response bodies are recorded parsed when possible, raw when not."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text.strip()


def write_transcript(
    out_dir: Path, name: str, record: dict, *, timestamp: str | None = None
) -> Path:
    """Scrub, stamp and write one transcript. Returns its repo-relative path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.json"
    document = {
        "recorded_utc": timestamp or datetime.datetime.now(
            datetime.timezone.utc
        ).replace(microsecond=0).isoformat(),
        **scrub(record),
    }
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _observation_block(
    vector: dict, decision: str, aws_version: str, transcript: str
) -> dict:
    condition = vector["condition"]
    operator = _OPERATOR[condition["consumer"]]
    return {
        "method": "aws-iam-policy-simulator",
        "date": datetime.date.today().isoformat(),
        "evidence": (
            f"simulate-custom-policy: {operator} {CONTEXT_KEY} "
            f"{json.dumps(condition['pattern'])} vs subject "
            f"{json.dumps(vector['subject'])} -> EvalDecision={decision} "
            f"({aws_version}). Raw request and response: {transcript}"
        ),
        "tool_version": aws_version,
        "transcript": transcript,
    }


def _simulate(ids: list[str], index: dict[str, dict], out_dir: Path, dry_run: bool) -> int:
    aws_version = "" if dry_run else _aws_version()
    disagreements = 0
    for vector_id in ids:
        vector = index[vector_id]
        reason = _eligible(vector)
        if reason:
            print(f"[i] SKIP     {vector_id}: {reason}")
            continue
        request = _build_request(vector)
        command = _build_command(vector)
        if dry_run:
            print(f"[i] DRY-RUN  {vector_id}  expect={vector['expect']}")
            print("    " + subprocess.list2cmdline(command))
            continue
        run = _run(command)
        record: dict[str, Any] = {
            "mode": "simulate-custom-policy",
            "vector_id": vector_id,
            "operator": _OPERATOR[vector["condition"]["consumer"]],
            "pattern": vector["condition"]["pattern"],
            "subject": vector["subject"],
            "expect": vector["expect"],
            "tool_version": aws_version,
            "argv": command,
            "request": request,
            "exit_code": run.returncode,
            "response": _parse_json(run.stdout),
            "stderr": run.stderr.strip() or None,
        }
        if run.returncode != 0:
            record["decision"] = None
            record["agrees"] = None
            transcript = _relative(write_transcript(out_dir, vector_id, record))
            print(f"[-] ERROR    {vector_id}: {run.stderr.strip()}", file=sys.stderr)
            print(f"    transcript: {transcript}", file=sys.stderr)
            disagreements += 1
            continue
        decision = json.loads(run.stdout)["EvaluationResults"][0]["EvalDecision"]
        agrees = (decision == "allowed") == (vector["expect"] == "match")
        record["decision"] = decision
        record["agrees"] = agrees
        transcript = _relative(write_transcript(out_dir, vector_id, record))
        if agrees:
            print(f"[+] AGREE    {vector_id}: EvalDecision={decision}")
            print(f"    transcript: {transcript}")
            print("    paste into the vector alongside \"status\": \"observed\":")
            block = json.dumps(
                {
                    "observation": _observation_block(
                        vector, decision, aws_version, transcript
                    )
                },
                indent=2,
            )
            print("    " + block.replace("\n", "\n    "))
        else:
            disagreements += 1
            print(
                f"[-] DISAGREE {vector_id}: expect={vector['expect']} but "
                f"EvalDecision={decision} - this is a FINDING; do not promote, "
                f"investigate the vector (or the matcher) against real AWS. "
                f"transcript: {transcript}"
            )
    return 1 if disagreements else 0


def resolve_creation_probe(
    args: argparse.Namespace, index: dict[str, dict]
) -> tuple[str | None, list[str], str]:
    """(operator, values, label) for a creation probe, or raise ValueError.

    The operator is ALWAYS explicit here -- derived from the vector's consumer or
    passed on the command line, never implied. Losing it is what forced the
    github-aws 0.3.3 narrowing, so the harness refuses to run without it.
    """
    if args.no_condition:
        if args.operator or args.values or args.creation_probe is not None:
            raise ValueError("--no-condition takes no operator, values or vector id")
        return None, [], "no-condition"
    if args.creation_probe:
        vector = index.get(args.creation_probe)
        if vector is None:
            raise ValueError(f"unknown vector id: {args.creation_probe}")
        reason = _eligible(vector)
        if reason:
            raise ValueError(f"{args.creation_probe}: {reason}")
        operator = _OPERATOR[vector["condition"]["consumer"]]
        pattern = vector["condition"]["pattern"]
        values = list(pattern) if isinstance(pattern, list) else [pattern]
        return operator, values, args.creation_probe
    if not (args.operator and args.values):
        raise ValueError(
            "creation probe needs a vector id, or both --operator and --values, "
            "or --no-condition"
        )
    return args.operator, list(args.values), "ad-hoc"


def _creation_probe(
    operator: str | None,
    values: list[str],
    label: str,
    out_dir: Path,
    dry_run: bool,
    assume_yes: bool,
) -> int:
    """Record whether iam:CreateRole ACCEPTS a trust policy. Always cleans up."""
    role_name = f"subvectors-probe-{secrets.token_hex(4)}"
    if dry_run:
        policy = _trust_policy(operator, values, f"arn:aws:iam::<ACCOUNT>:oidc-provider/{GH_ISSUER}")
        print(f"[i] DRY-RUN  creation probe {label}  role={role_name}")
        print(f"    operator={operator or 'NONE'} values={json.dumps(values)}")
        print("    " + json.dumps(policy))
        return 0

    identity = _run(["aws", "sts", "get-caller-identity", "--output", "json"])
    if identity.returncode != 0:
        print(f"[-] ERROR    cannot resolve account: {identity.stderr.strip()}", file=sys.stderr)
        return 2
    account = json.loads(identity.stdout)["Account"]
    principal = f"arn:aws:iam::{account}:oidc-provider/{GH_ISSUER}"
    policy = _trust_policy(operator, values, principal)
    aws_version = _aws_version()

    print(f"[!] creation probe {label}: creates IAM role {role_name}, then deletes it.")
    print(f"    operator={operator or 'NONE'} values={json.dumps(values)}")
    if not assume_yes:
        if input("    proceed? [y/N] ").strip().lower() not in ("y", "yes"):
            print("[i] aborted")
            return 0

    create = ["aws", "iam", "create-role", "--role-name", role_name,
              "--assume-role-policy-document", json.dumps(policy), "--output", "json"]
    run = _run(create)
    accepted = run.returncode == 0
    record: dict[str, Any] = {
        "mode": "iam-create-role",
        "probe": label,
        "operator": operator,
        "values": values,
        "role_name": role_name,
        "tool_version": aws_version,
        "argv": create,
        "trust_policy": policy,
        "exit_code": run.returncode,
        "accepted": accepted,
        "response": _parse_json(run.stdout) if accepted else None,
        "stderr": run.stderr.strip() or None,
    }
    try:
        if accepted:
            print(f"[+] ACCEPTED {label}: role created")
        else:
            print(f"[+] REJECTED {label}: {run.stderr.strip()}")
    finally:
        # Cleanup runs whatever the verdict was, and the check is recorded too:
        # an un-deleted probe role is a live trust relationship.
        if accepted:
            delete = _run(["aws", "iam", "delete-role", "--role-name", role_name])
            verify = _run(["aws", "iam", "get-role", "--role-name", role_name])
            record["cleanup"] = {
                "delete_exit_code": delete.returncode,
                "delete_stderr": delete.stderr.strip() or None,
                "get_role_after_delete_exit_code": verify.returncode,
                "get_role_after_delete_stderr": verify.stderr.strip() or None,
                "verified_absent": verify.returncode != 0
                and "NoSuchEntity" in (verify.stderr or ""),
            }
            state = "verified absent" if record["cleanup"]["verified_absent"] else "NOT VERIFIED"
            print(f"    cleanup: delete-role exit={delete.returncode}, get-role -> {state}")
        else:
            record["cleanup"] = {"nothing_created": True}
        transcript = _relative(write_transcript(out_dir, f"create-role-{label}", record))
        print(f"    transcript: {transcript}")

    cleanup = record.get("cleanup", {})
    if accepted and not cleanup.get("verified_absent"):
        print(
            f"[-] cleanup unverified for role {role_name} - delete it by hand before "
            "leaving the account",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="*", help="vector ids (default: the curated set)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="print each aws command instead of executing it",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="transcript directory (default: observations/<today>)",
    )
    creation = parser.add_argument_group("creation probe (experiment 4 -- creates a role)")
    creation.add_argument(
        "--creation-probe", metavar="VECTOR_ID", nargs="?", const="",
        help="probe iam:CreateRole with this vector's condition",
    )
    creation.add_argument(
        "--operator", choices=CREATION_OPERATORS,
        help="condition operator for an ad-hoc creation probe (always recorded)",
    )
    creation.add_argument(
        "--values", action="append", metavar="VALUE",
        help="a sub condition value for an ad-hoc creation probe (repeatable)",
    )
    creation.add_argument(
        "--no-condition", action="store_true",
        help="probe the condition-less trust policy (the 2023 bug class)",
    )
    creation.add_argument(
        "--yes", action="store_true", help="skip the creation-probe confirmation",
    )
    args = parser.parse_args(argv)

    index = _load_index()
    out_dir = args.out_dir or (OBSERVATIONS_DIR / datetime.date.today().isoformat())

    is_creation = args.creation_probe is not None or args.no_condition
    if not args.dry_run and shutil.which("aws") is None:
        print(
            "error: aws CLI not found - see docs/OBSERVED-PROMOTION.md 'Machine setup'",
            file=sys.stderr,
        )
        return 2

    if is_creation:
        if args.ids:
            print(
                "error: pass the creation probe's vector id to --creation-probe, "
                "not as a positional argument",
                file=sys.stderr,
            )
            return 2
        try:
            operator, values, label = resolve_creation_probe(args, index)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return _creation_probe(operator, values, label, out_dir, args.dry_run, args.yes)

    ids = args.ids or DEFAULT_IDS
    missing = [i for i in ids if i not in index]
    if missing:
        print(f"error: unknown vector id(s): {', '.join(missing)}", file=sys.stderr)
        return 2
    return _simulate(ids, index, out_dir, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
