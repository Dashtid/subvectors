# Roadmap

Re-pointed 2026-07-05: the scanner/PR-gate plan ("oidc-reach v1") is dropped in favor of the
conformance vector suite + the upstream fixes it feeds. The compounding test: an incumbent
shipping an overlapping feature must ADD a consumer of this corpus, never obsolete it.

**Cadence discipline:** every slice is weeknight-sized and independently shippable. Ship the
slice, update this file, stop.

## Where this actually stands (2026-09-03)

**14 suites / 160 vectors** — 149 `documented`, 11 `observed` — 400 tests, CI green on 3.11-3.13,
published to PyPI (latest release v0.6.0; `github-aws` 0.8.0 is staged on `main` for the next cut).

**On "the corpus is feature-complete. Do not add vectors."** That line stood here from 2026-08-18
and the corpus has grown 133 -> 160 since. The line was right and is being kept, but it was
compressed to the point of being misread. What it means: **the planned MATRIX is complete** — all 5
issuers x 6 consumer semantics have shipped, and no vector should be added to fill a cell, round out
a set, or make a table look symmetrical. That is the librarian trap the scoreboard below names.
What it never meant is that a verified finding should go unencoded. Every vector added since
carries one: a documented contradiction, an over-permission shape a real policy reaches by a
plausible route, or a tool disagreement. **The test for a new vector is "what did I find?", not
"what is missing?"** — if the answer is a gap in a table, do not add it.

**The uncomfortable read on the scoreboard.** The last fortnight added 27 vectors and zero merged
upstream PRs. By this file's own primary metric that is an input, not progress, and it should not
be dressed up. Two things soften it and neither cancels it: three Checkov PRs are open and
unreviewed (the queue is not the author's to move), and the corpus found three real defects in its
OWN code this cycle — a CEL string decoder that silently lost a character, a GitHub grammar that
rejected a subject GitHub documents how to mint, and a GitLab claim that was simply false. A corpus
that audits itself is worth something. It is still not a merged PR.

What is actually open, in priority order:

1. **Upstream: three Checkov PRs, zero reviews, zero merged** — #7610 (immutable `@id` support),
   #7627 (CKV_AZURE_249), #7665 (the multi-value fix), plus cartography #3088. Ladder step 1 is
   spent on all of them. The tracked policy is to wait: a fourth PR opened while three sit
   unreviewed is volume, not signal. Next touch is a review landing or the 2026-10-15 close-by.
   A fourth is nonetheless *ready* — the select-claim-key gap (`gh_sub_condition` reads only the
   `:sub` key, so a policy pinning `ref` alone passes CKV_AWS_358 and CKV_AWS_393) is now backed by
   four vectors rather than an assertion.
2. **`documented` -> `observed`: 11 of 160.** This is the corpus's real quality metric and the
   number that most deserves to move. AWS experiments 1-4 are done and transcript-backed under
   `observations/`; **experiment 5 (GCP unquoted-int) remains and is the one load-bearing corpus
   claim still resting on spec alone** — it needs a GCP project. Two cheap GitHub-only probes are
   also queued and need no cloud account at all: whether `%` is escaped in the `%3A` substitution,
   and whether `job_workflow_ref` carries `@id` suffixes under immutable subject claims. Both are
   one scratch repo and one workflow that dumps the token's claims. See
   `docs/OBSERVED-PROMOTION.md` and the probes in BACKLOG.md.
3. **Cadence, decided 2026-09-03 and written into CLAUDE.md.** Nine releases went out in the ten
   days to 2026-09-02, five of them in the final two, and each one invited a `subcheck` pin bump
   that means re-deriving a fixture. Releases are now batched to one a week, cut Sunday evening so
   they land before `subcheck`'s Monday 06:00 UTC drift canary; Monday is `subcheck` day; a session
   edits only its own working directory. This file is the strategy record — the operational rules
   live in CLAUDE.md.
4. **Adoption is still one consumer.** `subcheck` pins a released artifact and its canary runs
   weekly against this repo's `main` (verified clean 2026-09-03 with the 0.8.0 work in place, and
   its allowlist is empty, so that green is real). The secondary metric — a tool that is not ours
   consuming the vectors, or a citation — reads zero. Outreach items are parked in BACKLOG.md and
   are deliberately not being pushed while the PR queue is stalled.

## How we measure success (read before adding vectors)

The corpus is the ENGINE, not the deliverable. Wycheproof matters because it found real bugs in
real crypto libraries, not because it is a tidy collection. Same scoreboard here:

