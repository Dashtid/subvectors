"""GitHub Actions OIDC subject grammar (the leading ``repo:`` segment).

Recognizes the owner/repo segment of a GitHub OIDC token subject in BOTH forms:

    classic     repo:octo-org/octo-repo:ref:refs/heads/main
    immutable   repo:octo-org@123456/octo-repo@456789:ref:refs/heads/main

Immutable subjects carry an appended numeric ID on the owner and repo so the
claim survives a rename. They become mandatory for repositories created after
2026-07-15. A parser that understands only the classic form silently rejects
every new repository's token -- the exact defect this project exists to catch
(e.g. Checkov's gh_repo_regex, which has no ``@`` in its character class).

This operates on concrete *subjects*, not trust-policy *patterns* -- but the
guarantee is narrower than it looks, and was overstated here until 2026-09-02.
A wildcard in the OWNER or REPO position returns None (``repo:octo-org/*``,
``repo:*/octo-repo``). A wildcard *after* the repo segment is not inspected:
``repo:octo-org/octo-repo:*`` returns the concrete octo-org/octo-repo segment,
deliberately, because a consumer grading that pattern wants to know which
repository it names. A caller that needs "is this whole value a pattern?" must
test the whole string; this function only promises that the segment it returns
is wildcard-free.

Sources:
- Immutable subject claims:
  https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/
- OIDC subject claim reference:
  https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["RepoSegment", "parse_repo_segment"]

# repo:OWNER[@ownerid]/REPO[@repoid]:  -- a concrete subject always has a
# suffix claim after the repo, so the trailing ':' is required. Owner/repo
# names exclude the '/', '@', ':' delimiters and the '*'/'?' wildcard chars.
_REPO_RE = re.compile(
    r"^repo:"
    r"(?P<owner>[^/@:*?]+)(?:@(?P<owner_id>\d+))?"
    r"/"
    r"(?P<repo>[^/@:*?]+)(?:@(?P<repo_id>\d+))?"
    # The context segment is OPTIONAL. GitHub's sub customization documents
    # include_claim_keys: ["repo"] as the template for granting "cloud access to
    # all the workflows in a specific repository, across all branches/tags and
    # environments" -- which mints a bare `repo:ORG/REPO` with nothing after it.
    # Requiring the trailing colon rejected that subject outright (fixed
    # 2026-09-02), and it is precisely the repo-wide shape worth grading.
    r"(?::|$)"
)


@dataclass(frozen=True)
class RepoSegment:
    """The parsed owner/repo prefix of a GitHub OIDC subject."""

    owner: str
    repo: str
    owner_id: str | None
    repo_id: str | None

    @property
    def immutable(self) -> bool:
        """True when the subject carries embedded owner AND repo IDs.

        GitHub appends ``@id`` to both segments or to neither, so a one-sided
        subject (``owner@123/repo`` or ``owner/repo@456``) is *malformed* --
        a shape GitHub never mints -- and is not immutable. The parsed
        ``owner_id``/``repo_id`` still report whichever id was present.
        """
        return self.owner_id is not None and self.repo_id is not None


def parse_repo_segment(subject: str) -> RepoSegment | None:
    """Parse the leading ``repo:owner/repo:`` segment of a GitHub subject.

    Returns a :class:`RepoSegment`, or None if the leading segment is not a
    concrete ``repo:owner/repo``: a wildcard in the owner or repo position, or a
    subject scoped by a different leading claim such as ``repository_owner:``.

    The context segment after the repo is OPTIONAL (GitHub's documented
    ``include_claim_keys: ["repo"]`` customization mints a bare
    ``repo:ORG/REPO``) and is not examined, so a trailing wildcard such as
    ``repo:octo-org/octo-repo:*`` still yields its concrete segment.
    """
    m = _REPO_RE.match(subject)
    if m is None:
        return None
    return RepoSegment(
        owner=m.group("owner"),
        repo=m.group("repo"),
        owner_id=m.group("owner_id"),
        repo_id=m.group("repo_id"),
    )
