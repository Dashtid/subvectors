"""Cut a release: preflight, bump, tag, publish, verify.

Four releases went out on 2026-08-31 and every one repeated the same checklist by
hand. The failure modes are all bookkeeping -- a stale coverage table, a version
that moved in pyproject.toml but not in __init__.py or the README, a tag pushed
before CI was green, a publish nobody confirmed reached PyPI. This does the
checklist and refuses to proceed when one of them is off.

Publishing is via GitHub Release -> .github/workflows/release.yml -> PyPI OIDC
trusted publishing. There is no token here and there should never be one.

Usage:
    python scripts/release.py 0.5.0 --dry-run
    python scripts/release.py 0.5.0 --notes-file notes.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
INIT = REPO_ROOT / "src" / "subvectors" / "__init__.py"
README = REPO_ROOT / "README.md"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(args, capture_output=True, text=True, cwd=REPO_ROOT)
    if check and result.returncode != 0:
        raise SystemExit(f"error: {' '.join(args)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def fail(message: str) -> None:
    raise SystemExit(f"[-] {message}")


def preflight(version: str) -> None:
    if not SEMVER.match(version):
        fail(f"{version!r} is not a semver x.y.z")

    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        fail(f"on branch {branch}, expected main")
    if run("git", "status", "--porcelain"):
        fail("working tree is dirty -- commit or stash first")
    run("git", "fetch", "--quiet", "origin", "main")
    if run("git", "rev-parse", "HEAD") != run("git", "rev-parse", "origin/main"):
        fail("local main and origin/main disagree -- push or pull first")
    if version in run("git", "tag", "--list").splitlines():
        fail(f"tag v{version} already exists")

    print("[i] running the test suite")
    tests = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if tests.returncode != 0:
        fail("tests fail:\n" + tests.stdout[-2000:])

    # The coverage table is generated; a stale one is silent doc drift.
    before = README.read_text(encoding="utf-8")
    run(sys.executable, "scripts/coverage.py", "--write")
    if README.read_text(encoding="utf-8") != before:
        README.write_text(before, encoding="utf-8", newline="\n")
        fail("README coverage table is stale -- run scripts/coverage.py --write and commit")

    sha = run("git", "rev-parse", "HEAD")
    checks = run("gh", "run", "list", "--workflow=ci.yml", "--limit", "10",
                 "--json", "headSha,status,conclusion", check=False)
    if checks:
        for entry in json.loads(checks):
            if entry["headSha"] == sha:
                if entry["status"] != "completed":
                    fail(f"CI for {sha[:8]} is still {entry['status']} -- wait for it")
                if entry["conclusion"] != "success":
                    fail(f"CI for {sha[:8]} concluded {entry['conclusion']}")
                print(f"[+] CI green on {sha[:8]}")
                break
        else:
            print(f"[!] no CI run found for {sha[:8]} -- proceeding without that check")
    print("[+] preflight passed")


def bump(version: str, dry_run: bool) -> list[str]:
    edits = [
        (PYPROJECT, re.compile(r'^version = "[^"]+"$', re.M), f'version = "{version}"'),
        (INIT, re.compile(r'^__version__ = "[^"]+"$', re.M), f'__version__ = "{version}"'),
        (README, re.compile(r"^> Status: v[^ ]+ on PyPI", re.M), f"> Status: v{version} on PyPI"),
    ]
    touched = []
    for path, pattern, replacement in edits:
        text = path.read_text(encoding="utf-8")
        new, n = pattern.subn(replacement, text, count=1)
        if n != 1:
            fail(f"could not find the version line in {path.name}")
        if new != text:
            touched.append(path.name)
            if not dry_run:
                path.write_text(new, encoding="utf-8", newline="\n")
    return touched


def verify_pypi(version: str, attempts: int = 12, delay: int = 10) -> bool:
    url = f"https://pypi.org/pypi/subvectors/{version}/json"
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(delay)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the version to release, e.g. 0.5.0")
    parser.add_argument("--notes-file", type=Path, help="release notes markdown")
    parser.add_argument("--title", help="release title (default: v<version>)")
    parser.add_argument("--dry-run", action="store_true", help="preflight and bump only, no push")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args(argv)
    version, tag = args.version, f"v{args.version}"

    preflight(version)
    touched = bump(version, args.dry_run)
    print(f"[+] version -> {version} ({', '.join(touched) if touched else 'already current'})")

    if args.dry_run:
        run("git", "checkout", "--", "pyproject.toml", "src/subvectors/__init__.py", "README.md")
        print("[i] dry run -- version bump reverted, nothing pushed")
        return 0

    print(f"[!] about to publish {tag} to GitHub and PyPI. This cannot be unpublished.")
    if not args.yes and input("    proceed? [y/N] ").strip().lower() not in ("y", "yes"):
        run("git", "checkout", "--", "pyproject.toml", "src/subvectors/__init__.py", "README.md")
        print("[i] aborted, version bump reverted")
        return 0

    if touched:
        run("git", "add", *[str(REPO_ROOT / name) for name in
                            ("pyproject.toml", "src/subvectors/__init__.py", "README.md")])
        run("git", "commit", "-m", f"chore(release): {version}")
        run("git", "push", "origin", "main")
    run("git", "tag", tag)
    run("git", "push", "origin", tag)

    create = ["gh", "release", "create", tag, "--title", args.title or tag]
    create += ["--notes-file", str(args.notes_file)] if args.notes_file else ["--generate-notes"]
    print("[+] release: " + run(*create))

    print("[i] waiting for the publish workflow to reach PyPI")
    if not verify_pypi(version):
        print(
            f"[-] {version} is not on PyPI yet. Check "
            "`gh run list --workflow=release.yml` before assuming it failed.",
            file=sys.stderr,
        )
        return 1
    print(f"[+] pypi.org/project/subvectors/{version}/ is live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
