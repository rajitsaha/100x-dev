"""Registry for local AI-tool usage collectors.

The registry carries provenance and measurement capability separately from adapter
implementation so the dashboard/CLI cannot silently treat activity as billable usage.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from . import antigravity, claude_code, codex, cursor, pi


@dataclass(frozen=True)
class Collector:
    tool: str
    measurement: str
    source: str
    limitations: tuple[str, ...]
    module: ModuleType

    def scan(self, verbose: bool = False, **kwargs):
        return self.module.scan(verbose=verbose, **kwargs)


def collectors() -> list[Collector]:
    """Return collectors in stable display order."""
    return [
        Collector(
            "claude-code", "exact", "~/.claude/projects/**/*.jsonl", (), claude_code,
        ),
        Collector(
            "codex", "exact", "~/.codex/sessions/**/rollout-*.jsonl",
            ("cache-write counters are unavailable",), codex,
        ),
        Collector(
            "cursor", "activity_only", "~/.cursor/projects/*/agent-transcripts/**/*.jsonl",
            ("observed local transcripts expose no provider token counters",), cursor,
        ),
        Collector(
            "antigravity", "activity_only", "~/.gemini/antigravity",
            ("local protobuf schema exposes no provider token counters",), antigravity,
        ),
        Collector(
            "pi", "best_effort", "~/.pi/agent/sessions/**/*.jsonl",
            ("session formats vary; only rows carrying native usage fields are metered",), pi,
        ),
    ]
