"""
Claude Code cost adapter — owns glob + incremental cache + parse for
~/.claude/projects/**/*.jsonl, plus session/subagent/skill attribution.

Transcript fields used here were verified against real local transcripts on
2026-07-09: `sessionId` (also duplicated as `session_id` on some lines — the
first non-empty one wins), `isSidechain` (bool — true marks a subagent-branch
message), `attributionSkill` / `attributionPlugin` (set natively by Claude Code
when a Skill tool is active — this is EXACT attribution, not a heuristic). Slash
commands that are not Skills (e.g. built-in `/model`) don't set attributionSkill,
so those are segmented via the `<command-name>/xyz</command-name>` marker in the
user turn as a fallback — attribution for that path is a boundary heuristic: once
a marker is seen, usage on subsequent lines is attributed to it until the next
marker or a real attributionSkill supersedes it (same honesty convention as the
existing character-count composition estimate below — never presented as exact).
"""
import glob
import json
import os
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import _value  # noqa: E402 — project_label / mangle_path

from . import Usage  # noqa: E402

TOOL = "claude-code"
HOME = os.path.expanduser("~")
SOURCE_DIR = os.path.join(HOME, ".claude", "projects")
CACHE_FILE = os.path.join(HOME, ".claude", ".token-dashboard-cache.json")
CACHE_VERSION = 4  # bump -> re-parse all transcripts (attribution fields added)
FULL_SCAN_SECONDS = 1800
HOT_FILE_SECONDS = 86400
_MEM_PAYLOAD = None
_MEM_CACHE_KEY = None

project_label = _value.project_label


def _empty():
    return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}


def _add(dst, i, o, cr, cw):
    dst["input"] += i
    dst["output"] += o
    dst["cache_read"] += cr
    dst["cache_write"] += cw


COMP_CATS = ["prompts", "model_output", "code_authored", "tool_calls",
             "files_read", "logs", "other_results"]
COMP_LABELS = {
    "prompts": "your prompts", "model_output": "model output (prose)",
    "code_authored": "code written (edits)", "tool_calls": "tool calls",
    "files_read": "code / files read", "logs": "command output / logs",
    "other_results": "other tool results",
}
_READ_TOOLS = {"Read", "Glob", "Grep", "LS", "NotebookRead"}
_SHELL_TOOLS = {"Bash", "BashOutput"}
_EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
_COMMAND_RE = re.compile(r"<command-name>(/\S+)</command-name>")


def _classify(role, content, comp, tool_names):
    """Tally character counts per content-type category for one message."""
    if isinstance(content, str):
        comp["model_output" if role == "assistant" else "prompts"] += len(content)
        return
    if not isinstance(content, list):
        return
    for b in content:
        if isinstance(b, str):
            comp["model_output" if role == "assistant" else "prompts"] += len(b)
            continue
        if not isinstance(b, dict):
            continue
        bt = b.get("type")
        if bt == "text":
            comp["model_output" if role == "assistant" else "prompts"] += len(b.get("text") or "")
        elif bt == "tool_use":
            name = b.get("name", "")
            tool_names[b.get("id", "")] = name
            sz = len(json.dumps(b.get("input", {}), ensure_ascii=False))
            comp["code_authored" if name in _EDIT_TOOLS else "tool_calls"] += sz
        elif bt == "tool_result":
            name = tool_names.get(b.get("tool_use_id", ""), "")
            c = b.get("content", "")
            if isinstance(c, list):
                sz = sum(len(x.get("text") or "") for x in c if isinstance(x, dict))
            elif isinstance(c, str):
                sz = len(c)
            else:
                sz = len(json.dumps(c, ensure_ascii=False))
            if name in _READ_TOOLS:
                comp["files_read"] += sz
            elif name in _SHELL_TOOLS:
                comp["logs"] += sz
            else:
                comp["other_results"] += sz


