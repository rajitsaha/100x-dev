#!/usr/bin/env python3
"""
run_manifest.py — schema v1 reader/writer + session-cost join for pair-loop runs.

Manifest files live at ~/.100xprism/handoff-runs/<run-id>.json, one per pair-loop
run, written incrementally (atomic rename) by the pair-loop skill so a crashed run
still leaves an ingestable partial manifest. Single source of truth for the
schema and for joining a run's rounds to token cost — both the dashboard
(aggregate view, token-dashboard.py) and run-cost.py (a running loop's own
budget check) use it.
"""
import glob
import json
import os
import tempfile
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
RUNS_DIR = os.path.join(HOME, ".100xprism", "handoff-runs")
SCHEMA_VERSION = 1


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_manifest(run_id, task, cwd, branch, coder, reviewer, reviewer_fallback=False):
    return {
        "v": SCHEMA_VERSION, "run_id": run_id, "task": task, "cwd": cwd,
        "branch": branch, "pr": None, "coder": coder, "reviewer": reviewer,
        "reviewer_fallback": reviewer_fallback, "rounds": [],
        "outcome": {"verdict": None, "rounds": 0, "merged": None},
    }


def manifest_path(run_id):
    return os.path.join(RUNS_DIR, f"{run_id}.json")


def save_manifest(manifest):
    os.makedirs(RUNS_DIR, exist_ok=True)
    path = manifest_path(manifest["run_id"])
    fd, tmp = tempfile.mkstemp(dir=RUNS_DIR, prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    os.replace(tmp, path)


def load_manifest(run_id_or_path):
    path = run_id_or_path if str(run_id_or_path).endswith(".json") else manifest_path(run_id_or_path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_manifests():
    return sorted(glob.glob(os.path.join(RUNS_DIR, "*.json")))


def add_round(manifest, role, tool, session_id=None):
    """Start a new round (paired coder+reviewer rounds share the same `n`;
    a fresh coder round after a reviewer verdict starts the next `n`)."""
    if not manifest["rounds"]:
        n = 1
    else:
        last = manifest["rounds"][-1]
        n = last["n"] if (last["role"] == "coder" and role == "reviewer") else last["n"] + 1
    round_ = {"n": n, "role": role, "tool": tool, "session_id": session_id,
              "started": _now(), "ended": None}
    manifest["rounds"].append(round_)
    save_manifest(manifest)
    return round_


def close_round(manifest, round_, **fields):
    round_["ended"] = _now()
    round_.update(fields)
    save_manifest(manifest)


def close_run(manifest, verdict, merged=None):
    manifest["outcome"] = {
        "verdict": verdict,
        "rounds": manifest["rounds"][-1]["n"] if manifest["rounds"] else 0,
        "merged": merged,
    }
    save_manifest(manifest)


# ------------------------------------------------------------- cost join

def _parse_ts(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")


def round_cost(round_, summaries, pricing_mod, cwd=None):
    """Cost of one round: exact session-id match; else time-window overlap
    against summaries whose file mtime falls inside [started, ended] AND whose
    project label overlaps `cwd` (best-effort; returns 0.0 if nothing matches —
    never guesses)."""
    sid = round_.get("session_id")
    if sid:
        for s in summaries:
            if s.get("session_id") == sid:
                cost, _ = pricing_mod.cost_by_model(s.get("by_model", {}))
                return cost
    if not (round_.get("started") and round_.get("ended")):
        return 0.0
    start, end = _parse_ts(round_["started"]), _parse_ts(round_["ended"])
    total = 0.0
    for s in summaries:
        if cwd and s.get("project") and (cwd not in s["project"] and s["project"] not in cwd):
            continue
        mtime = s.get("mtime")
        if mtime is None:
            continue
        file_dt = datetime.utcfromtimestamp(mtime)
        if start <= file_dt <= end:
            c, _ = pricing_mod.cost_by_model(s.get("by_model", {}))
            total += c
    return total


def run_cost(manifest, summaries):
    """Total $ for a run, split by role: {"total":, "coder":, "reviewer":}."""
    import pricing as pricing_mod
    cwd = manifest.get("cwd")
    total, by_role = 0.0, {"coder": 0.0, "reviewer": 0.0}
    for r in manifest["rounds"]:
        c = round_cost(r, summaries, pricing_mod, cwd=cwd)
        total += c
        by_role[r["role"]] = by_role.get(r["role"], 0.0) + c
    return {"total": round(total, 4), "coder": round(by_role["coder"], 4),
            "reviewer": round(by_role["reviewer"], 4)}
