#!/usr/bin/env python3
"""
handoff.py — the HANDOFF.md conversation contract for pair-loop runs.

HANDOFF.md is the append-only local record of a coder<->reviewer loop: one
"Round N — ROLE (tool)" section per turn. It is gitignored — the PR body carries
the transcript once a run reaches PR phase, not the tracked file itself. The
reviewer's output must end with exactly `VERDICT: APPROVED` or
`VERDICT: CHANGES_REQUESTED` and list findings as a numbered `[category]
file:line — text` list; parse_verdict/parse_findings are the enforcement side of
that contract, used by scripts/pair-loop.py's `review` subcommand.
"""
import re
from datetime import datetime, timezone

HANDOFF_FILENAME = "HANDOFF.md"

_VERDICT_RE = re.compile(r"VERDICT:\s*(APPROVED|CHANGES_REQUESTED)")
_FINDING_RE = re.compile(
    r"^\s*\d+\.\s*\[(?P<category>[^\]]+)\]\s*(?:(?P<location>\S+:\d+)\s*—\s*)?(?P<text>.+)$")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def init_file(path, run_id, task, branch, coder, reviewer):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Pair-Loop Handoff — {run_id}\n"
                f"Task: {task} · Branch: {branch} · Coder: {coder} · Reviewer: {reviewer}\n")


def append_coder_round(path, n, tool, body):
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n## Round {n} — CODER ({tool}) · {_now()}\n{body}\n")


def append_reviewer_round(path, n, tool, findings, verdict):
    lines = [f"\n## Round {n} — REVIEWER ({tool}) · {_now()}\n"]
    if findings:
        lines.append("### Findings\n")
        for i, fnd in enumerate(findings, 1):
            loc = f"{fnd['location']} — " if fnd.get("location") else ""
            lines.append(f"{i}. [{fnd['category']}] {loc}{fnd['text']}\n")
    lines.append(f"VERDICT: {verdict}\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write("".join(lines))


def parse_verdict(reviewer_output):
    matches = _VERDICT_RE.findall(reviewer_output or "")
    return matches[-1] if matches else None


def parse_findings(reviewer_output):
    findings = []
    for line in (reviewer_output or "").splitlines():
        m = _FINDING_RE.match(line)
        if m:
            findings.append({
                "n": len(findings) + 1,
                "category": m.group("category").strip(),
                "location": (m.group("location") or "").strip(),
                "text": m.group("text").strip(),
            })
    return findings