- **Primary metric: bugs found and upstream PRs merged in shipping tools.** Each consumer's
  matching semantics we encode is a differential-testing oracle to run real tools against; a
  disagreement is a genuine defect in a security tool people trust. Slice 1 already has two
  (Checkov's regex accepts `org/*`, rejects the immutable `@id` format).
- **Secondary metric: adoption** — a tool consuming the vectors, or a citation of the corpus.
- **Vectors added is an INPUT, not the score.** Curation for its own sake is the failure mode
  (the "librarian" trap). A tranche that surfaces no bug and no adoption is a signal, not progress.

If, after v0.1, finding and landing real bugs in real tools is not energizing, that is the pivot
trigger (see rethink triggers) — not a cue to keep cataloguing. The corpus then becomes the
substrate for follow-on work, or is donated to a neutral home.

## v0.1 — GitHub-to-AWS tranche + the two feeder PRs (first month)

*Goal: land the first merged bug-fix PR (Checkov) and stand up the oracle that generated it.*

- [~] **Slice 1 — Checkov `oidc_utils.py` fix (upstream, deadline-bound: before 2026-07-15).**
      One PR: `gh_repo_regex` currently accepts `org/*` wildcard repos (false negative) and
      rejects the immutable `owner@123/name@456` format that becomes mandatory for new repos on
      2026-07-15 (false positive). Parametrized tests across CKV_AWS_358 / CKV_AZURE_249 /
      CKV_GCP_125; GitHub changelog citation in the PR body. 1-2 evenings.
      **Opened** as Checkov PR #7610 (immutable `@id` support across the four GH-OIDC checks); the
      org-wide `repo:org/*` case raised as the open question per plan. Awaiting maintainer review.
      Not yet merged, so still `[~]`.
- [x] **Slice 2 — suite skeleton.** JSON Schema for vectors; GitHub issuer grammar (classic AND
      immutable formats); ~20 AWS StringLike/StringEquals match/no-match vectors including
      wildcard-vs-immutable-ID footguns; ~100-line Python reference matcher passing pytest.
      Vector layout shaped so Checkov-style parametrized tests can be regenerated from it (the
      adoption hook). Done: skeleton shipped, github-aws now 27 vectors (0.2.0 tranche
      2026-07-16, adversarially source-verified); Azure/GCP/GitLab tranches landed alongside.
- [~] **Slice 3 — Cartography scoping issue (upstream).** Issue against `intel/aws/iam.py`
      ("# TODO support conditions") with a failing fixture: a GitHub-OIDC StringLike trust policy
      producing an unconditioned federated edge. Minimal additive proposal (sub/aud as edge
      properties, no new node types). Issue-first is correct here: it is a genuine schema-design
      question. 1 evening.
      **Advanced well past plan:** filed as issue #3078; maintainer green-lit option 3, tier-1
      first; now open as PR #3088 (`feat/iam-trust-conditions`, rebased 2026-08-15).
      Maintainer-requested reassess 2026-09-30.
- [~] **Slice 4 — Azure FIC tranche (the depth wedge).**
      - [x] Classic FIC `azure-fic-exact` consumer in the matcher + 10 cited vectors
            (`vectors/github-azure.json`): case-sensitivity, the silent no-error mismatch, the
            wildcard-as-literal trap (opposite of AWS StringLike — `repo:org/*` matches nothing on
            Azure), tag/environment scoping, the `pull_request` over-permission CKV_AZURE_249
            passes, and the classic-vs-immutable silent break.
      - [x] Flexible-FIC tranche (`claimsMatchingExpression`: `matches`/`eq`/`and`, `*`/`?`
            wildcards) — Preview, Graph/portal-only, version-stamped. SHIPPED:
            `src/subvectors/ffl.py` + the `azure-fic-flexible` consumer + all three issuers
            Microsoft supports — `github-azure-flexible` (8), `gitlab-azure-flexible` (5),
            `terraform-azure-flexible` (6).
      - [~] CKV_AZURE_249 deepening PR generated from the pull_request/tag/environment vectors.
            Opened as Checkov PR #7627 ("CKV_AZURE_249 should flag `pull_request` OIDC subjects").
      [!] (Corrected 2026-08-16 — the previous "correction" here was itself inverted.) The silence
      is at CREATION, not exchange: Azure performs no validation when a federated identity
      credential is written, so a wrong subject is accepted without complaint. At TOKEN EXCHANGE a
      mismatch DOES return an error — `AADSTS700213` ("No matching federated identity record found
      for presented assertion subject ... matching is done using a case-sensitive comparison");
      `AADSTS700211` is the issuer-mismatch variant and `AADSTS70021` the generic no-match.
      The defect to claim is "unvalidated at write time", not "fails silently". This wording still
      needs fixing in `matcher.py` and the Azure vector suites — see ARCHITECTURE.md known issues.

## v0.2 — breadth and consumers

- [x] GCP Workload Identity Federation CEL tranche. SHIPPED: `src/subvectors/cel.py` (incl. map
      indexing) + 4 suites — `github-gcp` (12), `gitlab-gcp` (6), `terraform-gcp` (6),
      `circleci-gcp` (6).
- [x] Non-GitHub issuers: GitLab, Bitbucket, CircleCI, Terraform Cloud subject dialects. ALL
      SHIPPED — 5 issuers total (github, gitlab, bitbucket, circleci, terraform-cloud).
- [ ] Consumer-adoption pass: offer vector-derived test PRs to zizmor / Prowler / GitHound where
      their matching logic diverges from the suite.
- [x] Judgment catalog write-up: the graded over-permission patterns as a citable reference page.
      **SHIPPED: [`docs/JUDGMENT-CATALOG.md`](docs/JUDGMENT-CATALOG.md)** — all 65
      `judgment.patterns` tags grouped into 10 canonical families, each with a definition,
      mechanism, typical grade, and example vector; `tests/test_judgment_catalog.py` guards both
      directions so the vocabulary cannot sprawl silently. [i] Note what this is and is not
      (2026-08-29): a stable, citable **reference page**, not an article. It is exactly the
      artifact-shaped proof this project trades in — someone can cite a pattern ID years from now.
      No companion post is owed or planned.

## Upstream integration targets

Places where a shipping tool's matching logic diverges from the corpus. Each divergence is a
concrete, vector-backed contribution:

- **Checkov's OIDC check family** (CKV_AWS_358/393, CKV_AZURE_249, CKV_GCP_125) grades a
  multi-value `sub` condition by a single value, so an OR-list can carry a value the check itself
  rejects standing alone. Read against source at checkov 3.3.16 / `d8aec9db`, 2026-08-31, and
  measured through checkov's own `Runner`:
  - CKV_AWS_393 (`aws_iam_role.assume_role_policy`) returns on the first value that yields any
    verdict, over JSON author order — `["repo:org/repo:ref:refs/heads/main", "*"]` PASSES.
  - CKV_AWS_358 (`data.aws_iam_policy_document`) reads element `[0]` only, but the Terraform
    parser sorts string values lexicographically before the check sees them
    (`clean_parser_types_lst`), which incidentally catches `*`-leading poisons. The residual miss
    is any unsafe value sorting after every safe one — of the abusable claims, `workflow:`.
  - CKV_GCP_125 extracts the CEL `assertion.sub ==` comparison with a first-match-only
    `re.search`, so disjuncts past the first are never inspected.
  - CKV_AZURE_249 is not affected (its `subject` is scalar and a list fails closed).
  No multi-value fixture exists anywhere in checkov's test suite. Separately, the subject regexes
  predate the immutable `@id` format.
- **Cartography** does not parse IAM trust-policy conditions at all, so a federated edge carries
  no `sub`/`aud` scoping.
- **Prowler** has no Entra federated-identity-credential checks (verified), so Azure FIC subject
  grading is entirely unrepresented there.

## Rethink triggers

- [!] No tool has merged a vector-derived PR or cited the corpus by end of 2026 → pivot the lead
      to the Prowler Entra-FIC gap; keep the corpus as its fixture backing.
- [!] A neutral home (e.g. an OpenSSF WG, sigstore) starts a machine-readable claims registry →
      contribute the corpus there; "own repo" becomes "join theirs".
- [!] Both current gaps close first (Checkov fix landed by someone else AND the Cartography TODO
      reached) → corpus survives; Prowler's Entra-FIC gap becomes the lead target.

## Explicitly dropped

- The scanner / diff-aware PR-gate race (the original oidc-reach v1) — killed 2026-07-05 by the
  red-team review: value decayed on a ~6-month incumbent fuse. Its research transfers wholesale:
  the subject grammars, Azure FIC judgment depth, and the over-permissive/tight fixture plan are
  the corpus seed.
- `cicd-threat-posture` (redundant sibling), Neo4j/graph-database anything (unchanged from June).
