# Backlog

Granular, current task list. Complements [`ROADMAP.md`](ROADMAP.md): the roadmap holds strategy,
phases, and rethink triggers; this holds the concrete next actions and the parking lot.

Success metric reminder (see ROADMAP): **bugs found and upstream PRs merged** is the score;
vectors added is an input. Prune this list toward that, not toward corpus size for its own sake.

Status keys: `[ ]` todo · `[~]` in progress · `[x]` done this cycle.

## In progress

- `[~]` **Checkov immutable-subject PR** (Slice 1). Deadline 2026-07-15. Ship the immutable `@id`
  regex fix only; raise the org-wide `repo:org/*` case as an open question (maintainer-documented
  as intended). **OPENED:** PR #7610 (immutable `@id` support across the four GH-OIDC checks); the
  org-wide `repo:org/*` case raised as the open question per plan. Sibling PR #7627 (CKV_AZURE_249
  `pull_request`) opened alongside. Both awaiting maintainer review; stays `[~]` until
  merged/closed.

## Next up — this repo, independent of the upstream PRs

- `[x]` **Grammar correctness fix (2026-08-18): `RepoSegment.immutable` used `or` where it needs
  `and`.** `src/subvectors/github.py` reported a one-sided `@id` subject (an id on the owner or the
  repo but not both) as immutable, but GitHub emits `@id` on both segments or neither, so that
  shape is *malformed* rather than rename-proof. Reachable, not latent: the two id groups in
  `_REPO_RE` are independently optional, so `parse_repo_segment` accepts one-sided input happily.
  Zero of 133 vectors hit the branch, so the corpus stayed frozen and coverage landed as two unit
  tests in `tests/test_github_grammar.py` (225 -> 227 green). `immutable` remains a two-state
  boolean, so a one-sided subject now reads the same as a legacy one; `owner_id`/`repo_id` on the
  dataclass still tell them apart. GitLab is unaffected -- `_SUBJECT_RE` makes `project_path:` and
  `project_id:` an alternation, so exactly one is ever set. subcheck shipped the identical bug
  (`34a42ce`, 2026-07-21) and corrected it in `423964f` (2026-07-30), three weeks ahead of this
  repo, so it needs no change now; if a one-sided vector is ever added, its vendored
  `github_subjects.json` fixture must be re-vendored with a matching `"format": "malformed"` entry.
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
  the announcement also names resource control policies). Checkov's AWS OIDC checks match only the
  `token.actions.githubusercontent.com:sub` condition key (`gh_sub_condition` in
  `checkov/common/util/oidc_utils.py`; verified against 3.3.16 / `d8aec9db`, 2026-08-31), so none
  of the new keys are graded; GitHub's own AWS how-to still says custom claims are unavailable in
  AWS (docs contradiction). Both are vector-backed upstream opportunities. Distinct from the
  multi-value gap below: this one is about which condition KEYS are read, that one is about how a
  single key's VALUE list is read.
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
  - `[~]` Bitbucket, CircleCI, Terraform Cloud issuer grammars + vectors. Terraform Cloud now
    spans THREE consumers (19 vectors): `terraform-azure-flexible` (6) + `terraform-gcp` (6) +
    `terraform-aws` (7). The GCP tranche is the payoff of the run_phase/immutable-id story: GCP CEL
    references ANY assertion claim, so the immutable terraform_organization_id/terraform_workspace_id
    the name-based sub omits ARE pinnable -- and Google's DOCUMENTED recommended condition pins
    exactly those (`assertion.terraform_organization_id=='..' && assertion.terraform_workspace_id=='..'`),
    plus a `terraform_run_phase=='apply'` gate. The immutable-id gap (open on Azure classic +
    flexible FIC) CLOSES on GCP. Also the shared-issuer spoof Google warns about (app.terraform.io
    is one issuer for all orgs; a workspace_name-only condition admits another tenant).
    **TFC -> AWS open question RESOLVED (2026-07-30): AWS does NOT expose terraform_*_id as
    condition keys, so the immutable-id gap PERSISTS on AWS -- exactly like Azure, unlike GCP.**
    Primary-source proof: the AWS OIDC condition-keys page (#condition-keys-wif) is a curated
    per-IdP allowlist with tabs for Default / GitHub / GitLab.com / CircleCI / Buildkite / OCI /
    Google -- and NO Terraform Cloud tab. Unlisted IdPs fall back to the Default mapping ("Use this
    mapping if your IdP is not listed in the tab options") = amr/aud/email/oaud/sub only. So the
    only lever for app.terraform.io is `app.terraform.io:sub` (name-based) plus the fixed `:aud`;
    HashiCorp's own documented policy pins exactly those two with StringEquals. The terraform_*_id
    ids ride IN the token but no AWS condition key references them -- one step sharper than
    azure-flexible, where the grammar merely can't see them. Clean three-way contrast: gap OPEN on
    AWS + Azure, CLOSED on GCP.
  - `[x]` CircleCI -> AWS: `circleci-aws` 0.1.0, 7 vectors. CircleCI is the STRUCTURAL OPPOSITE of
    Terraform Cloud, and the contrast is the payoff. (1) PER-ORG ISSUER: iss =
    oidc.circleci.com/org/<ORG_ID> and the AWS OIDC provider are both org-specific, so a different
    org's token fails issuer validation before conditions run -- cross-org spoofing is blocked
    STRUCTURALLY (no shared-issuer spoof, unlike TFC/GitLab/GCP). (2) IMMUTABLE-BY-CONSTRUCTION SUB:
    sub = org/<uuid>/project/<uuid>/user/<uuid>, all UUIDs, so pinning the sub is rename-proof by
    default -- the opposite of TFC's name-based sub. This is the first issuer to reach a `safe`
    grade on an exact sub pin without a name-reuse residual. (3) AWS registered exactly ONE custom
    key, `oidc.circleci.com/project-id` (project UUID) -- the AWS-recommended pin; other UUID claims
    (context-ids/org-id/pipeline-id) are NOT AWS-conditionable. (4) The SSH-RERUN escalation
    (novel, cited): `oidc.circleci.com/ssh-rerun`=true marks an interactive SSH debug session; such
    a token satisfies a normal project-scoped policy and CANNOT be reliably excluded in-policy (only
    project-id is a registered key; ssh-rerun was historically absent from claims_supported with a
    user-reported failure -- discuss thread 50863), so hardening is out-of-band (disable SSH debug
    at org/project level). (5) vcs-ref/vcs-origin are the only name-based levers (mutable, V2-token
    only, absent for webhooks) -- and a V2-shaped branch condition silently misses a V1/webhook
    token. Schema change: broadened the claim-name pattern to allow namespaced OIDC claim names
    (dots/slashes, e.g. `oidc.circleci.com/project-id`). Four new catalog tags (`wildcard-project`,
    `wildcard-user`, `vcs-ref`, `ssh-rerun`).
  - `[x]` Bitbucket -> AWS: `bitbucket-aws` 0.1.0, 6 vectors. The pre-build hypothesis ("like TFC,
    gap persists") was WRONG -- research corrected it: Bitbucket is structurally like CircleCI, so
    the immutable-id gap CLOSES BY CONSTRUCTION on AWS despite Bitbucket being absent from AWS's
    per-IdP allowlist (Default mapping, only <issuer>:sub / :aud conditionable, no custom key). Two
    reasons: (1) PER-WORKSPACE ISSUER (api.bitbucket.org/2.0/workspaces/{workspace}/.../oidc) ->
    structural cross-workspace isolation (the {workspace} slug in iss is mutable, but the immutable
    workspace UUID is in aud). (2) UUID-BASED SUB: {repositoryUuid}:{stepUuid} or
    {repositoryUuid}:{deploymentEnvironmentUuid}:{stepUuid}, all UUIDs -- the immutable repositoryUuid
    LEADS the sub, so pinning it is rename-proof with no AWS custom key. Signature footgun (a vector):
    stepUuid REGENERATES every run, so a full-sub StringEquals matches only the run that minted it and
    breaks on the next (must StringLike-wildcard the step). Also: branchName and the deploymentEnvironment
    NAME are mutable AND not in the Default mapping, so a Bitbucket AWS role CANNOT be restricted by
    branch, and the environment must be pinned by its deploymentEnvironmentUuid (middle sub segment),
    never by name. aud = ari:cloud:bitbucket::workspace/{uuid} (array when custom audiences added ->
    ForAnyValue). One new catalog tag (`volatile-sub`). No schema change (sub/aud are clean names).
    **All planned issuers now shipped: github, gitlab, terraform-cloud, circleci, bitbucket (5).**
    Clean AWS immutable-id-gap taxonomy: PERSISTS on a name-based sub with no key (Terraform Cloud);
    CLOSES via an AWS-registered key (GitHub repository_id, GitLab project_id); CLOSES BY CONSTRUCTION
    via a UUID sub + per-tenant issuer (CircleCI, Bitbucket).
  - `[x]` **Consumer depth (start): CircleCI -> GCP** (`circleci-gcp` 0.1.0, 6 vectors). GCP WIF
    federates a generic OIDC provider (issuer URI + JWKS + OIDC 1.0), so CircleCI works, registered
    with its per-org issuer. The payoff vs AWS: GCP's attribute_condition is CEL over the WHOLE
    assertion, so it can reference claims AWS's single registered key cannot -- pin
    oidc.circleci.com/project-id AND gate the branch via oidc.circleci.com/vcs-ref DIRECTLY (vcs-ref
    is not an AWS condition key, so on AWS a branch restriction could only be embedded in the V2 sub).
    Required a matcher extension: **cel.py now supports CEL map indexing `assertion['<claim>']`** --
    the only way to address a claim name with dots/slashes (namespaced OIDC claims); grounded in
    cel-spec map-access + GCP's own special-char bracket example (assertion.attributes['https://.../SAML/...']).
    5 new cel unit tests. No new catalog tags. Out of scope (string-claim tranche): ssh-rerun (bool)
    and context-ids (array) -- referenceable in principle, but the corpus models claim values as
    strings, so a faithful bool/array comparison isn't expressible yet.
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
  re-sourced). Terraform Cloud side ALSO shipped (`terraform-azure-flexible.json` 0.1.0, 6
  vectors, NEW issuer `terraform-cloud`): sub = `organization:{org}:project:{project}:workspace:
  {workspace}:run_phase:{plan|apply}`, name-based. The marquee vector is `run_phase:*` -- classic
  FIC needs "two federated identity credentials ... one that matches run_phase:plan and one that
  matches run_phase:apply" (HashiCorp azure-configuration, verbatim), and the wildcard collapses
  that plan/apply trust boundary. TFC is sub-only like GitLab but WORSE: no sub customization, so
  no immutable-id lever exists at all (the terraform_*_id claims are unreachable). Adversarial
  pass: 6/6 clean, 0 blockers. **Flexible FIC now covers all three issuers Microsoft supports
  (GitHub, GitLab, Terraform Cloud) -- consumer complete.** Two new judgment-catalog tags added
  (`run-phase-wildcard`, `wildcard-workspace`).
- `[i]` **Citation map for GitLab project_id facts** (learned across two verify rounds, so future
  vectors cite right the first time): the STRONG immutability wording -- "globally unique and
  remains the same for the entire lifetime of the project, including across group renames, project
  renames, and project transfers" -- is VERBATIM on `docs.gitlab.com/ci/cloud_services/aws/`; the
  SHORTER "...for the lifetime of the project" is on `id_token_authentication`. project_id-led-sub
  PRODUCIBILITY (project_id may be the first sub component) is documented in NO GitLab doc page --
  only in source: `project_ci_cd_setting.rb` `SUB_CLAIM_LEADING_COMPONENTS = %w[project_path
  project_id]`. Cite that file for producibility; a rendered-page fetch may miss the immutability
  sentence, so prefer the cloud_services/aws source for it.
- `[x]` **Judgment catalog.** Shipped `docs/JUDGMENT-CATALOG.md`: all 65 `judgment.patterns` tags
  grouped into 10 canonical families (`scope-repo`, `scope-ref`, `scope-tag`, `event-trust`,
  `mutable-identity`, `immutable-pin`, `composite`, `environment`, `type-trap`, `detection-gap`),
  each with a definition, mechanism, typical grade, and example vector. Stable, citable pattern
  IDs. `tests/test_judgment_catalog.py` guards both directions (every corpus tag documented; every
  cited example id real), so the vocabulary can't sprawl silently. Follow-up parked in the file's
  Vocabulary note: a consolidation pass could collapse the near-synonyms (`org-wide`/`wildcard-repo`,
  `path-based`/`path-only`/`path-reuse`, `always-false`/`vacuous-guard`) into a smaller set.
- `[ ]` **Immutable-format completeness.** Rename/transfer trigger vectors; `job_workflow_ref`
  grammar (stays mutable, not `@id`-suffixed); custom subject-claim templates.
- `[~]` **Promote key vectors `documented` -> `observed`** — no longer optional/low-priority:
  **DECISION TAKEN 2026-08-22: cloud sandbox is IN SCOPE** (personal free-tier, personal gear;
  the observed:documented ratio is the corpus's real quality metric; it read 0:133 at decision time
  and **6:127 after the 2026-08-29/30 runs** — experiments 1-4 done, 5 remains).
  **[i] PREPPED 2026-08-25: turnkey now.** The schema gives `observed` teeth (a required
  `observation` block: method/date/evidence, forbidden on `documented`; enforced by
  `tests/test_vectors.py`), and [`docs/OBSERVED-PROMOTION.md`](docs/OBSERVED-PROMOTION.md) is the
  runbook — exact `aws iam simulate-custom-policy` commands per experiment, setup, and the
  promotion steps. What remains is human: a cloud login, then each experiment is minutes.
  Machine state (probed 2026-08-22): no AWS CLI, no gcloud; `az` 2.89.1 installed but logged out —
  so the session that runs this starts with account setup (~15 min), then each experiment is
  minutes. `aws iam simulate-custom-policy` creates NO resources and is the workhorse.
  **[+] RUN 2026-08-29 — experiments 1-3 (the AWS-simulator half) complete.** aws-cli 2.36.33
  installed via winget; IAM user `subvectors-probe` (IAMReadOnlyAccess only). All six simulator
  calls returned the expected decision, controls included: (1) StringEquals AND StringLike are
  case-sensitive (case-flipped pattern -> implicitDeny, same-case control -> allowed) — the
  doc-vs-third-party contradiction settled in the docs' favor; (2) `*` crosses `:` and `/`
  (org-wide pattern admitted a subject spanning both; other-org control denied); (3) zero-width
  `*` confirmed (`main*` matched `main` exactly, and `main2`). Five vectors promoted with
  observation blocks (github-aws 0.3.1): case-mismatch-rejected, org-wide-wildcard-repo,
  repo-wide-wildcard-suffix, ref-wildcard-spans-nested-branch, branch-wildcard-zero-width.
  Provenance: 128 documented / 5 observed. Harness note for the next run: AWS CLI v2 auto-parses
  JSON-looking args, and `--policy-input-list` silently mis-handles both inline JSON and file://
  — build the full request with `--cli-input-json` (policy as an escaped string). Remaining:
  experiment 4 (needs a temporary iam:CreateRole/DeleteRole + OIDC-provider create/delete attach
  on the probe user, then detach) and experiment 5 (needs a GCP account).
  **[+] EXPERIMENT 4 RUN 2026-08-30 — the run's best finding.** Probed `iam:CreateRole` with a
  GitHub-OIDC trust policy three ways: (a) the vector's poisoned list
  `["repo:octo-org/octo-repo:ref:refs/heads/main", "repo:octo-org/*"]` -> **ACCEPTED**;
  (b) the runbook's `["repo:acme/x", "*"]` with a literal `*` value -> **ACCEPTED**;
  (c) no condition at all -> **REJECTED**, `MalformedPolicyDocument`: trust policy "must
  evaluate, using StringEquals, StringLike or StringEqualsIgnoreCase,
  token.actions.githubusercontent.com:sub or ...:job_workflow_ref which is not scoped to all."
  So AWS checks that a `sub` condition EXISTS and is not `*`-scoped-to-all, but does NOT inspect
  the remaining values of an OR-list — the 2023 sub-less bug is closed at creation, the 2026
  multi-value one is open. `gh-aws-multivalue-loose-value-poisons-list` promoted to `observed`
  with both the evaluation and creation halves in its evidence (github-aws 0.3.2, 127/6).
  Incidental: `create-role` does NOT require the OIDC provider to exist first (probe A succeeded
  before provider creation) — a role can be minted trusting a federated principal that is absent.
  Cleanup verified: role and provider deleted, `get-role` -> NoSuchEntity, `list-roles`/
  `list-open-id-connect-providers` both empty. **Feeder angle (re-scoped 2026-08-31 after reading
  checkov source):** the Checkov gap is real but it is NOT this vector's list. `repo:org/*` is an
  intentional pass in CKV_AWS_358/393 (code comment "this is a pass with a warning", PR #7221,
  locked by a customer regression fixture), so `["repo:org/repo:ref:refs/heads/main",
  "repo:org/*"]` passes for that reason and would be refuted in review. The demonstrable gap is a
  value the check rejects standing alone becoming invisible inside a list — `["repo:org/repo:ref:
  refs/heads/main", "*"]` PASSES CKV_AWS_393 (measured through checkov's `Runner`). See ROADMAP
  "Upstream integration targets" for the per-check detail.
  Run in this order (each promotes vectors and each is independently publishable). Status:
  1-4 DONE (08-29/30, see above); 5 open (needs a GCP project); an Azure token-exchange
  observation (AADSTS700213) is the natural 6th — needs `az login` + a throwaway GitHub Actions
  workflow minting a token against an Entra app FIC.
  1. **AWS `StringLike` case-sensitivity** — docs say case-sensitive; third-party references
     circulate the opposite. Simulator with upper/lowercased subject pairs. Settles a live
     contradiction; the most quotable single result.
  2. **Does `*` cross `:` and `/`?** — AWS states no rule for the most security-relevant wildcard
     behaviour in CI/CD federation. Simulator: pattern `repo:acme/*` vs subject
     `repo:acme/api:ref:refs/heads/main`. Promotes the entire wildcard-footgun family.
  3. **Zero-width `*`** (`gh-aws-branch-wildcard-zero-width`) — `main*` vs `main`. The vector
     already flags itself as interpretation-based.
  4. **June-2025 guardrail probe** — does role CREATION accept `values = ["repo:acme/x", "*"]`
     (loose value hidden in a list)? If yes: AWS blocked the 2023 bug and left the 2026 one open.
     Needs one real `iam create-role` + immediate delete.
  5. **GCP unquoted-int** (needs GCP account) — does WIF provider creation ACCEPT
     `assertion.project_id == 20`? The one load-bearing claim in the whole corpus with an
     unverified empirical step: cel.py's cross-type semantics are spec-confirmed, but if GCP
     rejects the expression at write time the fail-open angle collapses to a footnote.

## Upstream feeder PRs

- `[~]` **CKV_AWS_358 + CKV_AWS_393 multi-value fix — OPENED 2026-08-31 as Checkov PR #7665.**
  https://github.com/bridgecrewio/checkov/pull/7665 (commit `b7a3443d5`, 6 files, MERGEABLE).
  Thread tracked at `oss-contributions/checkov/7665-multivalue-sub/`. **The first feeder the
  observed-promotion programme produced** — the corpus vector
  `gh-aws-multivalue-loose-value-poisons-list` (promoted 2026-08-30) raised the question of
  whether the scanners grading these policies read the whole value list; they do not. Both AWS
  GitHub-OIDC checks inspected only ONE element and passed on the first safe value, so IAM's
  OR-over-values makes the tight neighbour irrelevant. Repro on unfixed upstream main
  `d8aec9db`: the role check passed `[tight, "*"]`. Fix classifies every value; mirrored
  fixtures (`fail-multivalue-wildcard`, `fail-multivalue-abusable`, `pass-multivalue-pinned`)
  in both suites; regression-guarded, flake8 clean, 22 tests green.
  [!] **The `iam:CreateRole` result was CUT from the PR.** The 2026-08-30 probe recorded the
  condition operator for the evaluation half but NOT for the `["repo:acme/x", "*"]` creation
  half — the first thing a skeptical reviewer would ask. The PR rests only on Checkov's own
  source plus two AWS doc quotes. **Fix the observation before citing it anywhere public:**
  re-run probe (b) recording the operator, or narrow the evidence string to what was actually
  captured.
  [!] **The first cut of this fix was wrong and the review caught it.** Making CKV_AWS_393 fail
  on any unsafe value *anywhere in the Condition* broke the OR/AND distinction: IAM ORs the
  values of ONE key but ANDs across operators and condition blocks, so a policy pinned tightly
  in `StringEquals` stays safe even beside a vacuous `StringLike sub = "*"` — the first cut
  flagged it, a false positive, and diverged from CKV_AWS_358's own behaviour. Scoped back to
  per-condition ("first sub condition decides", unchanged upstream semantics) and pinned with a
  cross-operator parity fixture whose verdicts match unfixed `d8aec9dba` exactly. **Lesson for
  the corpus: the multi-value vectors encode OR within a key; they do NOT license "any loose
  value anywhere fails", and a scanner that conflates the two is wrong in the safe direction.**
  Next: await the maintainer sweep (window closes 2026-09-03); rebase if #7610 lands first.
  `CKV_GCP_125`'s first-match-only `re.search` over CEL disjuncts is the same bug class and is
  the deliberate follow-up, held back so as not to triple this PR's review surface.
- `[ ]` **GitLab docs MR (ready to post): align Self-Managed AWS condition-key claim list.**
  Verified 2026-07-21: `doc/ci/secrets/id_token_authentication.md` line 191 says Self-Managed/
  Dedicated support "only the `sub` claim" as an AWS condition key, contradicting
  `doc/ci/cloud_services/aws/_index.md` line 55 ("only the `sub` and `aud` claims"), which was
  corrected by community MR !243076 (fixes closed docs-feedback issue #442261) touching only
  the AWS page. AWS's Default OIDC mapping (condition-keys reference) confirms `aud`+`sub` for
  any registered provider, so the one-line fix is aligning line 191 to "`sub` and `aud`".
  Direct docs MR per GitLab docs workflow (no issue-first); before posting, one authenticated
  search of gitlab-org/gitlab issues/MRs for an in-flight fix (unauthenticated search is
  401-limited). Post from an environment with GitLab authentication configured.

- `[~]` **CKV_AZURE_249 deepening PR.** OPENED as Checkov PR #7627 ("CKV_AZURE_249 should flag
  `pull_request` OIDC subjects"). Driven by the `pull_request`/tag/environment Azure vectors — the
  check passes patterns it should flag.
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
- `[~]` **Cartography scoping issue + failing fixture** (Slice 3). `intel/aws/iam.py`
  "# TODO support conditions"; minimal additive proposal (sub/aud as edge properties). Issue-first.
  Done and advanced: issue #3078 filed, maintainer-requested, now open as PR #3088
  (`feat/iam-trust-conditions`, tier-1); reassess 2026-09-30.
- `[ ]` **Consumer-adoption outreach.** Where a tool's matching diverges from the suite (zizmor,
  Prowler, GitHound), offer a vector-derived test PR. This is the adoption signal to watch.
  **First consumer recorded 2026-08-25: [subcheck](https://github.com/Dashtid/subcheck).** It no
  longer hand-vendors subject strings - it pins the released corpus (`subvectors==0.2.1`, a dev
  dependency) and runs a three-direction differential check (provenance / coverage / mis-parse) in
  CI, plus a weekly canary against this repo's `main`.
  **And the corpus immediately did its job.** The check found a real bug in that consumer: for the
  documented combined customization subject
  `repo:O/R:environment:prod:job_workflow_ref:...` (vector `gh-aws-custom-sub-combined-environment-jwr`),
  subcheck's decoder let `environment` swallow the whole `job_workflow_ref` tail, so a policy
  correctly pinning `environment: prod` failed against a token whose environment really was `prod`.
  Fixed in subcheck 0.3.0. It is an own-consumer find rather than a third-party one, so it does not
  count toward the "bugs found in shipping tools" metric - but it is the first evidence that the
  corpus catches what code review did not, which is the whole premise.
- `[ ]` **Prowler Entra-FIC gap** — Prowler ships no federated-identity-credential checks at all
  (verified), so Azure FIC subject grading is unrepresented there. Worth a vector-derived
  contribution once the Checkov and Cartography threads settle.
  **Re-verified 2026-08-26, and the ground moved.** Azure half still holds: `prowler/providers/
  azure/services/entra/` has no FIC check (nearest is `entra_app_registration_credential_not_
  expired`, about credential expiry, not subjects), and repo-wide code searches for
  `federatedIdentityCredentials` / `federated_identity` return nothing.
  **But Prowler has entered this space on GCP.** `iam_workload_identity_pool_provider_attribute_
  condition` (merged, still in `changelog.d` = unreleased, added by maintainer `pedrooot`) FAILs a
  WIF provider that trusts a hardcoded multi-tenant issuer set (GitHub Actions, GitLab.com,
  accounts.google.com, app.terraform.io) with no `attributeCondition`.
  **[!] Do NOT file "it passes a present-but-useless condition" as a bug.** That was this
  session's first read and it is wrong: the check's own metadata `Notes` states verbatim *"This
  check verifies that an attribute condition is present; it does not evaluate whether the
  condition's expression is sufficiently restrictive."* A maintainer-documented boundary, not a
  defect - filing it would be the stale-issue mistake the OSS norms exist to prevent.
  **What that boundary actually is: the corpus's differentiator, stated by someone else.** The
  suite already grades cited cases that are present-but-non-restrictive and would sail through:
  `gh-gcp-trivial-condition-any-repo-danger` (`assertion.repository_owner_id != ''`, a pure
  tautology admitting all of github.com), `gitlab-gcp-int-negation-always-true`
  (`assertion.project_id != 20` - vacuously true, string claim vs int literal),
  `tfc-gcp-workspace-name-shared-issuer-spoof` (no org restriction on a shared issuer), and
  `gh-gcp-owner-only-org-wide-danger`. The first two are mechanically decidable without full CEL
  evaluation, so a follow-up check is implementable rather than philosophical.
  **This is the compounding test from CLAUDE.md answered live:** an incumbent shipped an
  overlapping feature and the corpus became MORE consumable, not obsolete. It is also the
  adoption signal to watch - but it is a NEW upstream thread, and the gating condition above
  (Checkov + Cartography settling, still 0 merged) has not changed. Owner decision before acting.

## Repo hygiene / infra

- `[x]` LICENSE (Apache-2.0, code) + `vectors/LICENSE` (CC0-1.0, data) + README licensing.
- `[x]` CI (GitHub Actions, pytest on 3.11-3.13).
- `[x]` `.gitattributes` (LF normalization).
- `[x]` **CONTRIBUTING.md** — shipped: the two invariants (matcher reproduces `expect`; every
  claim cited by the vector's own sources), the vector-field table, the per-consumer rule shapes,
  the grade rubric, and the add-a-vector workflow (incl. `scripts/coverage.py --write`).
- `[x]` **Name decided: `subvectors`.** GitHub repo created
  (github.com/Dashtid/subvectors); package + docs renamed; local working dir renamed to
  match (2026-07-16). Fully closed.
- `[x]` **Vector coverage summary** in the README (counts by issuer x consumer): generated by
  `scripts/coverage.py` between `<!-- COVERAGE -->` markers, with `tests/test_readme_coverage.py`
  as a drift guard so it can never go stale. Currently 14 suites / 133 vectors / 6 consumers.
- `[x]` **Publish decision — RESOLVED 2026-08-25: PyPI, and it earned its keep.** The old answer
  here ("likely repo-only") was written before there was a consumer. `subvectors` 0.2.1 ships via
  trusted publishing (OIDC, no stored token) with the vectors packaged INSIDE the wheel
  (`force-include` + `importlib.resources`), which is the part that mattered: a consumer pins the
  corpus as a dependency instead of hand-vendoring subject strings. That is what let subcheck run a
  pinned three-direction drift check in CI, and that check immediately caught a real decoder bug —
  so publishing is what turned "first consumer" from a claim into a tested seam.
  Verified live 2026-08-28: `pypi.org/pypi/subvectors/json` → 200 at 0.2.1.

## Validation (not code)

- `[ ]` **Practitioner sanity-check.** Ask 1-2 cloud-security practitioners whether the
  shallow-FIC-lint / reach-widening problem this corpus targets is one they actually hit. A flat
  response is a signal to narrow scope.
- `[ ]` Re-read the ROADMAP rethink triggers before any strategy override.

## Later / ideas

- `[ ]` "caniuse for workload identity federation": issuer-claims x cloud-consumer capability
  matrix (a knowledge play the vectors can back).
- `[ ]` Contribute the corpus to a neutral home (OpenSSF WG / sigstore) if that path opens — the
  maintainer-role outcome.
- `[ ]` Optional live read-only mode against a free-tier sandbox.
