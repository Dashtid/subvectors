"""GitLab CI/CD OIDC subject grammar (the leading project_path / project_id segment).

Recognizes a GitLab ID-token subject in BOTH documented forms:

    default (name-based)   project_path:mygroup/myproject:ref_type:branch:ref:main
    immutable (id-based)    project_id:20:ref_type:branch:ref:main

The default sub is built from the components [project_path, ref_type, ref]. Unlike
GitHub -- whose immutable subjects embed numeric owner/repo IDs INSIDE the sub
(repo:owner@123/repo@456:...) -- GitLab's default sub is purely name-based. The
immutable identifiers project_id / namespace_id are SEPARATE token claims, not part
of the sub. The only way an immutable id appears in the sub is when a project sets
ci_id_token_sub_claim_components to lead with project_id, which swaps the leading
key from ``project_path:`` to ``project_id:``; that is the ``immutable`` form here.

Two more divergences from the GitHub grammar:
- The leading key is ``project_path:`` (or ``project_id:``), not ``repo:``.
- ref_type (branch|tag) and the SHORT ref name are separate colon segments, where
  GitHub fuses them into one ``ref:refs/heads/main`` segment.

Operates on concrete *subjects*, not trust-policy *patterns*: a value containing
``*`` or ``?`` is a wildcard condition, not a minted subject, so it returns None.

Sources:
- Sub format, ref_type/ref, project_id/namespace_id as separate claims:
  https://docs.gitlab.com/ci/secrets/id_token_authentication/
- Configurable sub components (ci_id_token_sub_claim_components):
  https://docs.gitlab.com/api/projects/
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["SubjectSegment", "parse_subject"]

# {project_path:PATH | project_id:DIGITS}:ref_type:(branch|tag):ref:REF
# Path segments and ref names never contain ':', so the literal ':ref_type:'
# delimiter bounds the (unbounded-depth) leading segment. '*'/'?' are excluded so
# a wildcard pattern is not mistaken for a concrete subject.
_SUBJECT_RE = re.compile(
    r"^(?:"
    r"project_path:(?P<project_path>[^:*?]+)"
    r"|project_id:(?P<project_id>\d+)"
    r")"
    r":ref_type:(?P<ref_type>branch|tag)"
    r":ref:(?P<ref>[^:*?]+)$"
)


@dataclass(frozen=True)
class SubjectSegment:
    """The parsed leading segment of a GitLab OIDC subject."""

    ref_type: str                 # "branch" or "tag"
    ref: str                      # short ref name, e.g. "main", "v1.0.0"
    project_path: str | None      # full slash path when name-based, else None
    project_id: str | None        # numeric id when the immutable sub form is used

    @property
    def immutable(self) -> bool:
        """True when the subject is built on the rename-proof project_id component."""
        return self.project_id is not None

    @property
    def namespace_path(self) -> str | None:
        """The group/subgroup portion of project_path (all but the project slug)."""
        if self.project_path is None or "/" not in self.project_path:
            return None
        return self.project_path.rsplit("/", 1)[0]

    @property
    def project(self) -> str | None:
        """The project slug (last segment of project_path)."""
        if self.project_path is None:
            return None
        return self.project_path.rsplit("/", 1)[-1]


def parse_subject(subject: str) -> SubjectSegment | None:
    """Parse a GitLab OIDC subject in its default or immutable (project_id) form.

    Returns a :class:`SubjectSegment`, or None if ``subject`` is not a GitLab
    ``project_path:``/``project_id:`` subject in the documented
    ``...:ref_type:(branch|tag):ref:...`` shape (e.g. a wildcard pattern, a
    GitHub ``repo:`` subject, or a non-default component ordering).
    """
    m = _SUBJECT_RE.match(subject)
    if m is None:
        return None
    return SubjectSegment(
        ref_type=m.group("ref_type"),
        ref=m.group("ref"),
        project_path=m.group("project_path"),
        project_id=m.group("project_id"),
    )
