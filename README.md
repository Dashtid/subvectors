# subvectors

**Conformance vectors for OIDC trust subjects — the answer key for CI/CD OIDC trust decisions: a
cited, versioned test-vector suite answering "does subject S satisfy trust condition C, and is C
safe?"**

When a CI pipeline authenticates to a cloud via OIDC (GitHub Actions to AWS/Azure/GCP today), the
entire security boundary is a string comparison: the token's `sub` claim versus an admin-written
matching rule — an AWS IAM trust-policy condition, an Azure federated-identity-credential (FIC)
subject, a GCP Workload Identity Federation attribute condition. Every security tool in this space
must re-implement that comparison and judge those rules. They re-figure it out alone, and they get
it wrong.

> Status: pre-v0.1. Built on personal time + personal equipment. IP-clean: cloud-CI OIDC trust
> boundaries, deliberately outside any medical-imaging / SBOM-SCA domain.

## The proof this is needed (verified 2026-07-04)

Checkov — one of the most widely used IaC security scanners — ships the only Azure FIC subject
check anywhere (`CKV_AZURE_249`). Read against its own source:

- It PASSES `repo:org/*` (any repo in the org may assume the role) and
  `repo:org/repo:pull_request` (unreviewed PR code may) — dangerous patterns waved through.
- Its repo regex has no `@` in the charset, so it will FAIL every valid immutable-format subject
  (`repo:owner@123456/name@456789:...`) — the format GitHub makes mandatory for repos created
  after **2026-07-15**.

The formats churn (GitHub immutable claims, Azure flexible-FIC expressions in preview, per-issuer
dialects from GitLab/Bitbucket/CircleCI), and every scanner re-derives the semantics from prose
docs. A single maintained, cited corpus of test vectors fixes that for everyone.

## What a vector looks like

```json
{
  "id": "gh-aws-0007",
  "issuer": "github",
  "subject": "repo:acme/webapp:pull_request",
  "condition": { "consumer": "aws-stringlike", "pattern": "repo:acme/webapp:*" },
  "expect": "match",
  "judgment": {
    "grade": "dangerous",
    "reason": "pattern admits pull_request runs; fork PR code can mint this subject"
  },
  "sources": ["https://docs.github.com/en/actions/deployment/security-hardening-your-deployments"],
  "status": "documented"
}
```

Three layers per vector:

1. **Grammar** — is the subject well-formed for its issuer (classic AND immutable GitHub formats)?
2. **Match semantics** — does it satisfy the consumer's condition (AWS `StringLike`/`StringEquals`
   globbing, Azure FIC exact match + flexible expressions, GCP CEL)?
3. **Judgment** — is the condition safe? Graded findings for the patterns that matter:
   `pull_request` subjects, unprotected refs, wildcarded repos/orgs, missing `aud` pinning.

Every vector carries a source citation and a `documented` vs `observed` status. A ~100-line
reference matcher (Python, pytest) passes the suite — it is a correctness oracle, not a product.

## Why an answer key instead of another scanner

Scanners in this space compete and get obsoleted: SpecterOps GitHound already maps
workflow-to-cloud OIDC reach, Prowler shipped a GitHub provider (2026-07-02), Wiz and Datadog are
converging (see [`docs/NOVELTY-AND-RISKS.md`](docs/NOVELTY-AND-RISKS.md)). A test-vector suite does
not compete with scanners — it grades them. Each new tool entering the space is a new consumer of
the corpus, the way Wycheproof tests everyone's cryptography and the JSON-Schema-Test-Suite tests
everyone's validators. Consumers keep their own matching code (no runtime dependency to trust) and
import the vectors at test time.

Bugs the vectors expose in real tools get fixed by upstream PRs (Checkov's OIDC check family,
Cartography's unparsed trust-policy conditions) — the distribution channel and the proof, in one.

## Scope order

GitHub issuer + AWS consumer first, Azure FIC as the depth tranche (its exact-match and
flexible-expression semantics are the least-tooled corner), then GCP CEL and non-GitHub issuers.
Fully offline: JSON vectors + pytest, no cloud account required.

## Why this project exists (for me)

Closes a specific, recurring gap: multi-cloud IAM / OIDC trust-boundary depth (AWS + **Azure**).
Writing a falsifiable, cited test case about a trust rule forces genuinely understanding the rule
— active-recall learning with a public artifact as the receipt.

## License

Dual-licensed to maximize adoptability:

- **Vector data (`vectors/`) — CC0-1.0** (public-domain dedication). Embed the vectors in your
  tool's test suite with zero attribution or licensing friction — that frictionlessness is the
  point. See [`vectors/LICENSE`](vectors/LICENSE).
- **Everything else** (the reference matcher, schema, docs) **— Apache-2.0**. See
  [`LICENSE`](LICENSE).
