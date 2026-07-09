#!/usr/bin/env python3
"""
run-cost.py — print a pair-loop run's cost so far.

Used by the pair-loop skill's per-round budget check (Plan: pair-loop-handoff-
skill) and standalone for inspecting a run.

Usage: python3 scripts/run-cost.py <run-id-or-manifest-path>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_manifest  # noqa: E402
import adapters.claude_code as claude_code  # noqa: E402
import adapters.codex as codex  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print("usage: run-cost.py <run-id-or-manifest-path>", file=sys.stderr)
        sys.exit(1)
    manifest = run_manifest.load_manifest(sys.argv[1])
    summaries = claude_code.scan(verbose=False) + codex.scan(verbose=False)
    result = run_manifest.run_cost(manifest, summaries)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
