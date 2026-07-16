# Roadmap

Re-pointed 2026-07-05: the scanner/PR-gate plan ("oidc-reach v1") is dropped in favor of the
conformance vector suite + upstream feeder campaigns. Rationale and the full decision record live
in [`docs/NOVELTY-AND-RISKS.md`](docs/NOVELTY-AND-RISKS.md). The compounding test: an incumbent
shipping an overlapping feature must ADD a consumer of this corpus, never obsolete it.

**Cadence discipline:** every slice is weeknight-sized and independently shippable. Ship the
slice, update this file, stop.

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
substrate for the deferred offensive project, or is donated to a neutral home.

## v0.1 — GitHub-to-AWS tranche + the two feeder PRs (first month)
*Goal: land the first merged bug-fix PR (Checkov) and stand up the oracle that generated it.*

- [ ] **Slice 1 — Checkov `oidc_utils.py` fix (upstream, deadline-bound: before 2026-07-15).**
      One PR: `gh_repo_regex` currently accepts `org/*` wildcard repos (false negative) and
      rejects the immutable `owner@123/name@456` format that becomes mandatory for new repos on
      2026-07-15 (false positive). Parametrized tests across CKV_AWS_358 / CKV_AZURE_249 /
      CKV_GCP_125; GitHub changelog citation in the PR body. 1-2 evenings.
- [x] **Slice 2 — suite skeleton.** JSON Schema for vectors; GitHub issuer grammar (classic AND
      immutable formats); ~20 AWS StringLike/StringEquals match/no-match vectors including
      wildcard-vs-immutable-ID footguns; ~100-line Python reference matcher passing pytest.
      Vector layout shaped so Checkov-style parametrized tests can be regenerated from it (the
      adoption hook). Done: skeleton shipped, github-aws now 27 vectors (0.2.0 tranche
      2026-07-16, adversarially source-verified); Azure/GCP/GitLab tranches landed alongside.
- [ ] **Slice 3 — Cartography scoping issue (upstream).** Issue against `intel/aws/iam.py`
      ("# TODO support conditions") with a failing fixture: a GitHub-OIDC StringLike trust policy
      producing an unconditioned federated edge. Minimal additive proposal (sub/aud as edge
      properties, no new node types). Issue-first is correct here: it is a genuine schema-design
      question. 1 evening.
- [~] **Slice 4 — Azure FIC tranche (the depth wedge).**
      - [x] Classic FIC `azure-fic-exact` consumer in the matcher + 10 cited vectors
            (`vectors/github-azure.json`): case-sensitivity, the silent no-error mismatch, the
            wildcard-as-literal trap (opposite of AWS StringLike — `repo:org/*` matches nothing on
            Azure), tag/environment scoping, the `pull_request` over-permission CKV_AZURE_249
            passes, and the classic-vs-immutable silent break.
      - [ ] Flexible-FIC tranche (`claimsMatchingExpression`: `matches`/`eq`/`and`, `*`/`?`
            wildcards) — Preview, Graph/portal-only, version-stamped. Its own consumer + slice
            (moving target; not exposed via Terraform/CLI yet).
      - [ ] CKV_AZURE_249 deepening PR generated from the pull_request/tag/environment vectors.
      (Correction to earlier note: a subject mismatch is a SILENT no-error rejection; AADSTS70021
      is the separate propagation-delay error, not a mismatch diagnostic.)

## v0.2 — breadth and consumers

- [ ] GCP Workload Identity Federation CEL tranche.
- [ ] Non-GitHub issuers: GitLab, Bitbucket, CircleCI, Terraform Cloud subject dialects.
- [ ] Consumer-adoption pass: offer vector-derived test PRs to zizmor / Prowler / GitHound where
      their matching logic diverges from the suite.
- [ ] Judgment catalog write-up: the graded over-permission patterns as a citable reference page.

## Standing upstream campaigns (tracked in the private oss-contributions tracker)

- Checkov OIDC check family (CKV_AWS_358/393, CKV_AZURE_249, CKV_GCP_125/118).
- Cartography trust-policy conditions.
- Fallback feeder if either seam closes: Prowler Entra FIC checks (verified zero FIC code there,
  proven community merge channel).

## Rethink triggers (re-read docs/NOVELTY-AND-RISKS.md before overriding)

- [!] No tool has merged a vector-derived PR or cited the corpus by end of 2026 → pivot the lead
      to the Prowler Entra-FIC campaign; keep the corpus as its fixture backing.
- [!] A neutral home (e.g. an OpenSSF WG, sigstore) starts a machine-readable claims registry →
      contribute the corpus there; "own repo" becomes "join theirs".
- [!] Both feeder seams close first (Checkov fix landed by someone else AND the Cartography TODO
      reached) → corpus survives; Prowler becomes feeder #1.

## Explicitly dropped

- The scanner / diff-aware PR-gate race (the original oidc-reach v1) — killed 2026-07-05 by the
  red-team review: value decayed on a ~6-month incumbent fuse. Its research transfers wholesale:
  the subject grammars, Azure FIC judgment depth, and the over-permissive/tight fixture plan are
  the corpus seed.
- `cicd-threat-posture` (redundant sibling), Neo4j/graph-database anything (unchanged from June).
