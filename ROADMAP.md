# Roadmap

Re-pointed 2026-07-05: the scanner/PR-gate plan ("oidc-reach v1") is dropped in favor of the
conformance vector suite + the upstream fixes it feeds. The compounding test: an incumbent
shipping an overlapping feature must ADD a consumer of this corpus, never obsolete it.

**Cadence discipline:** every slice is weeknight-sized and independently shippable. Ship the
slice, update this file, stop.

## Where this actually stands (2026-08-18)

**The corpus is feature-complete. Do not add vectors.** All 5 planned issuers and all 6 consumer
semantics have shipped: 14 suites / 133 vectors, 227 tests green, CI green on 3.11-3.13. Corpus and
code work paused 2026-07-31; docs hygiene continued through 08-18. It is **not stalled** — it is
built, and the remaining value is entirely OUTSIDE this repo.

**Fixed 2026-08-18 — the one correctness bug.** `RepoSegment.immutable` in
`src/subvectors/github.py` used `or` where it needed `and`, so a one-sided `@id` subject (an
id on the owner or the repo but not both) was reported as immutable when it is *malformed* — a
shape GitHub never mints. The branch was **reachable, not latent**: the two id groups in
`_REPO_RE` are independently optional, so `parse_repo_segment` parses one-sided input happily.
Zero of 133 vectors exercised it, which is why 225 green tests sailed over it; two unit tests now
cover both one-sided forms. **subcheck shipped the identical bug and fixed it three weeks earlier**
(`34a42ce` 2026-07-21 introduced `"immutable" if (owner_id or repo_id)`, `423964f` 2026-07-30
replaced it with a three-state `immutable`/`malformed`/`legacy` classification). The two agree
again on every input shape. Worth noting what this was: not the corpus disagreeing with an outside
tool, but this repo lagging a correction its own consumer had already made — the kind of drift
nothing here currently tests for.

What is actually open, in priority order:

1. ~~**Doc-truth debt**~~ — **DONE 2026-08-25.** The Azure "fails silently with no error" claim is
   corrected everywhere it appeared (matcher docstrings + 12 places across the `github-azure` and
   `gitlab-azure` suites): creation is unvalidated, the *exchange* returns `AADSTS700213`, and the
   six vectors naming that code now cite the Entra error-codes reference. The provenance split is
   no longer prose at all — `scripts/coverage.py` generates "133 `documented`" plus an explicit
   "no vector is `observed` yet" note into the README, and CI fails on a stale block.
2. **Three upstream PRs open, zero merged** — checkov #7610 (CI never ran; fork-PR workflow runs
   await approval), checkov #7627, cartography #3088. The scoreboard below says merged PRs are
   the metric; it currently reads 0.
3. **The `documented` → `observed` promotion — STARTED 2026-08-29: first 5 vectors observed** via
   the IAM policy simulator (experiments 1-3 of the runbook, controls included; github-aws 0.3.1;
   provenance now 128 documented / 5 observed). Settled empirically: StringEquals AND StringLike
   are case-sensitive (the doc-vs-third-party contradiction closed in the docs' favor), `*`
   crosses `:` and `/`, and zero-width `*` matching is confirmed rather than interpreted.
   Remaining: experiment 4 (role-creation guardrail probe — needs a temporary
   iam:CreateRole/DeleteRole attach on the probe user) and experiment 5 (GCP unquoted-int —
   needs a GCP account). See docs/OBSERVED-PROMOTION.md.
4. **PyPI release gate (added 2026-08-24) - CLOSED same day, v0.2.0 shipped.** The wheel now
   force-includes the whole `vectors/` tree (suites + schema + the corpus's CC0 LICENSE) and
   `subvectors.corpus` resolves it via `importlib.resources` (packaged install and source
   checkout both work; verified by installing the wheel in isolation - 14 suites load from the
   packaged path). Pending publisher configured, GitHub Release published, trusted-publishing
   run green. Follow-on for subcheck: pin the released artifact instead of hand-vendoring
   `github_subjects.json`.

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

- **Checkov's OIDC check family** (CKV_AWS_358/393, CKV_AZURE_249, CKV_GCP_125/118) reasons only
  about `sub`, and its subject regexes predate the immutable `@id` format.
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
