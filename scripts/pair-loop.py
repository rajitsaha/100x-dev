#!/usr/bin/env python3
"""
pair-loop.py — CLI orchestration for the /pair-loop handoff skill.

The interactive agent running the skill IS the coder; this CLI never simulates
coding. It owns: run bookkeeping (manifest + HANDOFF.md), the per-round budget
check, invoking the reviewer subprocess, and PR-body assembly. See
docs/superpowers/specs/2026-07-09-pair-loop-handoff-skill-design.md for the
full state machine.

Subcommands: start, budget-check, coder-done, review, finish.
"""
import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_manifest  # noqa: E402
import handoff  # noqa: E402
import _config  # noqa: E402
import _budget  # noqa: E402
import pricing  # noqa: E402
import adapters.claude_code as claude_code  # noqa: E402
import adapters.codex as codex  # noqa: E402


def _git_dirty(cwd):
    r = subprocess.run(["git", "status", "--porcelain"], cwd=cwd,
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def _current_branch(cwd):
    r = subprocess.run(["git", "branch", "--show-current"], cwd=cwd,
                       capture_output=True, text=True)
    return r.stdout.strip() or "HEAD"


def cmd_start(args):
    cwd = os.path.abspath(args.cwd or ".")
    # The dirty-tree check must run before any manifest/HANDOFF.md side effects
    # are created — a rejected start must leave zero partial state behind.
    if _git_dirty(cwd):
        print("error: working tree is dirty — commit or stash before starting a pair-loop run",
              file=sys.stderr)
        sys.exit(1)
    cfg = _config.load_config()["pair_loop"]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    branch = _current_branch(cwd)
    manifest = run_manifest.new_manifest(run_id, args.task, cwd, branch,
                                          cfg["coder"], cfg["reviewer"])
    run_manifest.save_manifest(manifest)
    handoff_path = os.path.join(cwd, handoff.HANDOFF_FILENAME)
    handoff.init_file(handoff_path, run_id, args.task, branch, cfg["coder"], cfg["reviewer"])
    print(json.dumps({"run_id": run_id, "manifest_path": run_manifest.manifest_path(run_id),
                      "handoff_path": handoff_path, "max_rounds": cfg["max_rounds"],
                      "coder": cfg["coder"], "reviewer": cfg["reviewer"]}))


def cmd_budget_check(args):
    manifest = run_manifest.load_manifest(args.run)
    per_run = _config.load_config()["budget"].get("per_run_usd")
    summaries = claude_code.scan(verbose=False) + codex.scan(verbose=False)
    cost = run_manifest.run_cost(manifest, summaries)
    _, level = _budget.status_for(cost["total"], per_run)
    print(json.dumps({"level": level, "spent": cost["total"], "limit": per_run}))
    sys.exit(2 if level == "alert" else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start")
    p_start.add_argument("--task", required=True)
    p_start.add_argument("--cwd", default=None)
    p_start.set_defaults(func=cmd_start)

    p_budget = sub.add_parser("budget-check")
    p_budget.add_argument("--run", required=True)
    p_budget.set_defaults(func=cmd_budget_check)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