def _extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def parse_file(path):
    """Aggregate one Claude Code transcript into totals, breakdowns, and
    session/subagent/skill attribution. Returns a per-file summary dict."""
    totals = _empty()
    by_day = defaultdict(_empty)
    by_model = defaultdict(_empty)
    by_day_model = defaultdict(lambda: defaultdict(_empty))
    comp = defaultdict(int)
    tool_names = {}
    msgs = 0
    first_fixed = None
    turns = 0
    session_id = None
    main_tokens = _empty()
    subagent_tokens = _empty()
    by_skill = defaultdict(_empty)
    skill_invocations = defaultdict(int)
    skill_exact = set()
    # Boundary-heuristic state: the last `<command-name>` marker seen carries
    # forward across lines (no explicit "end" marker exists), until a new
    # marker or a real attributionSkill supersedes it. Real attributionSkill
    # is NOT carried forward — it's trusted only on the line it actually
    # appears on, since Claude Code sets it natively per-message while active.
    current_marker_segment = None
    prev_attr_skill = None

    for line in open(path, errors="ignore"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if not isinstance(o, dict):
            continue
        if session_id is None:
            session_id = o.get("sessionId") or o.get("session_id")
        m = o.get("message")
        if isinstance(m, dict):
            role = m.get("role") or o.get("type") or ""
            _classify(role, m.get("content"), comp, tool_names)
            text = _extract_text(m.get("content"))
            cmd = _COMMAND_RE.search(text) if text else None
            current_skill_marker = cmd.group(1) if cmd else None
        else:
            current_skill_marker = None

        if current_skill_marker:
            current_marker_segment = current_skill_marker

        exact_skill = o.get("attributionSkill")
        attr_skill = exact_skill or current_marker_segment
        if attr_skill:
            if attr_skill != prev_attr_skill:
                skill_invocations[attr_skill] += 1
            if exact_skill:
                skill_exact.add(attr_skill)
        prev_attr_skill = attr_skill

        u = m.get("usage") if isinstance(m, dict) else None
        if not isinstance(u, dict):
            u = o.get("usage") if isinstance(o.get("usage"), dict) else None
        if not isinstance(u, dict):
            continue
        i = u.get("input_tokens", 0) or 0
        ot = u.get("output_tokens", 0) or 0
        cr = u.get("cache_read_input_tokens", 0) or 0
        cw = u.get("cache_creation_input_tokens", 0) or 0
        if not (i or ot or cr or cw):
            continue
        msgs += 1
        turns += 1
        _add(totals, i, ot, cr, cw)
        model = (m.get("model") if isinstance(m, dict) else None) or "unknown"
        _add(by_model[model], i, ot, cr, cw)
        day = (o.get("timestamp") or "")[:10] or "unknown"
        _add(by_day[day], i, ot, cr, cw)
        _add(by_day_model[day][model], i, ot, cr, cw)
        if first_fixed is None and (i + cr + cw) > 0:
            first_fixed = i + cr + cw
        if o.get("isSidechain"):
            _add(subagent_tokens, i, ot, cr, cw)
        else:
            _add(main_tokens, i, ot, cr, cw)
        if attr_skill:
            _add(by_skill[attr_skill], i, ot, cr, cw)

    return {
        "totals": totals,
        "by_day": dict(by_day),
        "by_model": dict(by_model),
        "by_day_model": {d: dict(models) for d, models in by_day_model.items()},
        "comp": {k: comp.get(k, 0) for k in COMP_CATS},
        "msgs": msgs,
        "turns": turns,
        "first_fixed": first_fixed or 0,
        "session_id": session_id,
        "main_tokens": main_tokens,
        "subagent_tokens": subagent_tokens,
        "by_skill": dict(by_skill),
        "skill_invocations": dict(skill_invocations),
        "skill_exact": sorted(skill_exact),
    }


def _load_cache_payload():
    global _MEM_PAYLOAD, _MEM_CACHE_KEY
    try:
        st = os.stat(CACHE_FILE)
        key = (CACHE_FILE, st.st_mtime, st.st_size)
        if _MEM_PAYLOAD is not None and _MEM_CACHE_KEY == key:
            return _MEM_PAYLOAD
    except OSError:
        key = (CACHE_FILE, None, None)
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            c = json.load(f)
        if not isinstance(c, dict):
            raise ValueError("cache root is not an object")
        if c.get("version") == CACHE_VERSION:
            _MEM_PAYLOAD, _MEM_CACHE_KEY = c, key
            return c
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"claude-code: ignoring unreadable cache {CACHE_FILE}: {exc}",
              file=sys.stderr)
    return {"version": CACHE_VERSION, "files": {}, "project_mtimes": {},
            "full_scan_at": 0}


