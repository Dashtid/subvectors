# Promoting a vector from `documented` to `observed`

Every vector ships `status: documented` (derived from cited docs) or `observed` (confirmed against
a real issuer/cloud). When this runbook was written (2026-08-25) the corpus was 133 documented /
0 observed; the AWS runs of 2026-08-29/30 promoted the first six (the live split is the README's
generated Coverage block). That ratio is the project's real quality metric: a `documented` vector
re-derives the same prose every scanner already misreads and can inherit its errors; an `observed`
vector adds information that exists nowhere else — the 08-30 run produced the project's first
primary finding (experiment 4 below).

Since 2026-08-25 the schema gives `observed` teeth: a vector with `status: observed` **must** carry
an `observation` block (`method`, `date`, `evidence`), and a `documented` vector **may not**. The
status can no longer be a stronger word with no more proof behind it — promotion means recording
how you confirmed it. `tests/test_vectors.py` enforces both directions.

## The `observation` block

```json
{
  "id": "gh-aws-branch-wildcard-zero-width",
  "...": "...",
  "status": "observed",
  "observation": {
    "method": "aws-iam-policy-simulator",
    "date": "2026-08-25",
    "evidence": "simulate-custom-policy: StringLike sub 'repo:octo-org/octo-repo:ref:refs/heads/main*' vs subject '...:main' -> evalDecision=allowed (aws-cli/2.17). AWS documents '*' only as 'any combination of characters'; zero-width is confirmed, not interpreted. Raw request and response: observations/2026-08-25/gh-aws-branch-wildcard-zero-width.json",
    "tool_version": "aws-cli/2.17",
    "transcript": "observations/2026-08-25/gh-aws-branch-wildcard-zero-width.json"
  }
}
```

`method` is one of: `aws-iam-policy-simulator`, `aws-sts-assume-role`, `azure-fic-token-exchange`,
`gcp-wif-token-exchange`, `gcp-wif-provider-validation`. `evidence` is the exact request and the
verbatim result — enough for a reader to reproduce, not a summary.

### `transcript` — why prose is not enough (added 2026-08-31)

`evidence` is prose, and prose loses the detail you did not know mattered. The 2026-08-30 creation
probe was hand-run and its **condition operator was never recorded** — and the strength of the whole
finding turns on it: under `StringLike` a bare `*` value is itself scoped-to-all, so AWS accepting it
contradicts AWS's own quoted guardrail text; under `StringEquals` it is an inert literal and the
result is weak. github-aws 0.3.3 had to narrow a headline claim because of it, after the overstated
string had already shipped in PyPI 0.3.0.

So every harness run now writes a machine-readable transcript under `observations/<date>/` holding
the exact request document, the verbatim response, the argv, the CLI version and the derived verdict.
Transcripts are **committed**: a reader can audit a promoted vector without an AWS account and
without re-running anything. AWS account ids are scrubbed to `<ACCOUNT-ID>` before anything reaches
disk, so they are safe to commit by construction rather than by remembering to sanitize.

`transcript` is optional in the schema so the hand-run 08-29/30 observations stay valid, but anything
the harness produces carries one. A promotion without a transcript needs a reason.

## Machine setup (probed 2026-08-25)

No `aws` CLI, no `gcloud`; `az` 2.89.1 is installed but logged out. So:

- **AWS** (experiments 1-4): `pip install awscli` (or the v2 bundle), then `aws configure` with a
  personal free-tier IAM user that has `iam:SimulateCustomPolicy` (and `iam:CreateRole` only for
  experiment 4). The simulator creates **no** resources.
- **Azure**: `az login` (interactive browser).
- **GCP** (experiment 5): install `gcloud`, `gcloud auth login`, a personal project with Workload
  Identity Federation API enabled.

Everything stays personal-account / free-tier — the IP-clean, personal-gear rule holds.

## The harness (added 2026-08-29)

For the AWS simulator experiments (1-3 below), don't type the commands by hand —
[`scripts/observe_aws.py`](../scripts/observe_aws.py) drives the simulator **from the corpus
itself**: it builds each policy from the vector's own `pattern`, presents the vector's own
`subject`, and compares AWS's `EvalDecision` to the vector's `expect`.

