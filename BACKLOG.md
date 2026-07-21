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
- `[x]` **Expand the AWS tranche** (github-aws 0.2.0, 10 -> 27 vectors): multi-value conditions
  (logical OR; one loose value poisons the list), `aud` pinning + default-owner-URL mismatch,
  absent-context-key semantics, `job_workflow_ref`/`repository_id`/`environment` pins via the
  GitHub-specific condition keys AWS STS added Feb 2026, customized-sub reusable-workflow pins
  (documented example strings verbatim), and StringLike branch footguns (prefix collision,
  zero-width `*`, nested-branch spanning, case sensitivity). Matcher/schema additions: list
  patterns (AWS-only, OR) and claim-targeted conditions resolved from the `claims` map.
- `[ ]` **Feeder angle from the Feb 2026 AWS change** (AWS What's New posted 2026-02-02, slug
  2026/01): STS now validates SELECT GitHub/GitLab/CircleCI/Google/OCI claims as trust-policy
  condition keys (GitHub: actor, actor_id, job_workflow_ref, repository, repository_id,
  repository_owner_id, workflow, ref, environment, enterprise_id -- not available in session;
  the announcement also names resource control policies). Checkov's
  AWS OIDC checks reason only about `sub`; GitHub's own AWS how-to still says custom claims are
  unavailable in AWS (docs contradiction). Both are vector-backed upstream opportunities.
- `[x]` **GitLab path-reuse follow-up:** verified from primary sources and folded into
  `gitlab-aws-path-reuse-no-projectid` (0.1.1). The burn is broader than AWS's note says --
  GitLab's route-model callbacks burn EVERY path-vacating flow (delete, rename, transfer;
  commit f7335ef7e, milestone 19.1) -- but non-retroactive, path-based subs only, original
  project exempt, and undocumented in GitLab's own user docs (AWS's WIF page is the only prose
  source). Grade stays dangerous: the mitigation is platform-side; the policy still pins
  nothing immutable.
- `[~]` **Non-GitHub issuers (breadth — incumbents cover this poorly).**
  - `[x]` GitLab → AWS: `src/subvectors/gitlab.py` grammar (default `project_path:` + immutable
    `project_id:` forms) + 10 cited vectors (`vectors/gitlab-aws.json`). Covers group-wide/subgroup
    wildcards, ref_type confusion, the no-merge_request-marker MR admission, and path-reuse.
  - `[x]` GitLab → Azure FIC and GitLab → GCP tranches (reuse azure-fic-exact / gcp-cel).
    GCP (gitlab-gcp 0.1.0, 6 vectors): the JSON-string type trap -- CEL heterogeneous equality
    makes `assertion.project_id == 20` always-false (fail-closed) and `!= 20` always-true
    (fail-OPEN, a vacuous exclusion guard) because GitLab mints claim values as strings; cel.py
    gained int literals + CEL-typed equality (cross-type false, bool not numeric) to encode it.
    Azure (gitlab-azure 0.1.0, 6 vectors, ZERO matcher changes): classic FIC exact match forces
    one credential per ref against Azure's hard cap of 20 FICs per identity (verified verbatim);
    the AWS-StringLike wildcard habit is a silent literal; and because the default sub carries
    only the mutable project_path (no project_id -- classic FIC references issuer+subject+audience
    only), a path-reuse squatter mints a byte-identical sub the FIC cannot distinguish. The
    project_id-led sub is the durable pin. GROUND-TRUTH note (an adversarial verifier wrongly
    claimed "the sub must lead with project_path"): GitLab source `project_ci_cd_setting.rb`
    defines `SUB_CLAIM_LEADING_COMPONENTS = %w[project_path project_id]`, so a `project_id:20:...`
    sub IS producible -- this confirms both `gitlab-az-fic-immutable-projectid-exact-match` and the
    shipped `gitlab-aws-immutable-projectid-sub-stringequals` + the `gitlab.py` grammar.
  - `[ ]` Bitbucket, CircleCI, Terraform Cloud issuer grammars + vectors.
  - `[x]` Multi-key AWS consumer -- shipped as **`aws-all`** (github-aws 0.3.0), a composite
    modeling a full IAM Condition block instead of the sketched `aws-stringequals-all`: `of`
    lists ANDed AWS string sub-conditions, so operators can MIX (StringEquals aud + StringLike
    sub, the documented AWS shape) and each key keeps claim targeting + values-OR lists. 5
    vectors including GitHub's documented aud+sub policy and AWS's branch-wildcard example as
    evaluated blocks.
  - `[x]` **Upgrade GitLab caution vectors to evaluated multi-key pins** (gitlab-aws 0.2.0,
    6 aws-all vectors): GitLab's documented sub+namespace_id+project_id triple pin and AWS's
    two-key example as evaluated blocks, the squatter rejected by the id keys, ref_protected
    guard match/reject, and the pipeline_source MR gate (graded dangerous: it changes which
    EVENT, not who -- developer branch pushes still sail through). Verified claim forms:
    ref_protected/project_id/namespace_id/pipeline_source are all JSON STRINGS in the token
    ("true", "20", "push"). Bonus doc finding recorded in the suite description: GitLab's two
    doc pages contradict each other on Self-Managed condition-key support (sub only vs
    sub+aud) -- a possible upstream GitLab docs issue.

