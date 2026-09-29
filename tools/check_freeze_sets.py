#!/usr/bin/env python3
"""Refuse a study whose freeze set covers a file meant to be appended after it.

A whole-study manifest exists to pin what MUST NOT change. `DEVIATIONS.md` is
the opposite: its purpose is to be written *after* the freeze, when a study finds
something its registration did not anticipate. Covering it turns recording a
deviation into an edit of a frozen artifact, so the study must choose between
leaving the problem unrecorded and breaking its own anchor. Both are worse than
the problem. `README.md` is the same shape for a different reason: its status
banner is false the moment the attempt runs.

This reads each study's GENERATED manifest, not its builder's source. That is
deliberate. The first version of this guard parsed `make_manifest.py` for string
literals and reported Study 015 as clean — 015 covers every top-level `*.md` by
glob and names neither file, so a source scan sees nothing while the manifest
would have carried both. 015 is in fact the strongest implementation: it globs
widely and then excludes the two BY CONSTRUCTION, after its own round 6 found an
earlier exclusion tautological because no glob had ever reached a top-level
`.md`. A guard that could be defeated by a glob would repeat exactly that defect.
The manifest is the covered set; anything else is a description of it.

It also checks that each manifest still DESCRIBES its tree: every listed file
is hashed and compared to its recorded digest. A covered file edited after the
manifest was written means the pin no longer describes the tree; a covered
file that is gone means the pin points at nothing. Either fails the run,
naming the study, the path, and which of the two it is.

A manifest line the guard cannot read is a problem of its own: a line no
check covers must not pass silently. Every non-blank, non-comment line has to
be 64 lowercase hex digits, two spaces, and a path — anything else (a
one-space separator, a tab, the `*` binary marker) fails the run naming the
study, the line number, and the line.

Run: python tools/check_freeze_sets.py
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STUDIES = ROOT / "studies"

# A file whose purpose is to change after the freeze must not be pinned by it.
APPEND_AFTER_FREEZE = ("DEVIATIONS.md", "README.md")

# Frozen before this guard existed. Their pins are correct and their anchors are
# published; re-scoping a frozen manifest now would rewrite an anchor to repair a
# mechanism none of these three ever used, which is the worse trade. Corrections
# for them belong in ANALYSIS.md, outside every covered set. Issue #65 proposes
# exactly this: fix it forward and leave these alone.
GRANDFATHERED = {
    "016-policy-currency-anchor",
    "017-witnessed-currency",
    "018-transition-rules",
}

_DIGEST_RE = re.compile(r"[0-9a-f]{64}")


def covered_paths(manifest: pathlib.Path) -> set[str]:
    """Every study-relative path a manifest pins.

    Each line is "<digest>  <path>"; the path is everything after the separator,
    so a name containing spaces survives.
    """
    covered = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        _, separator, path = line.partition("  ")
        if separator:
            covered.add(path.strip())
    return covered


def manifest_entries(manifest: pathlib.Path) -> list[tuple[str, str]]:
    """Every (digest, study-relative path) pair a manifest pins.

    Same line grammar as `covered_paths`: "<digest>  <path>", blanks and `#`
    comments skipped. Kept separate so the covered-set check above stays
    untouched.
    """
    entries = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, separator, path = line.partition("  ")
        if separator:
            entries.append((digest.strip(), path.strip()))
    return entries


def unreadable_lines(manifest: pathlib.Path) -> list[tuple[int, str]]:
    """(line number, line) pairs the guard cannot read.

    A readable line is 64 lowercase hex digits, two spaces, and a path -- the
    same grammar `covered_paths` and `manifest_entries` parse. Anything else
    that is not blank or a `#` comment is a line no check covers, so it is
    reported rather than silently skipped. Line numbers count every physical
    line so the report points at the file as written.
    """
    bad = []
    for lineno, raw in enumerate(manifest.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        digest, separator, path = line.partition("  ")
        if not separator or not path.strip() or _DIGEST_RE.fullmatch(digest.strip()) is None:
            bad.append((lineno, line))
    return bad


def sha256_of(path: pathlib.Path) -> str:
    """Hex digest of a file's bytes, streamed so large files stay cheap."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    problems: list[str] = []
    checked = 0
    grandfathered_hits = 0

    for manifest in sorted(STUDIES.glob("*/harness/STUDY-MANIFEST.sha256")):
        study = manifest.parent.parent.name
        checked += 1
        for lineno, text in unreadable_lines(manifest):
            problems.append(
                f"{study}: harness/STUDY-MANIFEST.sha256 line {lineno} is not "
                f"a '<digest>  <path>' line the guard can read: {text!r}. A line "
                f"the guard cannot parse is a line no check covers; write it as "
                f"64 lowercase hex digits, two spaces, and the study-relative path."
            )
        covered = covered_paths(manifest)
        for name in APPEND_AFTER_FREEZE:
            if name not in covered:
                continue
            if study in GRANDFATHERED:
                grandfathered_hits += 1
                continue
            problems.append(
                f"{study}: the freeze set covers {name}, which exists to be written "
                f"after the freeze. Pinning it means recording a deviation breaks the "
                f"anchor that deviation is recorded against. Exclude it by construction "
                f"and say so, as studies/015-cloudflare-os-boundary does (issue #65)."
            )
        study_dir = manifest.parent.parent
        for digest, path in manifest_entries(manifest):
            target = study_dir / path
            if not target.is_file():
                problems.append(
                    f"{study}: {path} is listed in harness/STUDY-MANIFEST.sha256 "
                    f"but is missing from the tree. Restore the file or regenerate "
                    f"the manifest; do not leave the pin pointing at nothing."
                )
            elif sha256_of(target) != digest:
                problems.append(
                    f"{study}: {path} no longer matches harness/STUDY-MANIFEST.sha256: "
                    f"the covered file was edited after the manifest was written. "
                    f"Revert the edit or regenerate the manifest."
                )

    if not checked:
        print("no study manifests found: this guard would pass vacuously", file=sys.stderr)
        return 1
    if not grandfathered_hits:
        # The exemptions describe three studies that really do carry these files.
        # If none does, the list is stale and the guard is weaker than it reads.
        print(
            "no grandfathered study still covers an append-after-freeze file; "
            "the GRANDFATHERED set is stale and should be removed",
            file=sys.stderr,
        )
        return 1

    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"checked {checked} study freeze set(s); {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())