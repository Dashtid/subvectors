# Judgment catalog

The reference matcher answers one question — *does subject S satisfy condition C?* — mechanically.
This catalog is the **other** layer: *is C safe?* That grade is human-authored in each vector's
`judgment` block, backed by a citation, and the matcher never reads it. The two are kept apart on
purpose: the match is falsifiable, the safety grade is a documented claim.

Every graded vector tags its `judgment.patterns` with one or more **pattern IDs** from this
catalog. The IDs are stable — cite them from a downstream tool, a review, or an upstream PR
("this waves through the subvectors `org-wide` pattern"). Patterns **compose**: a single vector
usually carries several (e.g. `exact-ref` + `name-based` + `no-id-pin`), and the grade reflects
the interaction, not any one tag.

## How to read a grade

- **safe** — tightly scoped *and* durable: an exact single-ref match, or a pin on an immutable id.
- **caution** — works, but carries a residual: a mutable/name-based identity, a wildcarded ref on
  an otherwise-pinned project, or scoping that leans on a protection rule elsewhere.
- **dangerous** — a real over-permission: an org/repo wildcard, a `pull_request` subject, any-branch
  admission, or a mutable-identity reclaim (path-reuse / cybersquat).

A grade is never computed from the tags — the tags classify *why*; the grade is the authored verdict.

## Pattern families

Ten families group every pattern the corpus uses. Family IDs are the coarse category; the
per-row **Pattern ID** is what a vector actually tags and what you cite.

### Repository / org scope — `scope-repo`

Over-broad scoping on the owner/repo axis: a wildcard (or an absent condition) lets unintended
repositories or whole orgs assume the identity. **Typically dangerous** (caution only when a
narrow, non-org-spanning suffix is involved).

| Pattern ID | Meaning | Grade | Example |
| --- | --- | --- | --- |
| `org-wide` | Wildcard admits every repo in an owner/org | dangerous | `gh-aws-org-wide-wildcard-repo` |
| `wildcard-repo` | `*` in the repository position; any repo matches | dangerous | `gh-aws-org-wide-wildcard-repo` |
| `wildcard-group` | GitLab group-level `*`; any project in the group | dangerous | `gitlab-aws-group-wide-wildcard-stringlike` |
| `subgroup-nesting` | `*` spans subgroup depth (`group/*` hits every nesting level) | dangerous | `gitlab-aws-group-wide-wildcard-stringlike` |
| `wildcard-suffix` | Trailing `*` after a prefix; everything sharing the prefix | caution/dangerous | `gh-aws-repo-wide-wildcard-suffix` |
| `repo-wide` | Repo pinned, but nothing narrower (any ref/env of it) | caution | `gh-aws-repository-id-immutable-pin` |
| `no-repo-scope` | The condition never constrains the repo/owner at all | dangerous | `gh-gcp-trivial-condition-any-repo-danger` |
| `confused-deputy` | A trivially-true condition trusts any repo (classic confused deputy) | dangerous | `gh-gcp-trivial-condition-any-repo-danger` |
| `wildcard-workspace` | `*` at the TFC workspace segment; any workspace in the project | dangerous | `tfc-flex-workspace-wildcard-project-wide` |
| `shared-issuer-spoof` | No org/tenant restriction on a shared issuer; another tenant's token satisfies it | dangerous | `tfc-gcp-workspace-name-shared-issuer-spoof` |
| `wildcard-project` | `*` at the CircleCI project segment; any project in the org | dangerous | `circleci-aws-project-wildcard-org-wide` |
| `wildcard-user` | `*` at the CircleCI user segment; any pipeline-triggering user | caution/dangerous | `circleci-aws-immutable-sub-user-wildcard` |

### Ref / branch scope — `scope-ref`

Over-broad scoping on the ref axis: any branch — including an attacker-pushable, unprotected one
— satisfies the condition. **Dangerous** for open wildcards; **caution** for prefix collisions.

