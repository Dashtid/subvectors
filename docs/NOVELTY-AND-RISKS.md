# Novelty & risks — the research basis (Jun 2026)

This project survived an 8-round idea search + a focused validation pass. Keep this file honest and
current — if a risk materializes (e.g. an incumbent ships the join), re-read it before spending more
weekends.

## DECISION — 2026-07-05: pivot from scanner to conformance suite

David chose to drop the scanner/PR-gate plan and reshape the project into the **OIDC subject
conformance vector suite + upstream feeder campaigns** (Checkov OIDC family, Cartography trust
conditions). Basis: the 2026-07-04 re-verification below (both June headline claims dead; ~6-month
incumbent fuse on the surviving gate wedge) plus a red-teamed 6-candidate search in which the
scanner baseline was killed on structure — its value decays when incumbents converge, while a
cited test-vector corpus gains a consumer with every tool that enters the space (Wycheproof /
JSON-Schema-Test-Suite model; consumers reject runtime data dependencies but adopt neutral vectors
at test time). The month of research transfers wholesale: subject grammars, Azure FIC judgment
depth, and the fixture plan become the corpus seed. New scope and rethink triggers: ROADMAP.md.
Key red-team caveat to manage: adoption risk — if no tool consumes the corpus by end of 2026, the
fallback ladder is Prowler Entra-FIC campaign first, corpus as its fixture backing.

## Re-verification — 2026-07-04 (pre-commit check #1: CLOSED)

Six-angle prior-art sweep with adversarial verification of every threatening claim; the two
verdict-changing findings were then re-verified by hand against primary sources (Checkov check
code read verbatim; GitHound repo/docs). Both June headline claims fell — a narrower, sharper
wedge survives.

### Verdicts on the June novelty claims

