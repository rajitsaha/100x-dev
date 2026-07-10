"""
Codex cost adapter — parses ~/.codex/sessions/**/rollout-*.jsonl.

Verified against a real Codex CLI (v0.142.5) rollout on 2026-07-09: each file is
one session, containing `session_meta` (session_id, cwd), `turn_context`
(per-turn `model`), and `event_msg`/`token_count` events whose
`info.total_token_usage` is a CUMULATIVE running total for the session (non-
decreasing across consecutive events in the sample file — but that was a
single 6-event sample, not a documented API guarantee). Per-event token counts
are therefore deltas between consecutive readings, not the readings
themselves — EXCEPT when a reading's counter is lower than the previous one
(e.g. a context-compaction event resetting `total_token_usage` mid-session),
in which case that reading is treated as a fresh baseline and its own
cumulative values are credited directly, rather than computing a negative
delta against the stale pre-reset baseline (which would silently discard real
usage via clamping).

Codex/OpenAI's cache accounting folds cached tokens INTO `input_tokens` (unlike
Claude Code's separate cache_read, which is additional to input) — so `input`
here is computed as `input_tokens - cached_input_tokens` to line up with our
(input, cache_read) split. Codex exposes no cache-write count; cache_write is
always 0 for this adapter — a documented limitation, not a bug.
"""
import glob
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import _value  # noqa: E402

from . import Usage  # noqa: E402

TOOL = "codex"
HOME = os.path.expanduser("~")
SOURCE_DIR = os.path.join(HOME, ".codex", "sessions")
CACHE_FILE = os.path.join(HOME, ".claude", ".token-dashboard-codex-cache.json")
CACHE_VERSION = 1


def _empty():
    return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}


def _add(dst, i, o, cr, cw):
    dst["input"] += i
    dst["output"] += o
    dst["cache_read"] += cr
    dst["cache_write"] += cw


def parse_file(path):
    """Aggregate one Codex rollout into the same summary shape claude_code.parse_file
    produces (minus fields Codex has no data for: composition, first_fixed,
    subagent/skill attribution)."""
    totals = _empty()
    by_day = defaultdict(_empty)
    by_model = defaultdict(_empty)
    by_day_model = defaultdict(lambda: defaultdict(_empty))
    session_id = None
    cwd = None
    current_model = "unknown"
    prev_cum = None
    msgs = 0

    for line in open(path, errors="ignore"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if not isinstance(o, dict):
            continue
        t = o.get("type")
        if t == "session_meta":
            payload = o.get("payload") or {}
            session_id = payload.get("session_id") or payload.get("id")
            cwd = payload.get("cwd")
            continue
        if t == "turn_context":
            model = (o.get("payload") or {}).get("model")
            if model:
                current_model = model
            continue
        if t != "event_msg":
            continue
        payload = o.get("payload") or {}
        if payload.get("type") != "token_count":
            continue
        cum = (payload.get("info") or {}).get("total_token_usage")
        if not isinstance(cum, dict):
            continue
        is_reset = prev_cum is not None and (
            cum.get("input_tokens", 0) < prev_cum.get("input_tokens", 0)
            or cum.get("cached_input_tokens", 0) < prev_cum.get("cached_input_tokens", 0)
            or cum.get("output_tokens", 0) < prev_cum.get("output_tokens", 0)
        )
        if prev_cum is None or is_reset:
            # No prior baseline, or the cumulative counter went DOWN (e.g. a
            # context-compaction event reset total_token_usage mid-session).
            # A negative delta against a stale pre-reset baseline is
            # nonsensical and would be silently clamped to 0, discarding real
            # usage — so treat this reading as a fresh baseline instead and
            # credit its own cumulative values directly.
            d_in_total = cum.get("input_tokens", 0)
            d_cr = cum.get("cached_input_tokens", 0)
            d_out = cum.get("output_tokens", 0)
        else:
            d_in_total = cum.get("input_tokens", 0) - prev_cum.get("input_tokens", 0)
            d_cr = cum.get("cached_input_tokens", 0) - prev_cum.get("cached_input_tokens", 0)
            d_out = cum.get("output_tokens", 0) - prev_cum.get("output_tokens", 0)
        prev_cum = cum
        if not is_reset and d_in_total <= 0 and d_out <= 0 and d_cr <= 0:
            continue  # duplicate/unchanged event (e.g. an end-of-session repeat)
        d_cr = max(d_cr, 0)
        d_in = max(d_in_total - d_cr, 0)
        d_out = max(d_out, 0)
        msgs += 1
        _add(totals, d_in, d_out, d_cr, 0)
        _add(by_model[current_model], d_in, d_out, d_cr, 0)
        day = (o.get("timestamp") or "")[:10] or "unknown"
        _add(by_day[day], d_in, d_out, d_cr, 0)
        _add(by_day_model[day][current_model], d_in, d_out, d_cr, 0)

    return {
        "totals": totals,
        "by_day": dict(by_day),
        "by_model": dict(by_model),
        "by_day_model": {d: dict(models) for d, models in by_day_model.items()},
        "comp": {},
        "msgs": msgs,
        "turns": msgs,
        "first_fixed": 0,
        "session_id": session_id,
        "main_tokens": dict(totals),
        "subagent_tokens": _empty(),
        "by_skill": {},
        "skill_invocations": {},
        "skill_exact": [],
        "cwd": cwd,
    }


def load_cache():
    try:
        with open(CACHE_FILE) as f:
            c = json.load(f)
        if c.get("version") == CACHE_VERSION:
            return c.get("files", {})
    except Exception:
        pass
    return {}


def save_cache(files):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"version": CACHE_VERSION, "files": files}, f)
    except Exception as e:
        print(f"warning: could not write codex cache: {e}", file=sys.stderr)


def _project_label(cwd):
    return _value.project_label_for_path(cwd) if cwd else "unknown"


def scan(verbose=False):
    """Glob + incrementally parse every Codex rollout. Returns [] if Codex has
    never been used locally (no ~/.codex/sessions dir)."""
    if not os.path.isdir(SOURCE_DIR):
        return []
    cache = load_cache()
    paths = glob.glob(os.path.join(SOURCE_DIR, "**", "*.jsonl"), recursive=True)
    new_cache = {}
    reparsed = 0
    for p in paths:
        try:
            st = os.stat(p)
        except OSError:
            continue
        prev = cache.get(p)
        if prev and prev.get("mtime") == st.st_mtime and prev.get("size") == st.st_size:
            new_cache[p] = prev
            continue
        summary = parse_file(p)
        summary["mtime"] = st.st_mtime
        summary["size"] = st.st_size
        cwd = summary.get("cwd")
        summary["project"] = _project_label(cwd)
        summary["projdir"] = (_value.mangle_path(os.path.abspath(os.path.expanduser(cwd)))
                               if cwd else "unknown")
        summary["tool"] = TOOL
        new_cache[p] = summary
        reparsed += 1
    save_cache(new_cache)
    if verbose:
        print(f"codex: scanned {len(paths)} rollouts ({reparsed} re-parsed, "
              f"{len(paths) - reparsed} cached)", file=sys.stderr)
    return list(new_cache.values())


def iter_dir_days(file_summaries):
    for s in file_summaries:
        projdir = s.get("projdir") or ""
        for day, d in (s.get("by_day") or {}).items():
            yield Usage(projdir, day, d.get("input", 0), d.get("output", 0),
                        d.get("cache_read", 0), d.get("cache_write", 0), TOOL)
