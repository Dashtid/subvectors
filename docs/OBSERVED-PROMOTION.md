# Promoting a vector from `documented` to `observed`

Every vector ships `status: documented` (derived from cited docs) or `observed` (confirmed against
a real issuer/cloud). The corpus is **133 documented / 0 observed**. That ratio is the project's
real quality metric: a `documented` vector re-derives the same prose every scanner already
misreads and can inherit its errors; an `observed` vector adds information that exists nowhere
else. Closing the gap is the highest-value work available (ROADMAP, "where this stands").

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
    "evidence": "simulate-custom-policy: StringLike sub 'repo:octo-org/octo-repo:ref:refs/heads/main*' vs subject '...:main' -> evalDecision=allowed (aws-cli/2.17). AWS documents '*' only as 'any combination of characters'; zero-width is confirmed, not interpreted.",
    "tool_version": "aws-cli/2.17"
  }
}
```

`method` is one of: `aws-iam-policy-simulator`, `aws-sts-assume-role`, `azure-fic-token-exchange`,
`gcp-wif-token-exchange`, `gcp-wif-provider-validation`. `evidence` is the exact request and the
verbatim result — enough for a reader to reproduce, not a summary.

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
```

On AGREE it prints a paste-ready `observation` block; on DISAGREE it exits non-zero — that is a
**finding** (the vector or the matcher is wrong about real AWS), not a flake. The curated default
set covers: `gh-aws-case-mismatch-rejected` (exp 1); `gh-aws-org-wide-wildcard-repo`,
`gh-aws-repo-wide-wildcard-suffix`, `gh-aws-pull-request-subject`,
`gh-aws-ref-wildcard-spans-nested-branch` (exp 2); `gh-aws-branch-wildcard-zero-width`,
`gh-aws-branch-prefix-collision`, `gh-aws-single-char-wildcard` (exp 3); plus
`gh-aws-exact-branch-stringlike`, `gh-aws-stringequals-treats-star-literally`, and
`gh-aws-multivalue-loose-value-poisons-list` as controls — **11 vectors from one login**.

## The experiments (ROADMAP order — each independently promotes vectors and is publishable)

### 1. AWS `StringLike` case-sensitivity  — `aws-iam-policy-simulator`

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

### 2. Does `*` cross `:` and `/`?  — `aws-iam-policy-simulator`

AWS states no rule for the most security-relevant wildcard behaviour in CI/CD federation. Pattern
`repo:octo-org/*` vs subject `repo:octo-org/octo-repo:ref:refs/heads/main`: an `allowed` decision
proves `*` spans both separators. Promotes the whole wildcard-footgun family (the matcher already
encodes this in `_stringlike_to_regex`; this turns "encoded" into "observed").

### 3. Zero-width `*`  — `aws-iam-policy-simulator`

`gh-aws-branch-wildcard-zero-width`: pattern `...:refs/heads/main*` vs subject `...:refs/heads/main`.
The vector already flags itself as resting on "the standard reading of 'any combination'." An
`allowed` decision confirms zero-width matching.

### 4. June-2025 guardrail probe  — `aws-sts-assume-role` (creates a role — delete it)

Does role **creation** accept `values = ["repo:acme/x", "*"]` (a loose value hidden in a list)?
`iam create-role` with that trust policy, record accept/reject, `iam delete-role` immediately. If
accepted: AWS blocked the 2023 sub-less bug and left the 2026 multi-value one open — a publishable
finding on its own.

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

## Promoting the vector

1. Run the experiment; capture the verbatim result.
2. Flip the vector's `status` to `observed` and add the `observation` block.
3. `pytest -q` — the schema now requires the block, and the matcher must still reproduce `expect`.
   A promotion that changes the *match result* is a finding, not a formatting change: fix the
   vector or the matcher, don't paper over it.
4. Update the coverage/provenance line in `README.md` (the `documented`/`observed` split) — the
   drift gate guards it.
5. One commit per experiment, ROADMAP updated. Weeknight-sized, as ever.