1. **"Azure FIC subject analysis is entirely un-tooled" — DEAD as worded.** Checkov
   `CKV_AZURE_249` (PR #6960, merged 2025-01-22; productized in Prisma Cloud as `azr-iam-249`)
   has linted the `subject` of `azuread_application_federated_identity_credential` since Jan
   2025 — the June pass missed it. But the check is shallow, confirmed against its own code: it
   splits on `:` and inspects only segments 0-1 — rejects a missing/`*` subject, `*` as the
   *entire* first/second segment, abusable *leading* claim types (`workflow:`, `environment:`,
   `ref:`, ...), and a malformed `org/name`. It PASSES `repo:org/repo:pull_request`, PASSES
   `repo:org/repo:ref:refs/heads/*`, PASSES `repo:octo-org/*` (its repo regex `[^/]+` accepts
   `*`). Coverage is Terraform `azuread` provider only — no
   `azurerm_federated_identity_credential` (managed-identity FIC), no ARM/Bicep, no live tenant.
   https://github.com/bridgecrewio/checkov/blob/main/checkov/terraform/checks/resource/azure/GithubActionsOIDCTrustPolicy.py
2. **"No tool joins the two sides" — DEAD.** SpecterOps **GitHound** (BloodHound OpenGraph
   collector for GitHub; active commits Apr–May 2026) parses workflow YAML
   (`GH_Workflow`/`GH_WorkflowJob` nodes incl. `id-token: write`) AND cloud trust (Azure FIC
   subjects incl. ref/environment/pull_request/wildcards; AWS role targets) and joins them via
   `GH_CanAssumeIdentity` edges in one attack-path graph. It MAPS reach but does not JUDGE it:
   no over-permission verdicts, live API collection only (no offline/fixture mode), no diff or
   PR-gating feature. https://github.com/SpecterOps/GitHound

### The surviving wedge (narrowed, sharpened)

- **Diff-aware reach-widening PR gate — still unclaimed by anyone.** Datadog gates workflow-side
  IaC; nobody gates the *joined* reach diff. This is now the headline, full stop.
- **Judgment, not mapping.** GitHound draws the edge; it never says "this subject is
  over-permissive because the branch is unprotected / it admits fork PRs." Verdicts + precision
  (suppress findings with no reachable workflow) remain ours.
- **Offline, fixture-driven static analysis.** GitHound requires live PAT/App collection;
  Checkov requires Terraform source. Nothing analyzes both sides from static artifacts in CI.
- **Azure FIC depth beyond Checkov's regex.** `pull_request` subjects, unprotected
  branches/tags/environments, wildcarded repos, `azurerm`/ARM/Bicep resources, live-tenant FICs,
  and the flexible/immutable formats below — all unchecked by anything today.

### Kill-window check: validating fast — treat the window as ~6 months

- **Prowler 5.32.0 (2026-07-02):** GitHub provider shipped workflow-side scanning (zizmor
  wrapper, PR #10607); release notes announce cross-provider attack-path linking as direction
  (Neptune sink + embedded Cartography, which already has GitHubWorkflow nodes).
- **Wiz Code (2026-04-20):** workflows/jobs/runners now live on the same Security Graph as cloud
  IAM "can assume" edges — the cross-edge is one release away.
- **Datadog (2026-04-16):** shipped a workflow-side IaC PR gate with inline comments, and holds
  the cloud-side rule (`def-000-5g7`) in a separate product — both halves, unjoined.

### Parser-target news (design inputs)

- **Flexible FIC (`claimsMatchingExpression`) still Preview** as of 2026-06-15: `matches`/`eq`/
  `and`, wildcards `*`/`?`; issuers GitHub/GitLab/Terraform Cloud; claims `sub` +
  `job_workflow_ref` (GitHub only); application objects only; Graph beta / portal only — no
  Terraform/CLI surface, so no IaC linter can reach it yet, and the grammar is a moving target.
  https://learn.microsoft.com/en-us/entra/workload-id/workload-identities-flexible-federated-identity-credentials
- **GitHub immutable sub claims:** repos created after **2026-07-15** get subjects with embedded
  IDs (`repo:octocat@123456/my-repo@456789:ref:...`). The subject grammar and fixture corpus —
  including the AWS v0.1 slice — must cover both formats.
  https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/

### Prior art to cite (README / any writeup)

- **O3-Cyber/oidc-code-to-cloud** (Sep 2024, dormant): graphs FIC-subject→GitHub reachability
  *inferred from the subject*; never reads workflow YAML; no lint, no gate.
- **TrustFix / oidc-audit** (Mar 2026 vendor): one-sided halves (workflow action + live-AWS
  sub-pattern linter); Azure/GCP on Q3–Q4 2026 roadmap; zero traction so far.
- **GhostGates** (Mar 2026): GitHub-side OIDC subject-template rules + scan diffing; no cloud
  collector.
- **BloodHound/AzureHound v8.9.0** (2026-03-23): FICs are first-class nodes
  (`AZFederatedIdentityCredential`, `AZAuthenticatesTo`) — existence only, no subject analysis.
- **Checkov OIDC family:** `CKV_AWS_358`/`CKV_AWS_393` (AWS trust-policy `sub` conditions;
  inline-policy variant added 2026-06-01), `CKV_GCP_125`/`CKV_GCP_118` (GCP WIF) — the family is
  actively expanding.

### Refuted scares (checked 2026-07-04, no capability found)

- Prowler: zero `federatedIdentityCredential` / `token.actions.githubusercontent` hits across
  Azure entra + AWS IAM checks; Attack Paths still AWS-only.
- KICS: zero OIDC/FIC/WIF queries. Terrascan: archived Nov 2025 — drop from future scans.
- zizmor, poutine, octoscan, Gato-X, Legitify, actionlint, Scorecard, harden-runner: all strictly
  GitHub-side.
- Defender for Cloud / Entra: FIC inventory + token-exchange-time rejection only; wildcard-risk
  warning is docs prose, not a check.
- AzADServicePrincipalInsights: FIC inventory, no subject analysis.
- Cartography `aws/iam.py`: `# TODO support conditions` still unshipped — trust-policy Condition
  blocks remain unparsed (the latent Prowler/Cartography join edge to watch).

## Verified novelty (Jun 2026 baseline — claims 2 and 3 superseded above)

- **Cartography stores OIDC trust as an opaque edge.** Verified from primary source:
  `cartography-cncf/cartography` `intel/aws/iam.py` `transform_role_trust_policies()` contains a
  literal `# TODO support conditions` and stores only `{arn, type, role_arn}` for federated
  principals — no `sub`/`StringLike` values, no repo/branch/workflow nodes. The Azure schema has no
  FIC / workload-identity node at all.
- **No tool does the bidirectional join.** Across the arXiv 2601.14455 survey of 9 Actions scanners
  (actionlint, frizbee, ggshield, pinny, poutine, scharf, scorecard, semgrep, zizmor — all
  workflow-side only), gato-x (GitHub-side reachability, zero cloud trust parsing), cloud-side
  checkers (Rezonate, Tinder, Datadog/Wiz CSPM, AWS Access Analyzer — trust-side only), and graph
  tools (Prowler Attack Paths — AWS-only, GitHub provider siloed from the cloud graph): **none**
  statically parse BOTH sides and join them into a can-assume reachability graph.
- **Azure FIC reachability analysis is entirely un-tooled.** Closest is
  AzADServicePrincipalInsights, which *inventories* FICs + roles but does NOT parse the subject
  condition for over-permission nor perform the reachability join. Confirmed across Microsoft
  tooling, OSS, CIEM, and security blogs.

## The honest risks (all survived validation — manage them)

1. **Perishability / kill-risk: HIGH on the AWS slice.** Prowler (Cartography+Neo4j+GitHub provider)
   and Wiz hold the graph substrate; a workflow→AWS cross-edge is one feature-release away. Window
   ~6–12 months. → Ship fast; lead with the Azure/seam wedge where the gap is confirmed clean.
2. **Demand is inferred, not voiced.** Zero issues/talks/retros ask for the specific cross-side
   join. The *category* (GitHub-Actions security; zizmor 5.6k stars) is proven; the specific join is
   verified white space, not voiced pull. → Run the practitioner sanity-check (see CLAUDE.md) before
   the full weekend commitment.
3. **The catastrophic case is already covered.** Missing-`sub` is caught by Datadog/Wiz CSPM, and
   AWS STS per-claim validation (GA Feb 2026) erodes the "the `sub` string is hard to reason about"
   pain. → The honest USP is precision + diff-aware PR-gate, NOT a new detector.
4. **Azure FIC = strongest novelty but weakest-evidenced demand.** Every concrete demand signal is
   AWS-centric; flexible/expression FIC is in active preview (moving target). → Pre-commit check #1:
   confirm Prowler/ScoutSuite/Checkov don't already lint FIC subjects. **[CLOSED 2026-07-04:
   Checkov does, shallowly — see the re-verification section above. Wedge narrowed, not gone.]**

## Why this beat the alternatives

- vs **cra-conformance** (Threat-Model-as-Code for EU CRA): rejected as a *first* flagship — it's
  STRIDE-under-IEC-81001-5-1, i.e. David's literal Hermes day-job methodology (IP-tainted, repeats
  the dicom-fuzzer mistake), and the space already ships products (craevidence.com, itemis, ThreatZ).
  A post-Hermes consultancy product, not a now-play.
- vs **pipelineghost** (offensive agentic-CI/CD harness): scored highest but rejected for now —
  David is at offensive Phase 0; an advanced offensive tool he can't yet explain at protocol level
  reads as theater. Revisit once he's deep into OSCP-track training.
