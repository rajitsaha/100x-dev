#!/usr/bin/env python3
"""Repo consistency / drift checker for 100xprism.

Run locally (`python3 scripts/meta-check.py`) or in CI (.github/workflows/meta.yml).
Catches the drift classes that have bitten releases before:

  1. Module frontmatter parses cleanly (delimited block + non-empty name & description).
  2. Declared counts in README and selected current docs match what the repo
     actually contains (modules / slash commands / auto-trigger skills / plugins).
  3. Every evals.json is valid JSON.
  4. Version triple agrees: VERSION == package.json.version
     (== git tag when TAG is passed via --tag or the TAG env var, e.g. in release.yml).

Exit code 0 = all checks pass; 1 = at least one failure (each printed with a ✗).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODULES_DIR = REPO / "modules"

failures: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def ok(msg: str) -> None:
    notes.append(msg)


def split_frontmatter(text: str) -> tuple[dict[str, str], bool]:
    """Lenient line-based parse mirroring adapters/lib/modules.py.

    Returns (fields, well_formed). well_formed is False when the leading/closing
    `---` delimiters are missing.
    """
    if not text.startswith("---\n"):
        return {}, False
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, False
    fm: dict[str, str] = {}
    current_key: str | None = None
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if line.startswith(" ") and current_key:
            fm[current_key] = (fm[current_key] + " " + line.strip()).strip()
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            current_key = key.strip()
            fm[current_key] = val.strip()
    return fm, True


def check_modules() -> dict[str, int]:
    """Parse every module; fail on malformed frontmatter. Returns computed counts."""
    skill_files = sorted(MODULES_DIR.glob("*/SKILL.md"))
    if not skill_files:
        fail("no modules found under modules/*/SKILL.md")
        return {"modules": 0, "slash": 0, "skills": 0}

    slash = 0
    aliases = 0
    allowed_tiers = {"core", "on-demand"}
    allowed_retention = {"must", "profile", "resolver"}
    for sf in skill_files:
        fm, well_formed = split_frontmatter(sf.read_text())
        slug = sf.parent.name
        if not well_formed:
            fail(f"{slug}: SKILL.md has no parseable `---` frontmatter block")
            continue
        if not fm.get("name"):
            fail(f"{slug}: frontmatter missing `name`")
        if not fm.get("description"):
            fail(f"{slug}: frontmatter missing `description`")
        tier = fm.get("tier", "on-demand")
        if tier not in allowed_tiers:
            fail(f"{slug}: frontmatter tier='{tier}' must be one of {sorted(allowed_tiers)}")
        retention = fm.get("retention", "")
        if retention and retention not in allowed_retention:
            fail(f"{slug}: frontmatter retention='{retention}' must be one of {sorted(allowed_retention)}")
        command = fm.get("slash_command", "")
        if command:
            slash += 1
            # An alias file is only emitted when the command name differs from the
            # slug — Claude Code already exposes every skill as /<slug>, so a
            # same-name alias double-lists it. See cmd_emit_claude_code.
            if command.lstrip("/") != slug:
                aliases += 1

    total = len(skill_files)
    counts = {"modules": total, "slash": slash, "aliases": aliases, "skills": total - slash}
    ok(f"modules parsed: {total} ({slash} slash commands → {aliases} emitted alias(es), "
       f"{total - slash} auto-trigger skills)")
    return counts


def check_plugins() -> int:
    data = json.loads((REPO / "plugins" / "plugins.json").read_text())
    n = len(data.get("plugins", []))
    # Every enabled plugin must be a fully-qualified name@marketplace id, and its
    # marketplace must be resolvable (built-in official marketplaces or declared
    # in extraKnownMarketplaces). Bare names silently no-op `claude plugin update`.
    OFFICIAL = {"claude-plugins-official", "claude-code-plugins"}
    known = OFFICIAL | set(data.get("extraKnownMarketplaces", {}).keys())
    for entry in data.get("plugins", []):
        if "@" not in entry:
            fail(f"plugins.json: '{entry}' is not a fully-qualified name@marketplace id")
            continue
        marketplace = entry.split("@", 1)[1]
        if marketplace not in known:
            fail(f"plugins.json: '{entry}' references unknown marketplace '{marketplace}'")
    ok(f"plugins[] entries: {n}")
    return n


PACK_PLATFORMS = {"claude-code", "codex", "cursor"}


def check_packs(path: Path) -> int:
    """Validate a pack registry — schema version, required keys, platform names."""
    data = json.loads(path.read_text())
    if data.get("schema") != 1:
        fail(f"packs.json: unsupported `schema` {data.get('schema')!r} (expected 1)")

    packs = data.get("packs", {})
    for slug, pack in packs.items():
        for key in ("title", "description", "source", "detect", "install"):
            if not pack.get(key):
                fail(f"packs.json: '{slug}' missing required key `{key}`")

        install = pack.get("install", {})
        for key in install:
            if key not in PACK_PLATFORMS | {"preferred", "cli"}:
                fail(f"packs.json: '{slug}' unknown install key '{key}'")

        preferred = install.get("preferred")
        if preferred and preferred != "cli" and preferred not in PACK_PLATFORMS:
            fail(f"packs.json: '{slug}' install.preferred='{preferred}' is not 'cli' or a platform")

        cli = install.get("cli")
        if cli:
            for key in ("requires", "command", "covers"):
                if not cli.get(key):
                    fail(f"packs.json: '{slug}' install.cli missing `{key}`")
            for platform in cli.get("covers", []):
                if platform not in PACK_PLATFORMS:
                    fail(f"packs.json: '{slug}' install.cli.covers has unknown platform '{platform}'")

        detect = pack.get("detect", {})
        for key in detect:
            if key not in {"files", "env", "contains"}:
                fail(f"packs.json: '{slug}' unknown detect key '{key}'")
        # Detection is root-only by design (see spec): reject anything path-like so a
        # nested path can never turn into a directory walk.
        paths = list(detect.get("files", [])) + [e.get("file", "") for e in detect.get("contains", [])]
        for p in paths:
            if "/" in p or "\\" in p or p in ("", ".", ".."):
                fail(f"packs.json: '{slug}' detect path '{p}' must be a bare filename")
        for entry in detect.get("contains", []):
            if not entry.get("file") or not entry.get("pattern"):
                fail(f"packs.json: '{slug}' detect.contains entry needs `file` and `pattern`")
                continue
            try:
                re.compile(entry["pattern"])
            except re.error as exc:
                fail(f"packs.json: '{slug}' detect.contains pattern invalid — {exc}")

    ok(f"packs[] entries: {len(packs)}")
    return len(packs)


def check_readme_counts(counts: dict[str, int]) -> None:
    """Assert every numeric count mention in the README matches the repo."""
    readme = (REPO / "README.md").read_text()
    # label in README -> computed key
    patterns = {
        r"(\d+)\s+modules": ("modules", counts["modules"]),
        r"(\d+)\s+slash commands": ("slash commands", counts["slash"]),
        r"(\d+)\s+auto-trigger skills": ("auto-trigger skills", counts["skills"]),
        r"(\d+)\s+(?:Claude Code\s+)?plugins": ("plugins", counts["plugins"]),
    }
    for pat, (label, expected) in patterns.items():
        found = [int(m) for m in re.findall(pat, readme)]
        if not found:
            fail(f"README: no '{label}' count mention found (expected {expected})")
            continue
        bad = [v for v in found if v != expected]
        if bad:
            fail(f"README: '{label}' says {bad} but repo has {expected}")
        else:
            ok(f"README '{label}' count = {expected} ({len(found)} mention(s)) ✓")


def check_current_doc_count_drift(counts: dict[str, int]) -> None:
    """Fail on stale count mentions in current, non-historical project docs."""
    # User-facing docs live on the gh-pages branch, which this checkout does not
    # carry — only repo-resident files can be drift-checked here.
    files = [
        "AGENTS.md",
        "install.sh",
        "package.json",
    ]
    patterns = {
        r"(\d+)\s+modules": ("modules", counts["modules"]),
        r"(\d+)\s+SKILL\.md files": ("SKILL.md files", counts["modules"]),
        r"(\d+)\s+cross-tool modules": ("cross-tool modules", counts["modules"]),
        r"(\d+)\s+slash commands": ("slash commands", counts["slash"]),
        r"(\d+)\s+slash command aliases": ("slash command aliases", counts["aliases"]),
        r"(\d+)\s+command-style modules": ("command-style modules", counts["slash"]),
        r"(\d+)\s+auto-trigger skills": ("auto-trigger skills", counts["skills"]),
        r"(\d+)\s+plugins": ("plugins", counts["plugins"]),
        r"(\d+)\s+Claude Code plugins": ("Claude Code plugins", counts["plugins"]),
    }
    checked = 0
    for rel in files:
        text = (REPO / rel).read_text()
        for pat, (label, expected) in patterns.items():
            found = [int(m) for m in re.findall(pat, text)]
            bad = [v for v in found if v != expected]
            checked += len(found)
            if bad:
                fail(f"{rel}: '{label}' says {bad} but repo has {expected}")
    ok(f"current doc count mentions checked: {checked}")


def check_evals() -> None:
    eval_files = sorted(MODULES_DIR.glob("**/evals.json"))
    bad = 0
    for ef in eval_files:
        try:
            json.loads(ef.read_text())
        except json.JSONDecodeError as e:
            fail(f"{ef.relative_to(REPO)}: invalid JSON — {e}")
            bad += 1
    ok(f"evals.json validated: {len(eval_files)} file(s), {bad} invalid")


def check_version_triple(tag: str | None) -> None:
    version_file = (REPO / "VERSION").read_text().strip()
    pkg_version = json.loads((REPO / "package.json").read_text())["version"]
    if version_file != pkg_version:
        fail(f"version drift: VERSION={version_file} != package.json={pkg_version}")
    else:
        ok(f"VERSION == package.json == {version_file}")
    if tag:
        tag_version = tag.lstrip("v")
        if tag_version != version_file:
            fail(f"version drift: git tag={tag_version} != VERSION={version_file}")
        elif tag_version != pkg_version:
            fail(f"version drift: git tag={tag_version} != package.json={pkg_version}")
        else:
            ok(f"git tag matches version triple ({tag_version})")


def main() -> int:
    ap = argparse.ArgumentParser(description="100xprism repo consistency checker")
    ap.add_argument("--tag", default=os.environ.get("TAG", ""),
                    help="git tag (e.g. v2.0.4) to include in the version-triple check")
    ap.add_argument("--packs", default="",
                    help="pack registry to validate (default: packs/packs.json). "
                         "Tests pass a temp copy so the tracked registry is never mutated.")
    args = ap.parse_args()

    counts = check_modules()
    counts["plugins"] = check_plugins()
    check_packs(Path(args.packs) if args.packs else REPO / "packs" / "packs.json")
    check_readme_counts(counts)
    check_current_doc_count_drift(counts)
    check_evals()
    check_version_triple(args.tag or None)

    print("\n".join(f"  ✓ {n}" for n in notes))
    if failures:
        print("\n".join(f"  ✗ {f}" for f in failures), file=sys.stderr)
        print(f"\nmeta-check: {len(failures)} failure(s)", file=sys.stderr)
        return 1
    print("\nmeta-check: all checks passed ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
