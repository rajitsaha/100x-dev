#!/usr/bin/env python3
"""Fast, local, versioned cross-tool token report.

This path intentionally avoids Git/GitHub/value scans used by the full dashboard.
It reports provider counters only; activity-only collectors never enter token totals.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

from adapters.registry import collectors

PURPOSES = ("input", "output", "cache_read", "cache_write")
SCHEMA_VERSION = 1


def _empty() -> dict[str, int]:
    return {key: 0 for key in PURPOSES}


def build_report(registry=None, tool: str | None = None) -> dict:
    registry = list(registry if registry is not None else collectors())
    if tool:
        registry = [collector for collector in registry if collector.tool == tool]
        if not registry:
            raise ValueError(f"unknown tool: {tool}")

    totals = _empty()
    sources = []
    for collector in registry:
        try:
            rows = collector.scan(verbose=False)
            error = None
        except Exception as exc:  # collector isolation is deliberate
            rows = []
            error = str(exc)

        source_totals = _empty()
        metered = collector.measurement != "activity_only"
        if metered:
            for row in rows:
                usage = row.get("totals") or {}
                for key in PURPOSES:
                    source_totals[key] += int(usage.get(key, 0) or 0)
                    totals[key] += int(usage.get(key, 0) or 0)

        sources.append({
            "tool": collector.tool,
            "measurement": collector.measurement,
            "source": collector.source,
            "limitations": list(collector.limitations),
            "sessions": len(rows),
            "metered_sessions": sum(
                1 for row in rows if metered and sum(int((row.get("totals") or {}).get(k, 0) or 0) for k in PURPOSES)
            ),
            "tokens": source_totals,
            "error": error,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "totals": totals,
        "sources": sources,
    }


def print_text(report: dict) -> None:
    total = sum(report["totals"].values())
    print(f"Cross-tool token utilization: {total:,} exact/best-effort provider tokens")
    for source in report["sources"]:
        tokens = sum(source["tokens"].values())
        note = f"; error: {source['error']}" if source["error"] else ""
        print(
            f"- {source['tool']}: {tokens:,} tokens; {source['sessions']} sessions; "
            f"measurement={source['measurement']}{note}"
        )
        for limitation in source["limitations"]:
            print(f"  limitation: {limitation}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--tool", default="")
    args = parser.parse_args()
    try:
        report = build_report(tool=args.tool or None)
    except ValueError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