```bash
python scripts/observe_aws.py --dry-run   # inspect the exact aws commands, no credentials needed
python scripts/observe_aws.py            # run the curated 11-vector set (exps 1-3 + controls)

# experiment 4 -- creates one IAM role, always deletes it, always records the operator
python scripts/observe_aws.py --creation-probe gh-aws-multivalue-loose-value-poisons-list
python scripts/observe_aws.py --creation-probe --operator StringLike \
    --values 'repo:acme/x' --values '*'
python scripts/observe_aws.py --no-condition      # the 2023 sub-less bug class
```

On AGREE it prints a paste-ready `observation` block (with the transcript path already filled in);
on DISAGREE it exits non-zero — that is a **finding** (the vector or the matcher is wrong about real
AWS), not a flake. Every call writes its transcript to `observations/<date>/` whether it succeeded,
disagreed or errored: a failed run is evidence too.

The creation probe **refuses to run on an implied operator** — it either derives it from the named
vector's consumer or takes an explicit `--operator`, and either way the operator lands in the
transcript. That is the 2026-08-30 defect encoded as a guard rather than a note. It prompts before
creating anything (`--yes` to skip), always attempts `delete-role`, and records the `get-role`
verification so an un-deleted probe role cannot pass silently.

`tests/test_observe_aws.py` covers everything except the network hop — request shape, the
`--cli-input-json` invocation, transcript writing, account-id scrubbing, and the operator guard — so
the harness is no longer only exercised on a live run.

[!] **AWS CLI v2 gotcha (learned the hard way on 2026-08-29):** the CLI auto-parses any argument
that looks like JSON, and `--policy-input-list` is typed *list of strings* — so an inline policy
document is mis-parsed, and `file://` is mis-handled too. The harness therefore sends the whole
request through `--cli-input-json` with the policy as an escaped string inside it (fixed
2026-08-30). If you hand-roll a call, do the same. The curated default
set covers: `gh-aws-case-mismatch-rejected` (exp 1); `gh-aws-org-wide-wildcard-repo`,
`gh-aws-repo-wide-wildcard-suffix`, `gh-aws-pull-request-subject`,
`gh-aws-ref-wildcard-spans-nested-branch` (exp 2); `gh-aws-branch-wildcard-zero-width`,
`gh-aws-branch-prefix-collision`, `gh-aws-single-char-wildcard` (exp 3); plus
`gh-aws-exact-branch-stringlike`, `gh-aws-stringequals-treats-star-literally`, and
`gh-aws-multivalue-loose-value-poisons-list` as controls — **11 vectors from one login**.

## The experiments (ROADMAP order — each independently promotes vectors and is publishable)

### 1. AWS `StringLike` case-sensitivity  — `aws-iam-policy-simulator`  [DONE 2026-08-29]

AWS docs say StringLike is case-sensitive; third-party references circulate the opposite. Settle it.

```bash
aws iam simulate-custom-policy \
  --policy-input-list '[{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"sts:AssumeRoleWithWebIdentity","Resource":"*","Condition":{"StringLike":{"token.actions.githubusercontent.com:sub":"repo:Octo-Org/octo-repo:*"}}}]}]' \
  --action-names sts:AssumeRoleWithWebIdentity \
  --context-entries 'ContextKeyName=token.actions.githubusercontent.com:sub,ContextKeyType=string,ContextKeyValues=repo:octo-org/octo-repo:ref:refs/heads/main'
```

Read `EvaluationResults[0].EvalDecision`. `implicitDeny` (case mismatch) confirms case-sensitivity.
Promotes the case-sensitivity vectors. This live doc-vs-reference contradiction is the most quotable
single result the project has.

### 2. Does `*` cross `:` and `/`?  — `aws-iam-policy-simulator`  [DONE 2026-08-29]

AWS states no rule for the most security-relevant wildcard behaviour in CI/CD federation. Pattern
`repo:octo-org/*` vs subject `repo:octo-org/octo-repo:ref:refs/heads/main`: an `allowed` decision
proves `*` spans both separators. Promotes the whole wildcard-footgun family (the matcher already
encodes this in `_stringlike_to_regex`; this turns "encoded" into "observed").