| Pattern ID | Meaning | Grade | Example |
| --- | --- | --- | --- |
| `wildcard-ref` | `*` in the ref/branch position; any branch matches | dangerous | `gh-flex-matches-branch-wildcard` |
| `unprotected-ref` | Admits a ref with no protection rule (attacker-pushable) | dangerous | `gh-flex-matches-branch-wildcard` |
| `unprotected-branch` | Admits any branch, including an unprotected one | caution | `gh-aws-branch-prefix-collision` |
| `any-branch` | A `startsWith`/prefix pattern any branch clears | caution | `gh-gcp-branch-prefix-startswith` |
| `wildcard-reftype` | `*` over the GitLab `ref_type` segment (branch OR tag) | dangerous | `gitlab-aws-ref-type-confusion-wildcard` |
| `ref-type-confusion` | Branch vs tag collapsed; a tag named like the branch matches | dangerous | `gitlab-aws-ref-type-confusion-wildcard` |
| `branch-prefix-collision` | A prefix pattern collides with a longer branch name | caution | `gh-aws-branch-prefix-collision` |
| `prefix-match` | Unanchored prefix admits more than intended | caution | `gh-gcp-branch-prefix-startswith` |
| `vcs-ref` | CircleCI V2 `vcs-ref` branch/tag pin; name-based, mutable, V2-token-only | caution | `circleci-aws-vcs-ref-branch-pin-v2` |

### Tag refs — `scope-tag`

Pinned to a tag, which is movable and (by default) unprotected. **Caution**: a maintainer or a
compromised token can repoint the tag to attacker-controlled code.

| Pattern ID | Meaning | Grade | Example |
| --- | --- | --- | --- |
| `tag-ref` | Pinned to a tag; tags are movable/unprotected by default | caution | `gh-aws-jwr-condition-key-tag-pin-mutable` |
| `mutable-ref-pin` | Pins a mutable ref (tag) rather than an immutable SHA | caution | `gh-aws-jwr-condition-key-tag-pin-mutable` |

### Event / trigger trust — `event-trust`

Trusts *which event* ran, not *who* — usually admitting unreviewed or proposed code.
**Dangerous**: a `pull_request` / merge-request pipeline runs unmerged changes.

| Pattern ID | Meaning | Grade | Example |
| --- | --- | --- | --- |
| `pull-request` | Trusts the `pull_request` subject (unmerged proposed code) | dangerous | `gh-aws-pull-request-subject` |
| `merge-request` | GitLab MR pipeline admitted (no MR marker in the sub) | dangerous | `gitlab-aws-merge-request-source-branch-admitted` |
| `no-event-guard` | No `pipeline_source`/event gate; any trigger qualifies | dangerous | `gh-gcp-pull-request-danger` |
| `pipeline-source-gate` | Gates the event but not *who* (branch pushes still broad) | dangerous | `gitlab-aws-all-pipeline-source-gates-mr` |
| `run-phase-wildcard` | TFC `run_phase:*` admits both plan and apply, collapsing the phase separation | dangerous | `tfc-flex-run-phase-wildcard-collapses-plan-apply` |
| `run-phase-pin` | TFC `run_phase` gated to one phase (e.g. `== 'apply'`) — the positive counterpart | safe | `tfc-gcp-immutable-id-run-phase-apply` |

### Mutable identity (rename / path-reuse) — `mutable-identity`

Identity pinned by a mutable name or path with no immutable anchor. **Dangerous** where a reclaim
(path-reuse / cybersquat) mints the same subject; **caution** for a name-based baseline that is
otherwise tightly scoped.

| Pattern ID | Meaning | Grade | Example |
| --- | --- | --- | --- |
| `name-based` | Identity pinned by a mutable name/path, no immutable id | caution/dangerous | `gh-gcp-owner-only-org-wide-danger` |
| `no-id-pin` | The condition pins no immutable id (rename/reuse exposure) | caution/dangerous | `gitlab-aws-exact-branch-namebased-stringequals` |
| `path-based` | Sub built on the mutable `project_path` | dangerous | `gl-flex-eq-path-reuse-squatter-no-lever` |
| `path-only` | Only the path is pinned; nothing immutable | dangerous | `gitlab-aws-path-reuse-no-projectid` |
| `path-reuse` | A reclaimed path mints a byte-identical sub (squatter) | dangerous | `gitlab-aws-path-reuse-no-projectid` |
| `cybersquat` | Attacker recreates a deleted owner/repo name | dangerous | `gh-gcp-name-recycle-danger` |
| `rename-break` | A rename silently breaks a name-based pin | caution | `gh-gcp-name-pin-breaks-on-rename` |
| `classic-sub` | Classic (non-immutable) subject; breaks at the immutable cutover | caution | `gh-gcp-classic-sub-immutable-break` |
| `immutable-break` | Immutable-format token no longer matches a classic pin | caution | `gh-gcp-classic-sub-immutable-break` |
| `no-project-id-pin` | Namespace pinned but not the immutable `project_id` | caution | `gitlab-aws-all-aws-example-namespace-pin` |
| `immutable-gap` | The consumer offers no lever to pin an immutable id | dangerous | `gl-flex-eq-path-reuse-squatter-no-lever` |

