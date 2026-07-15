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

- `[x]` **GCP CEL consumer + vector tranche.** Shipped: `src/subvectors/cel.py` (a minimal CEL
  evaluator -- ==/!=/&&/||/!/in, startsWith/endsWith/contains/matches with RE2 substring
  semantics), the `gcp-cel` consumer, 12 cited vectors (`vectors/github-gcp.json`), and the
  additive `claims` schema object. Deferred: the `attribute_mapping` / `google.subject` /
  `attribute.*` + principalSet IAM-binding layer (a separate downstream gate) -- its own tranche.
- `[ ]` **Expand the AWS tranche** beyond the 10 seed vectors: multiple `sub` conditions, `aud`
  pinning (`sts.amazonaws.com`), `job_workflow_ref` subjects, StringLike edge cases.
- `[~]` **Non-GitHub issuers (breadth — incumbents cover this poorly).**
  - `[x]` GitLab → AWS: `src/subvectors/gitlab.py` grammar (default `project_path:` + immutable
    `project_id:` forms) + 10 cited vectors (`vectors/gitlab-aws.json`). Covers group-wide/subgroup
    wildcards, ref_type confusion, the no-merge_request-marker MR admission, and path-reuse.
  - `[ ]` GitLab → Azure FIC and GitLab → GCP tranches (reuse azure-fic-exact / gcp-cel).
  - `[ ]` Bitbucket, CircleCI, Terraform Cloud issuer grammars + vectors.
  - `[ ]` Multi-key AWS consumer (`aws-stringequals-all` over a claims map) so name-based GitLab
    pins can encode `ref_protected` / `project_id` as EVALUATED keys, not just judgment prose —
    would upgrade several caution vectors. Schema/consumer extension.

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
- `[ ]` **CKV_GCP_125 scoping question / PR.** The check only reasons about `assertion.sub ==`
  conditions, so it is blind to the `assertion.repository_id`/`repository_owner_id` immutable pins
  Google officially recommends — it cannot distinguish the safest config from a missing one. Frame
  as the open question already in issue #7005 (not a unilateral bug). Vectors
  `gh-gcp-immutable-id-pin-safe` + `gh-gcp-classic-sub-immutable-break` demonstrate the divergence.
  `git log -S "assertion.sub"` in a fresh clone first (confirm still sub-only post-#7610).
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
- `[x]` **Name decided: `subvectors`.** GitHub repo created
  (github.com/Dashtid/subvectors); package + docs renamed. Remaining: the local working dir is
  still `c:\code-two\oidc-reach` — rename it to `subvectors` outside a live session (it is the
  session CWD).
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
