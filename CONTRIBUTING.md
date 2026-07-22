# Contributing to subvectors

subvectors is a **cited, versioned answer key** for CI/CD OIDC trust decisions: JSON test
vectors, each asking "does subject S satisfy trust condition C, and is C safe?", plus a tiny
Python reference matcher that must reproduce every declared result. The corpus is the product.
A contribution is almost always **a new vector** (or a new suite / consumer to hold one).

Before writing anything, skim [`README.md`](README.md) and the schema at
[`vectors/schema/vector-suite.schema.json`](vectors/schema/vector-suite.schema.json).

## Two invariants every vector must satisfy

1. **The matcher reproduces `expect`.** `tests/test_vectors.py` runs the reference matcher over
   every vector and asserts it returns exactly the declared `match` / `no-match`. If the matcher
   disagrees, one of them is wrong — and that is a finding to resolve, not a test to skip.
2. **Every factual claim is cited by that vector's OWN `sources`.** A statement that is true in
   the world but not supported by one of the URLs listed on the same vector does not ship. This
   is the whole value: no vector rests on vibes. Direct quotes must appear verbatim on the cited
   page. When you compare to another issuer or consumer, cite a source for that side too.

## Anatomy of a vector

```json
{
  "id": "gh-aws-branch-wildcard",
  "issuer": "github",
  "subject": "repo:octo-org/octo-repo:ref:refs/heads/feature-x",
  "condition": { "consumer": "aws-stringlike", "claim": "sub", "pattern": "repo:octo-org/octo-repo:ref:refs/heads/*" },
  "expect": "match",
  "judgment": { "grade": "dangerous", "reason": "Any branch of the repo can assume the role...", "patterns": ["wildcard-ref", "unprotected-ref"] },
  "status": "documented",
  "sources": ["https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html"]
}
```

| Field | Notes |
| --- | --- |
| `id` | Kebab-case, **unique across the whole corpus**. Prefer descriptive (`gh-aws-branch-wildcard`) over numeric. |
| `issuer` | `github` \| `gitlab` \| `bitbucket` \| `circleci` \| `terraform-cloud`. Which CI system minted the subject. |
| `subject` | A **concrete** minted subject value — never a wildcard. Wildcards belong in the condition `pattern`, not the token. |
| `claims` | Optional. The full token claim set the condition is evaluated against. Required when the condition targets a claim other than `sub`, or when a `gcp-cel` / `azure-fic-flexible` expression references a non-`sub` claim. When present, `claims.sub` **must equal** `subject`. |
| `condition` | `consumer` + the rule. See consumers below. |
| `expect` | `match` \| `no-match`. What the matcher must return. |
| `judgment` | Optional. `grade` (`safe` \| `caution` \| `dangerous`) + `reason` (cited) + optional `patterns` tags. Omit on purely mechanical `no-match` / contrast vectors that make no safety claim. |
| `status` | `documented` (derived from cited docs) or `observed` (confirmed against a real issuer/cloud). Default to `documented`; only claim `observed` if you actually ran it. |
| `sources` | One or more primary-source URLs. Every vector is cited. |

## Consumers (matching semantics)

| Consumer | Rule shape | Notes |
| --- | --- | --- |
| `aws-stringlike` | `pattern` string or list | IAM `StringLike`: `*` multi-char, `?` one char, case-sensitive, **not path-aware** (`*` spans `/` and `:`). A list `pattern` is a multi-value condition (logical OR). |
| `aws-stringequals` | `pattern` string or list | Exact, case-sensitive. `*`/`?` are literal. List = OR. |
| `aws-all` | `of`: array of AWS sub-conditions | A full IAM Condition block: **AND** of AWS string sub-conditions (operators may differ; each may target a claim and use value lists). Only the two AWS string consumers may appear inside. |
| `azure-fic-exact` | `pattern` string | Classic Azure FIC: exact string match on the targeted claim; wildcards are literal; a mismatch fails the exchange silently. |
| `azure-fic-flexible` | `pattern` string (expression) | Preview flexible FIC: `claims['<name>'] <op> '<comparand>'` clauses joined by `and`; `eq` exact, `matches` an anchored, non-path-aware glob. Evaluated by [`src/subvectors/ffl.py`](src/subvectors/ffl.py). Address claims inside the expression (`claim` stays `sub`). Version-stamp preview semantics in the vector. |
| `gcp-cel` | `pattern` string (CEL) | GCP WIF `attribute_condition`, evaluated by [`src/subvectors/cel.py`](src/subvectors/cel.py). Address claims as `assertion.<name>`; `claim` stays `sub`. |

For `gcp-cel` and `azure-fic-flexible`, a referenced claim absent from `claims` **raises** rather
than silently no-matching — so the vector must supply every claim on an evaluated path.

## Grading

The `judgment.grade` is human-authored and cited; the matcher never computes it. Rough rubric,
kept consistent across the corpus:

- **safe** — tightly scoped and durable (exact single-ref pin, or an immutable-id pin).
- **caution** — works but has a residual (name-based/mutable identity, a wildcarded ref on an
  otherwise-pinned project, environment scoping that leans on protection rules).
- **dangerous** — a real over-permission (org/repo wildcard, `pull_request` subject, any-branch
  admission, a path-reuse squatter with no immutable pin).

## Workflow

```bash
python -m pip install -e ".[dev]"     # pytest + jsonschema
python -m pytest -q                   # matcher reproduces every vector; schema validates; ids unique
python scripts/coverage.py --write     # regenerate the README coverage matrix after adding vectors
```

- New suite file: drop a `vectors/<issuer>-<consumer>.json` — it is auto-discovered, schema-
  validated, and matcher-checked. No registration needed.
- New consumer: implement its semantics in the matcher (a tiny evaluator module like `cel.py` /
  `ffl.py` if it is an expression language), add it to `SUPPORTED_CONSUMERS` and the schema
  `consumer` enum, and pin the operator semantics with unit tests in `tests/`.
- Regenerate the coverage matrix; `tests/test_readme_coverage.py` fails if you forget.

## Scope — hard boundaries

- **Stay in the cloud-CI / OIDC / IAM domain.** No medical-imaging or SBOM/SCA content.
- **Don't grow the matcher into a scanner.** No reachability graphs, PR gates, or live cloud
  collectors — it is a correctness oracle, not a product.
- Conventional commits; small, focused changes.

## Upstream findings

If a vector exposes a real bug in a downstream tool (a scanner mis-matching or waving through a
dangerous pattern), that becomes an upstream PR to the tool — the distribution channel and the
proof in one. Open it against the tool's repo with the vector as the failing case.