def load_cache():
    return _load_cache_payload().get("files", {})


def save_cache(files, project_mtimes=None, full_scan_at=0):
    global _MEM_PAYLOAD, _MEM_CACHE_KEY
    payload = {"version": CACHE_VERSION, "files": files,
               "project_mtimes": project_mtimes or {},
               "full_scan_at": full_scan_at}
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(payload, f)
        st = os.stat(CACHE_FILE)
        _MEM_PAYLOAD = payload
        _MEM_CACHE_KEY = (CACHE_FILE, st.st_mtime, st.st_size)
    except Exception as e:
        print(f"warning: could not write claude_code cache: {e}", file=sys.stderr)


def scan(verbose=False, dir_index=None):
    """Glob + incrementally parse every Claude Code transcript. Returns a list of
    per-file summary dicts with mtime/size/project/projdir/tool added."""
    payload = _load_cache_payload()
    cache = payload.get("files", {})
    old_project_mtimes = payload.get("project_mtimes", {})
    last_full_scan = payload.get("full_scan_at", 0) or 0
    now = time.time()
    full_scan = not cache or now - last_full_scan >= FULL_SCAN_SECONDS
    paths = set() if full_scan else set(cache)
    cached_by_project = defaultdict(set)
    for cached_path in cache:
        cached_by_project[os.path.dirname(cached_path)].add(cached_path)
    project_mtimes = {}
    changed_projects = set()
    try:
        projects = [entry for entry in os.scandir(SOURCE_DIR) if entry.is_dir()]
    except OSError:
        projects = []
    for project in projects:
        try:
            mtime = project.stat().st_mtime
        except OSError:
            continue
        project_mtimes[project.path] = mtime
        if full_scan or old_project_mtimes.get(project.path) != mtime:
            changed_projects.add(project.path)
            current = set(glob.glob(os.path.join(project.path, "*.jsonl")))
            paths.difference_update(cached_by_project.get(project.path, ()))
            paths.update(current)
    new_cache = {}
    reparsed = 0
    labels_by_dir = {}
    cache_changed = set(cache) != paths
    hot_cutoff = now - HOT_FILE_SECONDS
    for p in sorted(paths):
        prev = cache.get(p)
        needs_stat = (full_scan or prev is None or os.path.dirname(p) in changed_projects
                      or prev.get("mtime", 0) >= hot_cutoff)
        if not needs_stat:
            new_cache[p] = prev
            continue
        try:
            st = os.stat(p)
        except OSError:
            cache_changed = True
            continue
        if prev and prev.get("mtime") == st.st_mtime and prev.get("size") == st.st_size:
            summary = prev
        else:
            summary = parse_file(p)
            summary["mtime"] = st.st_mtime
            summary["size"] = st.st_size
            reparsed += 1
            if verbose and reparsed % 200 == 0:
                print(f"  parsed {reparsed} new/changed claude transcripts...", file=sys.stderr)
        # Labels are derived on every scan so old cached summaries are corrected
        # when a formerly ambiguous transcript directory is resolved.
        projdir = os.path.basename(os.path.dirname(p))
        if projdir not in labels_by_dir:
            labels_by_dir[projdir] = project_label(p, dir_index=dir_index)
        summary["project"] = labels_by_dir[projdir]
        summary["projdir"] = projdir
        summary["tool"] = TOOL
        new_cache[p] = summary
    full_scan_at = now if full_scan else last_full_scan
    metadata_changed = project_mtimes != old_project_mtimes or full_scan
    if cache_changed or reparsed or metadata_changed:
        save_cache(new_cache, project_mtimes, full_scan_at)
    if verbose:
        mode = "full" if full_scan else "incremental"
        print(f"claude_code: scanned {len(paths)} transcripts ({reparsed} re-parsed, "
              f"{len(paths) - reparsed} cached; {mode})", file=sys.stderr)
    return list(new_cache.values())


def iter_dir_days(file_summaries):
    """Yield one Usage per (transcript dir, day) from already-parsed summaries."""
    for s in file_summaries:
        projdir = s.get("projdir") or ""
        for day, d in (s.get("by_day") or {}).items():
            yield Usage(projdir, day, d.get("input", 0), d.get("output", 0),
                        d.get("cache_read", 0), d.get("cache_write", 0), TOOL)
