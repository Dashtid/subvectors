# subvectors

[![PyPI](https://img.shields.io/pypi/v/subvectors)](https://pypi.org/project/subvectors/)
[![CI](https://github.com/Dashtid/subvectors/actions/workflows/ci.yml/badge.svg)](https://github.com/Dashtid/subvectors/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://github.com/Dashtid/subvectors/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://github.com/Dashtid/subvectors/blob/main/pyproject.toml)

**Conformance vectors for OIDC trust subjects — the answer key for CI/CD OIDC trust decisions: a
cited, versioned test-vector suite answering "does subject S satisfy trust condition C, and is C
safe?"**

When a CI pipeline authenticates to a cloud via OIDC (GitHub Actions to AWS/Azure/GCP today), the
entire security boundary is a string comparison: the token's `sub` claim versus an admin-written
matching rule — an AWS IAM trust-policy condition, an Azure federated-identity-credential (FIC)
subject, a GCP Workload Identity Federation attribute condition. Every security tool in this space
must re-implement that comparison and judge those rules. They re-figure it out alone, and they get
it wrong.

> Status: v0.6.0 on PyPI - the corpus ships inside the wheel. An independent personal
> project, built on personal time and personal equipment. Every vector is source-cited, and
> **16 of the 163 vectors are `observed`**, all of them in the `github-aws` suite (56
> vectors), by two methods: 11 against the live AWS IAM policy simulator
> (`aws-iam-policy-simulator`, `iam:SimulateCustomPolicy`, with five `iam:CreateRole` probes
> recorded behind one of them), and 5 against tokens a real GitHub Actions job minted on
> 2026-10-08 (`github-actions-oidc-claims`: the issuer side only - what GitHub puts in the
> token - with the AWS match of that string still `documented`). **No token exchange has been
> observed yet, on AWS or on any other cloud** - the simulator evaluates a trust policy
> against a claim value you hand it, and the GitHub probe mints a token nobody presents.
> Every other suite is `documented` only. Each observed vector links a committed transcript
> under [`observations/`](https://github.com/Dashtid/subvectors/tree/main/observations)
> holding the exact request and the verbatim response, so the claim is auditable without an
> AWS or GitHub account. The generated [Coverage](#coverage) block carries the live
> `documented`/`observed` split.

## The proof this is needed (verified 2026-07-04; charset claim re-checked against current source 2026-09-19)

Checkov — one of the most widely used IaC security scanners — ships the only Azure FIC subject
check anywhere (`CKV_AZURE_249`). Read against its own source:

- It PASSES `repo:org/*` (any repo in the org may assume the role) and
  `repo:org/repo:pull_request` (unreviewed PR code may) — dangerous patterns waved through.
- Its repo regex has no `@` in the charset, so it will FAIL every valid immutable-format subject
  (`repo:owner@123456/name@456789:...`) — the format GitHub makes mandatory for repos created
  after **2026-07-15** (observed on a repository created 2026-10-08: it minted that format with
  no opt-in).

It is a bug class, not one tool's slip: another scanner's OIDC guardrail shipped exactly the
set-operator miss this corpus grades — `ForAnyValue:StringLike` hiding a wildcard `sub` — as
[CVE-2026-82856](https://github.com/advisories/GHSA-q2f7-m237-v562) (`@hulumi/policies` before
1.3.2, CVSS 9.3). And a third-party fixture repository reports that applying Checkov PR #7610
drops Checkov's immutable-subject false positives from 8 to 0, which is the same defect read from
the other side.

The formats churn (GitHub immutable claims, Azure flexible-FIC expressions in preview, per-issuer
dialects from GitLab/Bitbucket/CircleCI), and every scanner re-derives the semantics from prose
docs. A single maintained, cited corpus of test vectors fixes that for everyone.

## What a vector looks like

```json
{
  "id": "gh-aws-0007",
  "issuer": "github",
  "subject": "repo:acme/webapp:pull_request",
  "condition": { "consumer": "aws-stringlike", "pattern": "repo:acme/webapp:*" },
  "expect": "match",
  "judgment": {
    "grade": "dangerous",
    "reason": "pattern admits pull_request runs, which execute unmerged proposed changes rather than the protected default branch"
  },
  "sources": ["https://docs.github.com/en/actions/deployment/security-hardening-your-deployments"],
  "status": "documented"
}
```

Three layers per vector:

1. **Grammar** — is the subject well-formed for its issuer (classic AND immutable GitHub formats)?
2. **Match semantics** — does it satisfy the consumer's condition (AWS `StringLike`/`StringEquals`
   globbing, Azure FIC exact match + flexible expressions, GCP CEL)?
3. **Judgment** — is the condition safe? Graded findings for the patterns that matter:
   `pull_request` subjects, unprotected refs, wildcarded repos/orgs, missing `aud` pinning. The
   graded patterns are a stable, citable vocabulary — see
   [`docs/JUDGMENT-CATALOG.md`](https://github.com/Dashtid/subvectors/blob/main/docs/JUDGMENT-CATALOG.md).

Every vector carries a source citation and a provenance status — `documented` (derived from
primary documentation) or `observed` (recorded from a live exchange). The current split is
generated under [Coverage](#coverage) rather than asserted here, so it cannot drift. A small,
dependency-free Python reference matcher (pytest) passes the suite — it is a correctness oracle,
not a product.

## Coverage

<!-- COVERAGE:START (generated by scripts/coverage.py -- run `python scripts/coverage.py --write`) -->

**14 suites - 163 vectors** across 5 issuers and 6 consumer semantics.

Vectors by issuer x cloud-consumer semantics:

| Issuer | aws-stringlike | aws-stringequals | aws-all | azure-fic-exact | azure-fic-flexible | gcp-cel | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `github` | 18 | 31 | 7 | 10 | 12 | 12 | **90** |
| `gitlab` | 5 | 5 | 6 | 6 | 6 | 6 | **34** |
| `bitbucket` | 1 | 2 | 3 | - | - | - | **6** |
| `circleci` | 4 | - | 4 | - | - | 6 | **14** |
| `terraform-cloud` | 3 | 3 | 1 | - | 6 | 6 | **19** |
| **Total** | **31** | **41** | **21** | **16** | **24** | **30** | **163** |

Suites:

- `bitbucket-aws` 0.1.0 - 6 vectors
- `circleci-aws` 0.2.0 - 8 vectors
- `circleci-gcp` 0.1.0 - 6 vectors
- `github-aws` 0.9.0 - 56 vectors
- `github-azure-flexible` 0.2.0 - 12 vectors
- `github-azure` 0.1.0 - 10 vectors
- `github-gcp` 0.1.1 - 12 vectors
- `gitlab-aws` 0.2.0 - 16 vectors
- `gitlab-azure-flexible` 0.2.0 - 6 vectors
- `gitlab-azure` 0.1.0 - 6 vectors
- `gitlab-gcp` 0.1.0 - 6 vectors
- `terraform-aws` 0.1.0 - 7 vectors
- `terraform-azure-flexible` 0.1.0 - 6 vectors
- `terraform-gcp` 0.1.0 - 6 vectors

Judgments: 34 safe - 53 caution - 52 dangerous - 24 ungraded (mechanical no-match / contrast vectors carry no safety grade).

Provenance: 147 `documented` - 16 `observed`.

<!-- COVERAGE:END -->

## Install

```bash
pip install subvectors
```

The wheel ships the entire corpus, so a consumer pins a versioned artifact
instead of vendoring JSON by hand:

```python
from subvectors import corpus

corpus.suite_names()                 # ['bitbucket-aws', ..., 'terraform-gcp']
corpus.load_suite("github-aws")      # one suite, parsed
corpus.load_schema()                 # the JSON Schema the suites validate against
```

Prefer no dependency at all? The vectors are plain JSON under `vectors/` —
clone and read. The corpus itself is CC0 (`vectors/LICENSE`).

## Why an answer key instead of another scanner

Scanners in this space compete and get obsoleted: SpecterOps GitHound already maps
workflow-to-cloud OIDC reach, Prowler shipped a GitHub provider (2026-07-02), Wiz and Datadog are
converging. A test-vector suite does
not compete with scanners — it grades them. Each new tool entering the space is a new consumer of
the corpus, the way Wycheproof tests everyone's cryptography and the JSON-Schema-Test-Suite tests
everyone's validators. Consumers keep their own matching code (no runtime dependency to trust) and
import the vectors at test time.

The intended distribution channel is upstream PRs against the tools the vectors grade — the
channel and the proof in one. Four are open and **none has been merged or reviewed by a
maintainer** (PR state checked 2026-10-08): Checkov
[#7610](https://github.com/bridgecrewio/checkov/pull/7610) (opened 2026-07-14),
[#7627](https://github.com/bridgecrewio/checkov/pull/7627) (2026-07-27) and
[#7665](https://github.com/bridgecrewio/checkov/pull/7665) (2026-08-31) against the OIDC check
family, and Cartography
[#3088](https://github.com/cartography-cncf/cartography/pull/3088) (2026-07-30) for unparsed
trust-policy conditions. Zero merged upstream PRs is the honest scoreboard; see `ROADMAP.md`.

## Scope order

GitHub issuer + AWS consumer first, Azure FIC as the depth tranche (its exact-match and
flexible-expression semantics are the least-tooled corner), then GCP CEL and non-GitHub issuers.
Fully offline: JSON vectors + pytest, no cloud account required.

## Why this project exists (for me)

Closes a specific, recurring gap: multi-cloud IAM / OIDC trust-boundary depth (AWS + **Azure**).
Writing a falsifiable, cited test case about a trust rule forces genuinely understanding the rule
— active-recall learning with a public artifact as the receipt.

## License

Dual-licensed to maximize adoptability:

- **Vector data (`vectors/`) — CC0-1.0** (public-domain dedication). Embed the vectors in your
  tool's test suite with zero attribution or licensing friction — that frictionlessness is the
  point. See [`vectors/LICENSE`](https://github.com/Dashtid/subvectors/blob/main/vectors/LICENSE).
- **Everything else** (the reference matcher, schema, docs) **— Apache-2.0**. See
  [`LICENSE`](https://github.com/Dashtid/subvectors/blob/main/LICENSE).