### Immutable pinning (the durable fixes) — `immutable-pin`

Pins an immutable identifier or an exact value — the safe end of the catalog. **Safe** on its own;
**caution** only when a residual wildcard remains elsewhere in the condition.

| Pattern ID | Meaning | Grade | Example |
| --- | --- | --- | --- |
| `immutable` | Pins an immutable id (owner/repo id, `project_id`) — rename-proof | safe | `gh-aws-immutable-exact-match` |
| `immutable-id` | Pins the numeric immutable id claim | safe | `gh-gcp-immutable-id-pin-safe` |
| `project-id-pin` | Pins `gitlab.com:project_id` (immutable) as a condition key | safe | `gitlab-aws-all-docs-triple-pin` |
| `project-id-sub` | Sub built on the immutable `project_id` | safe | `gitlab-aws-immutable-projectid-sub-stringequals` |
| `sha-pinned` | Pins a commit SHA ref — content-immutable | safe | `gh-aws-jwr-condition-key-sha-pin` |
| `rename-proof` | Survives rename/transfer via an immutable id | safe | `gh-gcp-immutable-id-survives-rename` |
| `exact-ref` | Exact single-ref match (no wildcard) | safe | `gh-aws-exact-branch-stringequals` |
| `exact-repo` | Exact owner/repo match | safe | `gh-gcp-owner-repo-ref-safe` |
| `eq` | Flexible-FIC `eq` (exact equality) | safe | `gh-flex-eq-exact-branch` |
| `custom-sub` | Customized sub-claim template pinned exactly | safe/caution | `gh-aws-custom-sub-jwr-exact` |

### Composite / multi-key conditions — `composite`

Multiple keys or values combined. An AND of guards strengthens; an OR value-list or a residual
wildcard weakens. **Grade tracks the tightest AND-clause and the loosest OR-value.**

| Pattern ID | Meaning | Grade | Example |
| --- | --- | --- | --- |
| `multi-key-and` | Full Condition block; ANDed keys must all hold | safe/caution | `gh-aws-all-documented-aud-sub-policy` |
| `multi-claim-and` | Flexible-FIC `and` across two claims | caution | `gh-flex-and-reusable-workflow-pin` |
| `aud-pinned` | Pins the `aud` claim (rejects default-owner-URL mismatch) | safe | `gh-aws-aud-pinned-official-action` |
| `namespace-id-pin` | Pins `gitlab.com:namespace_id` (group; changes on transfer) | caution | `gitlab-aws-all-aws-example-namespace-pin` |
| `ref-protected` | Requires `ref_protected=true` (protected ref only) | caution | `gitlab-aws-all-refprotected-guard-match` |
| `multivalue-or` | Multi-value condition (OR); the loosest value sets the boundary | safe/dangerous | `gh-aws-multivalue-two-repos-or` |
| `in-list` | CEL `in [...]` membership (OR over a set) | caution | `gh-gcp-in-list-multi-org` |
| `reusable-workflow-pin` | Pins `job_workflow_ref` (which reusable workflow ran) | safe/caution | `gh-aws-jwr-condition-key-sha-pin` |
| `reusable-workflow` | Reusable-workflow scenario (caller + workflow) | caution | `gh-flex-and-reusable-workflow-pin` |
| `job-workflow-ref` | Uses the `job_workflow_ref` claim | caution | `gh-flex-and-reusable-workflow-pin` |
| `set-operator` | `ForAllValues:`/`ForAnyValue:` qualifier on a condition | caution/dangerous | `gh-aws-foranyvalue-absent-environment-rejected` |
| `forallvalues-fail-open` | `ForAllValues` under an Allow passes vacuously when the claim is absent | dangerous | `gh-aws-forallvalues-absent-environment-fails-open` |

