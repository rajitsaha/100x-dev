"""
Pi cost adapter — parses ~/.pi/agent/sessions/**/*.jsonl (best-effort).

Pi session JSONL shape varies by version. This adapter extracts usage when
present; otherwise yields empty token buckets (never invents prices). Missing
directory → scan() returns [].
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import _value  # noqa: E402

from . import Usage  # noqa: E402

TOOL = "pi"
HOME = os.path.expanduser("~")
SOURCE_DIR = os.path.join(HOME, ".pi", "agent", "sessions")
CACHE_FILE = os.path.join(HOME, ".claude", ".token-dashboard-pi-cache.json")
CACHE_VERSION = 1


def _empty():
    return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}


def _add(dst, i, o, cr, cw):
    dst["input"] += i
    dst["output"] += o
    dst["cache_read"] += cr
    dst["cache_write"] += cw


def _usage_from_obj(o: dict):
    for key in ("usage", "token_usage", "tokens"):
        u = o.get(key)
        if isinstance(u, dict):
            inp = int(u.get("input") or u.get("input_tokens") or u.get("prompt_tokens") or 0)
            out = int(u.get("output") or u.get("output_tokens") or u.get("completion_tokens") or 0)
            cr = int(u.get("cache_read") or u.get("cache_read_input_tokens") or u.get("cached_tokens") or 0)
            cw = int(u.get("cache_write") or u.get("cache_creation_input_tokens") or 0)
            if inp or out or cr or cw:
                return inp, out, cr, cw
    inp = int(o.get("input_tokens") or o.get("prompt_tokens") or 0)
    out = int(o.get("output_tokens") or o.get("completion_tokens") or 0)
    cr = int(o.get("cache_read_input_tokens") or o.get("cached_tokens") or 0)
    cw = int(o.get("cache_creation_input_tokens") or 0)
    if inp or out or cr or cw:
        return inp, out, cr, cw
    return None


def _model_from_obj(o: dict) -> str:
    for key in ("model", "modelId", "model_id"):
        v = o.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    m = o.get("message")
    if isinstance(m, dict):
        v = m.get("model")
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "unknown"


def _day_from_obj(o: dict, fallback: str) -> str:
    ts = o.get("timestamp") or o.get("time") or o.get("ts")
    if isinstance(ts, (int, float)):
        try:
            if ts > 1e12:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except (OSError, ValueError, OverflowError):
            return fallback
    if isinstance(ts, str) and len(ts) >= 10 and ts[4] == "-":
        return ts[:10]
    return fallback


def parse_file(path):
    totals = _empty()
    by_day = defaultdict(_empty)
    by_model = defaultdict(_empty)
    by_day_model = defaultdict(lambda: defaultdict(_empty))
    main_subagent_by_day = defaultdict(lambda: {"main": _empty(), "subagent": _empty()})
    session_id = None
    cwd = None
    msgs = 0
    st = os.stat(path)
    fallback_day = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")

    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except Exception:
                continue
            if not isinstance(o, dict):
                continue
            session_id = session_id or o.get("sessionId") or o.get("session_id") or o.get("id")
            meta = o.get("meta") if isinstance(o.get("meta"), dict) else {}
            cwd = cwd or o.get("cwd") or meta.get("cwd")
            day = _day_from_obj(o, fallback_day)

            usage = _usage_from_obj(o)
            if usage is None and isinstance(o.get("message"), dict):
                usage = _usage_from_obj(o["message"])
            if usage is None:
                continue
            i, out, cr, cw = usage
            model = _model_from_obj(o)
            msgs += 1
            _add(totals, i, out, cr, cw)
            _add(by_day[day], i, out, cr, cw)
            _add(by_model[model], i, out, cr, cw)
            _add(by_day_model[day][model], i, out, cr, cw)
            _add(main_subagent_by_day[day]["main"], i, out, cr, cw)

    return {
        "totals": totals,
        "by_day": dict(by_day),
        "by_model": dict(by_model),
        "by_day_model": {d: dict(m) for d, m in by_day_model.items()},
        "main_subagent_by_day": {
            d: {"main": v["main"], "subagent": v["subagent"]}
            for d, v in main_subagent_by_day.items()
        },
        "session_id": session_id,
        "cwd": cwd,
        "msgs": msgs,
        "comp": {},
        "by_skill": {},
        "skill_invocations": {},
        "tool": TOOL,
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
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump({"version": CACHE_VERSION, "files": files}, f)
    except Exception as e:
        print(f"warning: could not write pi cache: {e}", file=sys.stderr)


def scan(verbose=False):
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
        summary["project"] = _value.project_label_for_path(cwd) if cwd else "pi"
        summary["projdir"] = (
            _value.mangle_path(os.path.abspath(os.path.expanduser(cwd))) if cwd else "unknown"
        )
        summary["tool"] = TOOL
        new_cache[p] = summary
        reparsed += 1
    save_cache(new_cache)
    if verbose:
        print(
            f"pi: scanned {len(paths)} sessions ({reparsed} re-parsed, "
            f"{len(paths) - reparsed} cached)",
            file=sys.stderr,
        )
    return list(new_cache.values())


def iter_dir_days(file_summaries):
    for s in file_summaries:
        projdir = s.get("projdir") or ""
        for day, d in (s.get("by_day") or {}).items():
            yield Usage(
                projdir, day,
                d.get("input", 0), d.get("output", 0),
                d.get("cache_read", 0), d.get("cache_write", 0),
                TOOL,
            )
