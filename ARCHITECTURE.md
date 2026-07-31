# How subvectors works

A plain-language tour, for picking the project back up after time away.

## The one thing to hold onto

**subvectors is not a tool. It is a pile of test data.**

That is the single most confusing thing about it, so it's worth saying plainly. There is Python in
this repo, but the Python is *not the product* — it exists only to prove the data is correct. The
product is the JSON in `vectors/`.

The closest analogy: a **standard test fire** used to certify smoke detectors. It isn't a smoke
detector and doesn't compete with any. It's the thing you test detectors *against*.

## The problem it exists for

When a CI pipeline authenticates to a cloud, the entire security boundary is one string comparison:
the token's `sub` claim versus an admin-written matching rule.

```
   subject (what the pipeline presents)      condition (the admin's rule)
   repo:acme/payments-api:pull_request   vs   repo:acme/payments-api:*
```

The catch: **that comparison means different things to different clouds.** The same rule is a
wildcard glob to AWS `StringLike`, dead literal text to AWS `StringEquals`, dead literal text to
classic Azure FIC, and a typed expression to GCP.

Every security scanner (Checkov, Prowler, Wiz, …) has to re-implement this comparison, and they all
work it out alone from prose docs. They get it wrong. subvectors is a **shared answer key** so they
don't have to guess — and so their mistakes become visible.

Crucially it **grades scanners rather than competing with them**. A new scanner is a new *consumer*
of the corpus, not a rival. Same reason Wycheproof tests everyone's crypto.

## What a vector is

One vector is one falsifiable test case. From `vectors/github-aws.json`:

```json
{
  "id": "gh-aws-0007",
  "issuer": "github",
  "subject": "repo:acme/webapp:pull_request",
  "condition": { "consumer": "aws-stringlike", "pattern": "repo:acme/webapp:*" },
  "expect": "match",
  "judgment": {
    "grade": "dangerous",
    "reason": "pattern admits pull_request runs"
  },
  "sources": ["https://docs.github.com/..."],
  "status": "documented"
}
```

Read it as: *"an issuer minted this subject; an admin wrote this rule; here is whether they match;
here is whether the rule is safe; here is the doc that proves it."*

Three separable layers, deliberately kept apart:

1. **Grammar** — is the subject well-formed for its issuer?
2. **Match** — does it satisfy the condition? *Mechanically checkable.* The matcher decides this.
3. **Judgment** — is the condition *safe*? *A human opinion with a citation.* The matcher never
   reads it, so a consumer who disagrees with a grade can strip judgment and still use layers 1–2.

Two fields carry the honesty:
- **`sources`** — every vector cites a primary source. Required by the schema.
- **`status`** — `documented` (derived from docs) vs `observed` (confirmed against a real
  issuer/cloud). **All vectors are currently `documented`.** Closing that gap is the highest-value
  work available; see `BACKLOG.md`.

## The files

```
vectors/           <- THE PRODUCT. 13 suites, 127 vectors. CC0-licensed.
  github-aws.json        one file per (issuer x cloud) pair
  github-azure.json      github/gitlab/bitbucket/circleci/terraform x aws/azure/gcp
  ...
  schema/                JSON Schema every vector must validate against
  LICENSE                CC0-1.0 - copy these freely, no attribution needed

src/subvectors/    <- THE ORACLE. ~865 lines. Proves the vectors are self-consistent.
  matcher.py             satisfies(subject, condition) -> bool. The entry point.
  cel.py                 mini CEL evaluator (GCP conditions are CEL expressions)
  ffl.py                 mini expression evaluator (Azure flexible FIC, preview)
  github.py              GitHub subject grammar (legacy + immutable @id formats)
  gitlab.py              GitLab subject grammar (project_path + project_id forms)

tests/             <- THE PROOF.
  test_vectors.py        runs EVERY vector through the matcher, asserts `expect`
  test_matcher.py        unit tests for the matching semantics
  test_cel.py            CEL evaluator tests
  ...

docs/
  JUDGMENT-CATALOG.md    the graded over-permission patterns
  NOVELTY-AND-RISKS.md   the decision record (why this shape, what was killed)
```

## How the matcher works

`matcher.py` answers exactly one question: **does subject S satisfy condition C?**

Each `condition` names a **consumer** — which cloud's matching rules to apply:

| Consumer | Semantics |
|---|---|
| `aws-stringlike` | Glob. `*` = any characters, and it **spans `/` and `:`** — which is precisely why `repo:org/*` admits every repo in the org. |
| `aws-stringequals` | Exact equality. `*` is a literal character, so `repo:org/*` matches *nothing real*. |
| `azure-fic-exact` | Exact equality too — classic Azure FIC supports no wildcards at all. Opposite of AWS `StringLike`, from an identical-looking config. |
| `gcp-cel` | Not a string comparison. A CEL expression over the whole claim set, evaluated by `cel.py`. |
| `azure-fic-flexible` | Azure's preview expression language; wildcards are back. Evaluated by `ffl.py`. |
| `aws-all` | A composite: a full IAM Condition block, ANDing several AWS sub-conditions. |

Two behaviours worth remembering because they're where real bugs live:

- **Values are OR'd (AWS only).** A condition may carry a *list* of patterns, and IAM ORs them — so
  **one loose value poisons an otherwise tight list.**
- **Unsupported consumers raise, never return False.** A vector can never pass by being silently
  unmatched.

## How to run it

```bash
pytest -q        # runs every vector through the matcher
```

That's the whole loop. If a vector's `expect` disagrees with the matcher, the suite goes red — so
either the vector is wrong or the matcher is. Nothing else to start; there's no server, no CLI, no
cloud account.

## What it deliberately does NOT do

Guardrails, not gaps. See `CLAUDE.md`.

- **Not a scanner, not a PR gate, no reachability graphs.** That was the original `oidc-reach` plan
  and it was **killed on 2026-07-05** — the value decayed on a ~6-month incumbent fuse. If you find
  a doc still describing this project as a "PR gate," that doc is stale.
- **No runtime dependencies.** A consumer should be able to read or vendor the oracle, not have to
  trust a package.
- **It does not depend on subcheck** and never will. subcheck consumes *these* vectors as test
  fixtures; the arrow points one way. An answer key can't depend on one of its students.

## How success is measured

**Bugs found and upstream PRs merged.** Not vector count.

Vectors added is an *input*. A tranche that surfaces no bug and no adoption is a signal to stop, not
progress. Cataloguing for its own sake is the named failure mode ("the librarian trap") — see
`ROADMAP.md`.

## Known issues to fix before publishing

Recorded here so they aren't rediscovered later (from the 2026-07-30 verification pass):

- **Azure "fails silently, no error" is only half right.** *Creation* of a FIC is unvalidated and
  silent; *token exchange* returns `AADSTS700213`. Appears in `matcher.py`, several Azure vector
  files, and `ROADMAP.md` (where the parenthetical "correction" is itself inverted).
- **`RepoSegment.immutable` in `github.py` uses `or`.** It should be `and` — GitHub emits `@id` on
  both segments or neither, so a one-sided subject is *malformed*, not immutable. subcheck already
  fixed this on its side, so the two grammars currently disagree.
- **README counts are stale** — it says 10 suites / 107 vectors; actually 13 / 127.
- **README says vectors carry a `documented` vs `observed` status**, implying a mix. All are
  currently `documented`.