### 3. Zero-width `*`  — `aws-iam-policy-simulator`  [DONE 2026-08-29]

`gh-aws-branch-wildcard-zero-width`: pattern `...:refs/heads/main*` vs subject `...:refs/heads/main`.
The vector already flags itself as resting on "the standard reading of 'any combination'." An
`allowed` decision confirms zero-width matching.

### 4. June-2025 guardrail probe  — `aws-sts-assume-role` (creates a role — delete it)  [DONE 2026-08-30]

Does role **creation** accept `values = ["repo:acme/x", "*"]` (a loose value hidden in a list)?
`iam create-role` with that trust policy, record accept/reject, `iam delete-role` immediately. If
accepted: AWS blocked the 2023 sub-less bug and left the 2026 multi-value one open — a publishable
finding on its own.

**Result — the run's sharpest finding.** `iam:CreateRole` **rejects** a condition-less GitHub-OIDC
trust policy (`MalformedPolicyDocument`: must evaluate `:sub` or `:job_workflow_ref` "which is not
scoped to all") but **accepts** the poisoned list — and even accepts a literal `*` as one value of
the list. AWS validates that a `sub` condition *exists*; it does not inspect the remaining values of
an OR-list. Recorded in `gh-aws-multivalue-loose-value-poisons-list` (evaluation half + creation
half). Incidental: `create-role` does not require the OIDC provider to exist first. Details and
cleanup verification in `BACKLOG.md`.

**[+] RE-RUN 2026-08-31 THROUGH THE HARNESS — operator pinned, claim restored at full strength.**
The 08-30 probe was hand-run and its condition operator was never recorded, which forced github-aws
0.3.3 to narrow the claim. All three probes were repeated with transcripts:

| Probe | Operator | Values | Result |
| --- | --- | --- | --- |
| the vector's own list | `StringLike` | `["repo:octo-org/octo-repo:ref:refs/heads/main", "repo:octo-org/*"]` | **ACCEPTED** |
| bare-`*` list | `StringLike` | `["repo:acme/x", "*"]` | **ACCEPTED** |
| condition-less | — | — | **REJECTED**, `MalformedPolicyDocument` |

The operator was the load-bearing detail and it came back the strong way. **Under `StringLike` a bare
`*` value is itself scoped to all** — so AWS accepts, inside an OR-list, exactly the shape its own
rejection message says the policy must not have ("...`:sub` or `...:job_workflow_ref` which is not
scoped to all"). The creation-time guardrail checks that a `sub` condition **exists**, not that its
values are scoped. Transcripts: `observations/2026-08-31/create-role-*.json`; both roles deleted with
`get-role -> NoSuchEntity` recorded.

**[+] SETTLED 2026-08-31/09-01 — the guardrail reads only the first value.**
`StringLike ["*"]` standing alone is REJECTED. So AWS does reject a scoped-to-all `sub` value. But
the same `"*"` in second position, behind a harmless value, is ACCEPTED — and reversing those two
values flips the verdict back to REJECTED.

| `sub` condition (StringLike) | Result |
| --- | --- |
| `["repo:octo-org/octo-repo:ref:refs/heads/main", "repo:octo-org/*"]` | accepted |
| `["repo:acme/x", "*"]` | accepted |
| `["*", "repo:acme/x"]` | **rejected** |
| `["*"]` | **rejected** |
| *no condition* | **rejected** |

AWS is not scanning for a non-scoped value — if it were, `["*", "repo:acme/x"]` would be accepted on
its second element. **It reads element `[0]` and stops.** A scoped-to-all value is therefore
invisible to the guardrail in any position but the first.

That is the same first-value-only defect the corpus feeds upstream to scanners (Checkov #7665), in
the cloud provider's own validator. All four rejections carry the identical `MalformedPolicyDocument`
naming `:sub` or `:job_workflow_ref` "which is not scoped to all" — so the error text describes a
check stricter than the one AWS actually performs.

[!] **Transcript collision, 2026-08-31 — fixed in the harness.** The single-`*` probe wrote to
`create-role-ad-hoc.json`, the same filename the earlier `["repo:acme/x","*"]` probe had used, and
silently overwrote it; the first result survived only because it was already committed. The two
records are now `create-role-ad-hoc-star-only.json` and `create-role-ad-hoc-tight-plus-star.json`
(contents untouched, recovered from git). The harness now derives an ad-hoc label from a hash of
`(operator, values)`, accepts `--label` to name a run, and **refuses to overwrite a transcript that
records a different probe** — a collision is an error, not a clobber.

### 5. GCP unquoted-int  — `gcp-wif-provider-validation` (needs GCP)

The one load-bearing claim in the whole corpus with an unverified empirical step. `cel.py` encodes
that `assertion.project_id == 20` is always-false when the claim is a JSON string — but nobody has
confirmed GCP's provider-creation API even **accepts** that expression rather than rejecting it at
write time. Create a WIF provider with `--attribute-condition='assertion.project_id == 20'`; record
whether creation succeeds. If GCP rejects it, the fail-open angle collapses to a footnote — so run
this before leaning on it anywhere public: an upstream PR, a vector's `judgment`, or the judgment
catalog. (Reworded 2026-08-29: this line used to read "before leaning on it in the article". There
is no article — that programme closed 2026-08-29 — but the verify-before-you-claim rule it encoded
is unchanged, and now points at the artifacts that replaced it.)

## The loop, automated (added 2026-09-01)

The 2026-08-29/30/31 runs repeated the same bookkeeping by hand every time, and every
mistake that reached a published artifact was bookkeeping: a lost condition operator, a
transcript silently overwritten, a stale coverage table, a version that moved in one file
and not the other. Three scripts now carry that load. None of them decide anything.

```bash
# 1. observe -- writes a transcript per call, refuses an implied operator,
#    refuses to overwrite a record of a different probe
python scripts/observe_aws.py
python scripts/observe_aws.py --creation-probe <vector-id>

# 2. promote -- transcripts in, observation blocks out, suite version bumped
python scripts/promote.py observations/<date> --dry-run
python scripts/promote.py observations/<date> --suite-version 0.5.0

# 3. release -- preflight, bump three files, tag, publish, verify PyPI
python scripts/release.py 0.5.0 --dry-run
python scripts/release.py 0.5.0 --notes-file notes.md
```

**What stays manual, deliberately.** The AWS key lifecycle (create it, delete it when
done). The judgment call about whether a result is worth promoting. And the sentence in
`observation.evidence` explaining what a result MEANS -- `promote.py` writes a factual
one-liner and will not overwrite prose you have enriched, precisely so that the thinking
is never generated.

**What CI now enforces** (`tests/test_observations.py`): every `observed` vector's
transcript exists in the repo; the transcript is about that vector (its recorded pattern,
subject and operator must match); its verdict matches the vector's `expect`; no AWS
account id appears anywhere under `observations/`; and every creation probe records both
its operator and a verified role deletion. So provenance drift becomes a failing test
rather than something a reader has to catch.

## Promoting the vector

1. Run the experiment through the harness; it captures the verbatim result and writes the transcript.
2. Flip the vector's `status` to `observed` and paste the printed `observation` block (it already
   carries `transcript`).
3. **Commit the transcript** under `observations/<date>/` in the same commit as the promotion. An
   `observed` vector whose transcript is not in the repo is a claim a reader has to take on trust —
   which is the thing this corpus exists not to do.
4. `pytest -q` — the schema requires the block, and the matcher must still reproduce `expect`.
   A promotion that changes the *match result* is a finding, not a formatting change: fix the
   vector or the matcher, don't paper over it.
5. Update the coverage/provenance line in `README.md` (the `documented`/`observed` split) — the
   drift gate guards it.
6. One commit per experiment, ROADMAP updated. Weeknight-sized, as ever.

**Never widen the prose beyond the transcript.** If a detail was not captured, either re-run to
capture it or say in `evidence` that it was not captured and what turns on it. That rule exists
because it was broken once, publicly, in a released artifact.