## Corpus / product depth

- `[x]` **Flexible FIC tranche** (`azure-fic-flexible` consumer): shipped `src/subvectors/ffl.py`
  (a minimal expression evaluator -- `claims['<name>'] <op> '<comparand>'` clauses joined by
  `and`; `eq` exact, `matches` an anchored non-path-aware glob with `?`=one char / `*`=multi),
  wired into the matcher, and `vectors/github-azure-flexible.json` (0.1.0, 8 vectors, GitHub
  issuer). Pins: the org-wide `repo:org/*` that classic FIC treats as a literal but flexible FIC
  HONORS; the `????` fixed-width `?` footgun (both directions); the documented reusable-workflow
  `sub`+`job_workflow_ref` `and` pin; and the pull_request + subject-scanner blind spot (flexible
  FIC nulls `subject`). PREVIEW, version-stamped (page updated 2026-06-15, languageVersion 1).
  Adversarial pass: 8/8 clean, 0 blockers. GitLab side ALSO shipped (`gitlab-azure-flexible.json`
  0.1.0, 5 vectors): GitLab flexible FIC references ONLY `sub` (no job_workflow_ref, no
  project_id), so unlike GitHub there is no second claim to `and` in -- encoded as the
  path-reuse squatter that even an exact `eq` cannot exclude, and the project_id-led sub as the
  ONLY immutable lever (bake the id into the sub, since it is not a separate matchable claim).
  Adversarial pass: 5/5 mechanically clean; one attribution blocker fixed (immutability quote
  re-sourced). Remaining: Terraform Cloud flexible FIC (sub-only, new issuer -- needs the TFC
  `organization:...:workspace:...:run_phase:...` sub grammar researched first).
- `[i]` **Citation map for GitLab project_id facts** (learned across two verify rounds, so future
  vectors cite right the first time): the STRONG immutability wording -- "globally unique and
  remains the same for the entire lifetime of the project, including across group renames, project
  renames, and project transfers" -- is VERBATIM on `docs.gitlab.com/ci/cloud_services/aws/`; the
  SHORTER "...for the lifetime of the project" is on `id_token_authentication`. project_id-led-sub
  PRODUCIBILITY (project_id may be the first sub component) is documented in NO GitLab doc page --
  only in source: `project_ci_cd_setting.rb` `SUB_CLAIM_LEADING_COMPONENTS = %w[project_path
  project_id]`. Cite that file for producibility; a rendered-page fetch may miss the immutability
  sentence, so prefer the cloud_services/aws source for it.
- `[ ]` **Judgment catalog.** Write the graded over-permission patterns (`pull-request`,
  `wildcard-repo`, `org-wide`, `wildcard-suffix`, `tag-ref`, `environment-scoped`,
  unprotected-branch) as a citable reference page; consider stable pattern IDs.
- `[ ]` **Immutable-format completeness.** Rename/transfer trigger vectors; `job_workflow_ref`
  grammar (stays mutable, not `@id`-suffixed); custom subject-claim templates.
- `[ ]` **Promote key vectors `documented` -> `observed`** by confirming against a real issuer/
  cloud once (optional, low-priority live check). Priority candidate:
  `gh-aws-branch-wildcard-zero-width` -- AWS never says `*` matches "zero or more" verbatim
  (only "multi-character match wildcard" / "any combination of characters"), so the zero-width
  match rests on interpretation until observed via the IAM policy simulator or live STS.

## Upstream feeder PRs — each in its own target-repo session, tracked in oss-contributions

- `[ ]` **GitLab docs MR (ready to post): align Self-Managed AWS condition-key claim list.**
  Verified 2026-07-21: `doc/ci/secrets/id_token_authentication.md` line 191 says Self-Managed/
  Dedicated support "only the `sub` claim" as an AWS condition key, contradicting
  `doc/ci/cloud_services/aws/_index.md` line 55 ("only the `sub` and `aud` claims"), which was
  corrected by community MR !243076 (fixes closed docs-feedback issue #442261) touching only
  the AWS page. AWS's Default OIDC mapping (condition-keys reference) confirms `aud`+`sub` for
  any registered provider, so the one-line fix is aligning line 191 to "`sub` and `aud`".
  Direct docs MR per GitLab docs workflow (no issue-first); before posting, one authenticated
  search of gitlab-org/gitlab issues/MRs for an in-flight fix (unauthenticated search is
  401-limited). No gitlab.com credentials in this environment -- post from a session with
  GitLab auth, then track in oss-contributions.

- `[ ]` **CKV_AZURE_249 deepening PR.** After the first Checkov PR lands. Driven by the
  `pull_request`/tag/environment Azure vectors — the check passes patterns it should flag.
  Stronger angle now vectored: flexible FIC nulls the `subject` property and moves matching into
  `claimsMatchingExpression`, so any subject-only check is BLIND to a flexible-FIC rule entirely
  (`gh-flex-eq-pull-request-scanner-blindspot`). Confirm CKV_AZURE_249 reads only `subject`
  (`git log -S "claimsMatchingExpression"` in a Checkov clone) before framing — if unhandled,
  that is a coverage-gap finding, not just a shallow-pattern one.
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
  (github.com/Dashtid/subvectors); package + docs renamed; local working dir renamed to
  `c:\code-two\subvectors` (2026-07-16). Fully closed.
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
