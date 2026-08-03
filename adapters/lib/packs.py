#!/usr/bin/env python3
"""Manage optional third-party skill packs declared in packs/packs.json.

Packs are opt-in. Nothing here installs anything unless the user explicitly runs
`add`, and detection is strictly read-only: it reports which declared packs look
relevant to the current project and stops there.

Ownership is tracked per config entry, not per platform — see the state file shape
in docs/superpowers/plans/2026-08-03-skill-packs.md. If the user already had a
plugin listed, we did not add it and will never remove it.

Subcommands:
  detect  — which declared packs match the current project (read-only)
  status  — every declared pack, its detection result, and its install state
  add     — install a pack
  remove  — reverse what we recorded inserting
  sync    — re-apply opted-in packs; drop packs no longer declared
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Mapping

REPO = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO / "packs" / "packs.json"
PLATFORMS = ("claude-code", "codex", "cursor")


def load_registry(path: Path) -> dict:
    data = json.loads(path.read_text())
    if data.get("schema") != 1:
        raise SystemExit(f"packs.py: unsupported registry schema {data.get('schema')!r}")
    return data.get("packs", {})


def load_state(path: Path) -> dict:
    """Our own sidecar. Tolerant: an unreadable sidecar just means 'nothing installed'."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_settings(path: Path) -> dict:
    """The user's settings.json. Strict: never replace config we could not read.

    load_state's tolerance is wrong here — collapsing a malformed settings.json to {}
    and writing it back would destroy the user's whole configuration.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(
            f"packs.py: refusing to rewrite {path} — it exists but could not be read ({exc}). "
            "Fix or move the file, then retry."
        )
    return data if isinstance(data, dict) else {}


def project_root(start: Path) -> Path:
    """Git toplevel of `start`, or `start` itself when not in a repository."""
    try:
        r = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return start
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip())
    return start


def pack_matches(pack: dict, root: Path, env: Mapping[str, str]) -> bool:
    """OR over files / env / contains. Root-only: never descends into subdirectories."""
    detect = pack.get("detect", {})
    for name in detect.get("files", []):
        if (root / name).is_file():
            return True
    for var in detect.get("env", []):
        if env.get(var):
            return True
    for entry in detect.get("contains", []):
        target = root / entry["file"]
        if not target.is_file():
            continue
        try:
            text = target.read_text(errors="replace")
        except OSError:
            continue
        if re.search(entry["pattern"], text, re.MULTILINE):
            return True
    return False


def settings_path(args) -> Path:
    return Path(args.settings) if args.settings else Path.home() / ".claude" / "settings.json"


def state_path(args) -> Path:
    if args.state:
        return Path(args.state)
    return settings_path(args).parent / ".100xprism-packs.json"


def describe(packs: dict, root: Path, env: Mapping[str, str], state: dict) -> list[dict]:
    installed = state.get("packs", {})
    return [
        {
            "slug": slug,
            "title": pack.get("title", slug),
            "description": pack.get("description", ""),
            "source": pack.get("source", ""),
            "detected": pack_matches(pack, root, env),
            "platforms": installed.get(slug, {}).get("platforms", {}),
        }
        for slug, pack in sorted(packs.items())
    ]


def render(rows: list[dict]) -> str:
    lines = []
    for row in rows:
        if row["platforms"]:
            note = "installed: " + ", ".join(f"{k}={v}" for k, v in sorted(row["platforms"].items()))
        elif row["detected"]:
            note = f"detected here — run `/pack add {row['slug']}` to install"
        else:
            note = "not installed"
        lines.append(f"  {row['slug']:<14} {row['title']}\n    {note}")
    return "\n".join(lines) if lines else "  (no packs declared)"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="packs.py")
    ap.add_argument("command", choices=["detect", "status", "add", "remove", "sync"])
    ap.add_argument("slug", nargs="?", default="")
    ap.add_argument("--packs", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--project", default=".")
    ap.add_argument("--settings", default="")
    ap.add_argument("--state", default="")
    ap.add_argument("--json", action="store_true")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    packs = load_registry(Path(args.packs))
    state = load_state(state_path(args))

    if args.command in ("detect", "status"):
        root = project_root(Path(args.project).resolve())
        rows = describe(packs, root, os.environ, state)
        if args.command == "detect":
            rows = [r for r in rows if r["detected"]]
        print(json.dumps({"packs": rows}, indent=2) if args.json else render(rows))
        return 0

    raise SystemExit(f"packs.py: '{args.command}' not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
