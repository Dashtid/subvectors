"""GitHub Actions OIDC subject grammar (the leading ``repo:`` segment).

Recognizes the owner/repo segment of a GitHub OIDC token subject in BOTH forms:

    classic     repo:octo-org/octo-repo:ref:refs/heads/main
    immutable   repo:octo-org@123456/octo-repo@456789:ref:refs/heads/main

Immutable subjects carry an appended numeric ID on the owner and repo so the
claim survives a rename. They become mandatory for repositories created after
2026-07-15. A parser that understands only the classic form silently rejects
every new repository's token -- the exact defect this project exists to catch
(e.g. Checkov's gh_repo_regex, which has no ``@`` in its character class).

This operates on concrete *subjects*, not trust-policy *patterns*: a value
containing ``*`` or ``?`` is a wildcard condition, not a minted subject, so it
is not a valid subject here and returns None.

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
    r":"
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
        """True when the subject carries embedded owner/repo IDs."""
        return self.owner_id is not None or self.repo_id is not None


def parse_repo_segment(subject: str) -> RepoSegment | None:
    """Parse the leading ``repo:owner/repo:`` segment of a GitHub subject.

    Returns a :class:`RepoSegment`, or None if ``subject`` is not a
    ``repo:``-scoped concrete subject (e.g. a wildcard pattern, or a subject
    scoped by a different leading claim such as ``repository_owner:``).
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