### Environment scoping — `environment`

Scoped to a named deployment environment: only as strong as that environment's protection rules
(required reviewers, branch restrictions). **Safe** when those exist, **caution** otherwise.

| Pattern ID | Meaning | Grade | Example |
| --- | --- | --- | --- |
| `environment-scoped` | Scoped to a deployment environment (as strong as its rules) | safe/caution | `gh-aws-environment-key-absent-claim-rejected` |
| `absent-key` | A condition key absent from the token → mismatch (fail-closed) | safe | `gh-aws-environment-key-absent-claim-rejected` |
| `percent-encoded` | A `:` inside a metadata value is minted as `%3A`; the pin must match the encoded form | safe/dangerous | `gh-aws-environment-colon-literal-pin-denies` |

### Type-level / expression traps — `type-trap`

The condition is well-formed but the *type* or *width* is wrong. Most **fail closed** (caution:
breakage, not exposure); the vacuous-negation cases **fail open** (dangerous).

| Pattern ID | Meaning | Grade | Example |
| --- | --- | --- | --- |
| `type-mismatch` | Cross-type comparison (JSON string vs number/bool) | caution | `gitlab-gcp-int-literal-never-matches` |
| `int-literal` | Bare int literal vs a string claim (never equal) | caution/dangerous | `gitlab-gcp-int-literal-never-matches` |
| `bool-literal` | Bare bool literal vs a string claim (never equal) | caution | `gitlab-gcp-bool-literal-never-matches` |
| `always-false` | The condition can never match (fail-closed breakage) | caution | `gitlab-gcp-int-literal-never-matches` |
| `always-true` | Negation of a type-mismatch matches everything (fail-OPEN) | dangerous | `gitlab-gcp-int-negation-always-true` |
| `vacuous-guard` | An exclusion guard that excludes nothing | dangerous | `gitlab-gcp-int-negation-always-true` |
| `fixed-width` | `????` matches only names of that exact length | dangerous | `gh-flex-question-fixed-width-footgun` |
| `wildcard-question` | `?` single-char width footgun | dangerous | `gh-flex-question-fixed-width-footgun` |
| `regex` | RE2 `matches()` anchoring / substring pitfalls | caution | `gh-gcp-matches-tag-regex` |
| `volatile-sub` | Pins a per-run volatile sub segment (e.g. Bitbucket `stepUuid`); an exact match breaks on the next run | caution | `bitbucket-aws-full-sub-stringequals-breaks-next-run` |

### Detection / tooling gaps — `detection-gap`

The rule is unsafe *and* hard to see: a scanner looking at the wrong field misses it entirely.
**Dangerous** — the over-permission compounds with undetectability.

| Pattern ID | Meaning | Grade | Example |
| --- | --- | --- | --- |
| `scanner-blindspot` | Rule invisible to subject-only scanners (flexible FIC nulls `subject`) | dangerous | `gh-flex-eq-pull-request-scanner-blindspot` |
| `ssh-rerun` | CircleCI SSH-debug-session token admitted; cannot be reliably excluded in-policy | dangerous | `circleci-aws-ssh-rerun-debug-token-admitted` |

## Vocabulary note

These IDs grew per-tranche, so some are near-synonyms (`org-wide` / `wildcard-repo`,
`path-based` / `path-only` / `path-reuse`, `always-false` / `vacuous-guard`). They are kept
distinct where a vector draws a real line, and grouped by family here. `tests/test_judgment_catalog.py`
enforces that **every** `judgment.patterns` tag in the corpus is documented above, so the
vocabulary cannot sprawl silently — a new tag must be filed under a family or CI fails. A future
consolidation pass may collapse the closest synonyms into a smaller canonical set; until then,
cite the family ID when you want the category and the pattern ID when you want the specific line.
