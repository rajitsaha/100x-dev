"""Cost adapters: per-tool sources of (dir, day, token) usage.

Claude Code and Codex expose exact local token counters. Cursor and Antigravity
expose local activity/session evidence without token counters; their adapters
collect that coverage but intentionally emit no billable usage.
"""
from collections import namedtuple

Usage = namedtuple("Usage", "dir day input output cache_read cache_write tool")

from . import antigravity, claude_code, codex, cursor, pi  # noqa: E402

ADAPTERS = [claude_code, codex, cursor, antigravity, pi]
