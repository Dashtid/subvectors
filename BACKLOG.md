# Backlog

Granular, current task list. Complements [`ROADMAP.md`](ROADMAP.md): the roadmap holds strategy,
phases, and rethink triggers; this holds the concrete next actions and the parking lot.

Success metric reminder (see ROADMAP): **bugs found and upstream PRs merged** is the score;
vectors added is an input. Prune this list toward that, not toward corpus size for its own sake.

Status keys: `[ ]` todo · `[~]` in progress · `[x]` done this cycle.

## In progress

- `[~]` **Checkov immutable-subject PR** (Slice 1) — separate `c:\code-two\checkov` session.
  Deadline 2026-07-15. Ship the immutable `@id` regex fix only; raise the org-wide `repo:org/*`
  case as an open question (maintainer-documented as intended). Snapshot to the private tracker
  once opened.

## Next up — this repo, independent of the upstream PRs

- `[ ]` **GCP CEL consumer + vector tranche.** `google_iam_workload_identity_pool_provider`
  `attribute_condition` uses CEL; a real expression matcher (bigger lift than exact/glob). The
  third major cloud consumer.
- `[ ]` **Expand the AWS tranche** beyond the 10 seed vectors: multiple `sub` conditions, `aud`
  pinning (`sts.amazonaws.com`), `job_workflow_ref` subjects, StringLike edge cases.
- `[ ]` **Non-GitHub issuers.** GitLab, Bitbucket, CircleCI, Terraform Cloud subject dialects —
  grammar + vectors. Breadth across CI systems (an area incumbents cover poorly).

## Corpus / product depth

- `[ ]` **Flexible FIC tranche** (`azure-fic-flexible` consumer): `claimsMatchingExpression` with
  `matches`/`eq`/`and` and `*`/`?` wildcards. Preview — Graph/portal-only, no Terraform/CLI
  surface; version-stamp every vector. Its own matcher (expression parse) and slice.
- `[ ]` **Judgment catalog.** Write the graded over-permission patterns (`pull-request`,
  `wildcard-repo`, `org-wide`, `wildcard-suffix`, `tag-ref`, `environment-scoped`,
  unprotected-branch) as a citable reference page; consider stable pattern IDs.
- `[ ]` **Immutable-format completeness.** Rename/transfer trigger vectors; `job_workflow_ref`
  grammar (stays mutable, not `@id`-suffixed); custom subject-claim templates.
- `[ ]` **Promote key vectors `documented` -> `observed`** by confirming against a real issuer/
  cloud once (optional, low-priority live check).

## Upstream feeder PRs — each in its own target-repo session, tracked in oss-contributions

- `[ ]` **CKV_AZURE_249 deepening PR.** After the first Checkov PR lands. Driven by the
  `pull_request`/tag/environment Azure vectors — the check passes patterns it should flag.
- `[ ]` **Cartography scoping issue + failing fixture** (Slice 3). `intel/aws/iam.py`
  "# TODO support conditions"; minimal additive proposal (sub/aud as edge properties). Issue-first.
- `[ ]` **Consumer-adoption outreach.** Where a tool's matching diverges from the suite (zizmor,
  Prowler, GitHound), offer a vector-derived test PR. This is the adoption signal to watch.
- `[ ]` **Fallback feeder: Prowler Entra-FIC checks** — only if the Checkov/Cartography seams close
  first (Prowler has zero FIC code; verified merge channel).

## Repo hygiene / infra

- `[x]` LICENSE (Apache-2.0, code) + `vectors/LICENSE` (CC0-1.0, data) + README licensing.
- `[x]` CI (GitHub Actions, pytest on 3.11-3.13).
- `[x]` `.gitattributes` (LF normalization).
- `[ ]` **CONTRIBUTING.md** — how to add a vector: schema fields, primary-source citation,
  `documented` vs `observed`, reference matcher must reproduce `expect`.
- `[ ]` **Final name decision.** Working name `oidc-subject-conformance`; repo dir still
  `oidc-reach`. Rename dir + remote before first public push.
- `[ ]` **Vector coverage summary** in the README (counts by issuer x consumer), ideally generated.
- `[ ]` **Publish decision** — PyPI for the matcher, or repo-only. Likely repo-only for now.

## Validation (not code)

- `[ ]` **Demand sanity-check** (pre-commit check #2 from the pivot): ask 1-2 cloud-security
  practitioners whether the shallow-FIC-lint / reach-widening pain is real and felt. Narrows scope
  if it lands flat.
- `[ ]` Re-read the ROADMAP rethink triggers before any strategy override.

## Later / ideas

- `[ ]` "caniuse for workload identity federation": issuer-claims x cloud-consumer capability
  matrix (a knowledge play the vectors can back).
- `[ ]` Contribute the corpus to a neutral home (OpenSSF WG / sigstore) if that path opens — the
  maintainer-role outcome.
- `[ ]` Optional live read-only mode against a free-tier sandbox.
