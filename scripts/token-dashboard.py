#!/usr/bin/env python3
"""
token-dashboard.py — local, offline token-usage dashboard for Claude Code.

Reads ~/.claude/projects/**/*.jsonl (the transcripts Claude Code writes), and
serves a small web UI that breaks usage down by the four token "purposes"
(input / output / cache-read / cache-write), by project, by day, and by model.
It also shows a "startup bloat" meter: the fixed context (system prompt + tool/
skill/agent descriptions + SessionStart injections) re-sent on every turn, and a
"content composition" ESTIMATE (code written / files read / logs / model prose /
prompts) derived char-by-char from the transcripts — see the caveat below.

Machine-global + singleton: it reads the global ~/.claude/projects dir, so ONE
instance covers every session and every repo/directory on the machine. An explicit
launch replaces a prior owned instance; --ensure-daemon keeps a healthy one running.

Composition caveat: the API bills tokens per TURN as aggregates, not per content
block — so the composition view is an *estimate* of where text volume goes
(chars ÷ 4), not billed truth. Treat it as directional.

No third-party dependencies. Fully offline (no CDN). Uses an on-disk cache
keyed by file path + mtime + size, so only new/changed transcripts are re-parsed.

Usage:
    python3 scripts/token-dashboard.py            # serve on http://127.0.0.1:8787
    python3 scripts/token-dashboard.py --port 9000
    python3 scripts/token-dashboard.py --print    # print a text summary, no server
    python3 scripts/token-dashboard.py --no-open  # don't auto-open the browser

Pricing for the cost estimate is per-model (see pricing.py's RATES table);
unmatched model ids fall back to Opus-tier rates and are flagged in fallback_pct.
"""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _value  # noqa: E402 — shared value layer (one source of truth)
import _summaries  # noqa: E402
import pricing  # noqa: E402
import adapters.claude_code as claude_code  # noqa: E402
import adapters.codex as codex  # noqa: E402
import adapters.cursor as cursor  # noqa: E402
import adapters.antigravity as antigravity  # noqa: E402
import run_manifest  # noqa: E402
import _budget  # noqa: E402
import _suggest  # noqa: E402

HOME = os.path.expanduser("~")
PROJECTS_DIR = claude_code.SOURCE_DIR
REFRESH_SECONDS = 30  # auto-rebuild cadence; mtime/size cache makes a no-op pass cheap
PID_FILE = os.path.join(HOME, ".100xprism", "token-dashboard.pid")


def _empty():
    return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}


def _add(dst, i, o, cr, cw):
    dst["input"] += i
    dst["output"] += o
    dst["cache_read"] += cr
    dst["cache_write"] += cw


COMP_CATS = claude_code.COMP_CATS
COMP_LABELS = claude_code.COMP_LABELS

project_label = _value.project_label


def build(verbose=True):
    """Scan every adapter (incremental via each adapter's own cache) and return
    the full dataset."""
    discovered, dir_index = _value.cached_scan()
    cc_summaries = claude_code.scan(verbose=verbose, dir_index=dir_index)
    cx_summaries = codex.scan(verbose=verbose)
    cursor_summaries = cursor.scan(verbose=verbose, dir_index=dir_index)
    antigravity_summaries = antigravity.scan(verbose=verbose)
    all_summaries = cc_summaries + cx_summaries + cursor_summaries + antigravity_summaries

    totals = _empty()
    by_project = defaultdict(_empty)
    by_day = defaultdict(_empty)
    by_project_day_model = defaultdict(lambda: defaultdict(lambda: defaultdict(_empty)))
    by_day_model_global = defaultdict(lambda: defaultdict(_empty))
    by_model = defaultdict(_empty)
    comp_chars = defaultdict(int)
    sessions = 0
    fixed_samples = []
    total_msgs = 0
    by_session = []
    by_skill_agg = defaultdict(lambda: {"cost": 0.0, "invocations": 0, "exact": False})
    main_cost_total = 0.0
    subagent_cost_total = 0.0

    for s in all_summaries:
        t = s["totals"]
        _add(totals, t["input"], t["output"], t["cache_read"], t["cache_write"])
        proj = s.get("project", "?")
        _add(by_project[proj], t["input"], t["output"], t["cache_read"], t["cache_write"])
        for day, d in s.get("by_day", {}).items():
            _add(by_day[day], d["input"], d["output"], d["cache_read"], d["cache_write"])
        for day, models in s.get("by_day_model", {}).items():
            for model, d in models.items():
                _add(by_project_day_model[proj][day][model], d["input"], d["output"], d["cache_read"], d["cache_write"])
                _add(by_day_model_global[day][model], d["input"], d["output"], d["cache_read"], d["cache_write"])
        for mdl, d in s.get("by_model", {}).items():
            _add(by_model[mdl], d["input"], d["output"], d["cache_read"], d["cache_write"])
        for cat, n in s.get("comp", {}).items():
            comp_chars[cat] += n
        if s.get("turns"):
            sessions += 1
            total_msgs += s.get("msgs", 0)
        if s.get("first_fixed"):
            fixed_samples.append(s["first_fixed"])

        file_cost, _ = pricing.cost_by_model(s.get("by_model", {}))
        total_file_tokens = sum(t.values())
        if s.get("session_id") and total_file_tokens:
            by_session.append({
                "session_id": s["session_id"], "project": proj, "tool": s.get("tool"),
                "cost": round(file_cost, 4), "msgs": s.get("msgs", 0), "mtime": s.get("mtime", 0),
                "models": sorted(s.get("by_model", {}).keys()),
                "model_costs": {model: round(pricing.cost_of(tok, model), 4)
                                for model, tok in s.get("by_model", {}).items()},
            })
        if total_file_tokens:
            main_frac = sum(s.get("main_tokens", _empty()).values()) / total_file_tokens
            sub_frac = sum(s.get("subagent_tokens", _empty()).values()) / total_file_tokens
            main_cost_total += file_cost * main_frac
            subagent_cost_total += file_cost * sub_frac
        for skill, tok in s.get("by_skill", {}).items():
            frac = sum(tok.values()) / total_file_tokens if total_file_tokens else 0
            entry = by_skill_agg[skill]
            entry["cost"] += file_cost * frac
            if skill in s.get("skill_exact", []):
                entry["exact"] = True
        for skill, n in s.get("skill_invocations", {}).items():
            by_skill_agg[skill]["invocations"] += n

    fixed_samples.sort()
    n = len(fixed_samples)
    median_fixed = fixed_samples[n // 2] if n else 0
    avg_fixed = sum(fixed_samples) / n if n else 0

    total_cost, fallback_tokens = pricing.cost_by_model(by_model)
    total_tokens = sum(totals.values())
    fallback_pct = round(100 * fallback_tokens / total_tokens, 1) if total_tokens else 0.0
    cost_by_purpose = {k: round(v, 4) for k, v in pricing.cost_breakdown(by_model).items()}

    by_day_model_cost = {
        day: {model: round(pricing.cost_of(tok, model), 4)
              for model, tok in models.items()}
        for day, models in by_day_model_global.items() if day != "unknown"
    }

    by_project_day_cost = {
        lbl: {day: round(pricing.cost_by_model(models)[0], 4) for day, models in days.items()}
        for lbl, days in by_project_day_model.items()
    }

    mangled_by_label, tokens_by_label, window_by_label, tool_by_label = {}, {}, {}, defaultdict(set)
    for s in all_summaries:
        label = s.get("project", "?")
        mangled = s.get("projdir", "")
        mangled_by_label.setdefault(mangled, label)
        tk = tokens_by_label.setdefault(label, _empty())
        t = s["totals"]
        _add(tk, t["input"], t["output"], t["cache_read"], t["cache_write"])
        tool_by_label[label].add(s.get("tool", "claude-code"))
        days = sorted(d for d in s.get("by_day", {}) if d != "unknown")
        activity_day = (s.get("activity") or {}).get("day")
        if activity_day:
            days.append(activity_day)
            days.sort()
        if days:
            lo, hi = window_by_label.get(label, (days[0], days[-1]))
            window_by_label[label] = (min(lo, days[0]), max(hi, days[-1]))
    tool_by_label = {lbl: "+".join(sorted(tools)) for lbl, tools in tool_by_label.items()}

    realdir_by_label = {}
    for real_dir, label in discovered.items():
        realdir_by_label.setdefault(label, real_dir)
    directories = assemble_directories(
        mangled_by_label, tokens_by_label, by_project_day_cost,
        window_by_label, tool_by_label,
        discovered=discovered, realdir_by_label=realdir_by_label,
        dir_index=dir_index)

    comp_tokens = {k: comp_chars.get(k, 0) // 4 for k in COMP_CATS}
    comp_sum = sum(comp_tokens.values()) or 1
    composition = sorted(
        ([COMP_LABELS[k], comp_tokens[k], round(100 * comp_tokens[k] / comp_sum, 1)]
         for k in COMP_CATS if comp_tokens[k]),
        key=lambda r: -r[1],
    )

    cutoff = time.time() - 30 * 86400
    by_session = sorted((s for s in by_session if s["mtime"] >= cutoff),
                         key=lambda r: -r["cost"])[:50]
    by_skill = sorted(
        ({"skill": k, "cost": round(v["cost"], 4), "invocations": v["invocations"],
          "exact": v["exact"]} for k, v in by_skill_agg.items()),
        key=lambda r: -r["cost"],
    )

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_cost = pricing.cost_by_model(by_day_model_global.get(today_str, {}))[0]
    week_start = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    week_cost = sum(
        pricing.cost_by_model(models)[0]
        for day, models in by_day_model_global.items() if day >= week_start
    )
    budget = _budget.budget_summary(today_cost, week_cost)

    month_start = (datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d")
    month_cost = sum(
        pricing.cost_by_model(models)[0]
        for day, models in by_day_model_global.items() if day >= month_start
    )

    dated_days = sorted(day for day in by_day_model_global if day != "unknown")
    source_counts = defaultdict(int)
    activity_sources = defaultdict(lambda: {"sessions": 0, "messages": 0,
                                             "artifacts": 0, "projects": set()})
    activity_sessions = []
    for s in all_summaries:
        if sum(s.get("totals", {}).values()):
            source_counts[s.get("tool", "unknown")] += 1
        if s.get("activity_only"):
            tool = s.get("tool", "unknown")
            activity = s.get("activity") or {}
            entry = activity_sources[tool]
            entry["sessions"] += 1
            entry["messages"] += activity.get("messages") or 0
            entry["artifacts"] += activity.get("artifacts") or 0
            entry["projects"].add(s.get("project", "unknown"))
            activity_sessions.append({
                "session_id": s.get("session_id"), "project": s.get("project"),
                "tool": tool, "day": activity.get("day"),
                "messages": activity.get("messages"),
                "artifacts": activity.get("artifacts"),
                "source": activity.get("source"),
            })
    activity_summary = {
        tool: {"sessions": value["sessions"], "messages": value["messages"],
               "artifacts": value["artifacts"], "projects": len(value["projects"])}
        for tool, value in sorted(activity_sources.items())
    }
    activity_sessions.sort(key=lambda r: r.get("day") or "", reverse=True)
    value_sources = defaultdict(int)
    matched_cost = 0.0
    outcome_totals = {"commits": 0, "prs": 0, "releases": 0}
    for row in directories:
        value = row.get("value") or {}
        value_sources[value.get("kind", "none")] += 1
        if row.get("cost") is not None and value.get("kind") == "git":
            matched_cost += row["cost"]
            for key in outcome_totals:
                outcome_totals[key] += len(value.get(key, [])) if key == "releases" else value.get(key, 0)
    outcome_coverage = round(100 * matched_cost / total_cost, 1) if total_cost else 0.0
    economics = {
        "matched_cost": round(matched_cost, 2),
        "cost_per_commit": round(matched_cost / outcome_totals["commits"], 2)
        if outcome_totals["commits"] else None,
        "cost_per_pr": round(matched_cost / outcome_totals["prs"], 2)
        if outcome_totals["prs"] else None,
        "cost_per_release": round(matched_cost / outcome_totals["releases"], 2)
        if outcome_totals["releases"] else None,
        **outcome_totals,
    }

    handoff_runs = _build_handoff_runs(all_summaries)

    dataset = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "transcripts": len(all_summaries),
        "sessions": sessions,
        "messages": total_msgs,
        "totals": totals,
        "total_cost": round(total_cost, 2),
        "cost_by_purpose": cost_by_purpose,
        "fallback_pct": fallback_pct,
        "pricing": {"as_of": pricing.PRICING_AS_OF, "sources": pricing.PRICING_SOURCES},
        "period_cost": {"today": round(today_cost, 2), "week": round(week_cost, 2),
                        "month": round(month_cost, 2), "lifetime": round(total_cost, 2)},
        "economics": economics,
        "data_quality": {
            "usage_sources": dict(sorted(source_counts.items())),
            "activity_sources": activity_summary,
            "value_sources": dict(sorted(value_sources.items())),
            "pricing_coverage_pct": round(100 - fallback_pct, 1),
            "outcome_cost_coverage_pct": outcome_coverage,
            "window": {"start": dated_days[0] if dated_days else None,
                       "end": dated_days[-1] if dated_days else None},
        },
        "bloat": {"median": int(median_fixed), "avg": int(avg_fixed), "samples": n},
        "composition": composition,
        "by_project": sorted(
            ([k, v, round(pricing.cost_of(v), 2)] for k, v in by_project.items()),
            key=lambda r: -(r[1]["input"] + r[1]["cache_read"] + r[1]["cache_write"]),
        )[:25],
        "by_day": sorted(([k, v] for k, v in by_day.items() if k != "unknown")),
        "by_day_model_cost": by_day_model_cost,
        "by_model": sorted(
            ([k, v] for k, v in by_model.items()),
            key=lambda r: -(r[1]["input"] + r[1]["cache_read"] + r[1]["cache_write"]),
        ),
        "by_project_day_cost": by_project_day_cost,
        "directories": directories,
        "by_session": by_session,
        "by_skill": by_skill,
        "main_subagent_split": {"main_cost": round(main_cost_total, 2),
                                 "subagent_cost": round(subagent_cost_total, 2)},
        "budget": budget,
        "handoff_runs": handoff_runs,
        "activity": {"by_tool": activity_summary,
                     "sessions": activity_sessions[:100],
                     "session_count": len(activity_sessions)},
    }
    dataset["suggestions"] = [
        {"impact_usd": round(s.impact_usd, 2), "title": s.title,
         "message": s.message, "action": s.action}
        for s in _suggest.suggestions(dataset)
    ]
    return dataset


def _build_handoff_runs(all_summaries):
    """Join every pair-loop run manifest to its round costs."""
    rows = []
    for path in run_manifest.list_manifests():
        try:
            manifest = run_manifest.load_manifest(path)
            cost = run_manifest.run_cost(manifest, all_summaries)
            reviewer_rounds = [r for r in manifest["rounds"] if r["role"] == "reviewer"]
            final_findings = reviewer_rounds[-1].get("findings") if reviewer_rounds else None
            rows.append({
                "run_id": manifest["run_id"], "task": manifest.get("task", ""),
                "rounds": manifest["outcome"].get("rounds", 0),
                "coder_cost": cost["coder"], "reviewer_cost": cost["reviewer"],
                "total_cost": cost["total"], "outcome": manifest["outcome"].get("verdict"),
                "pr": manifest.get("pr"), "merged": manifest["outcome"].get("merged"),
                "final_round_findings": final_findings,
            })
        except (OSError, ValueError, KeyError, AttributeError, TypeError):
            # A structurally-valid-JSON-but-schema-incomplete manifest (e.g.
            # missing "rounds"/"outcome", or a null "outcome" — `.get()` on
            # None raises AttributeError, not KeyError) must not take down
            # the whole dashboard build — skip just that one run.
            continue
    rows.sort(key=lambda r: -r["total_cost"])
    return rows


def fmt(n):
    n = float(n)
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(n) >= div:
            return f"{n / div:.1f}{unit}"
    return str(int(n))


def print_summary(data):
    t = data["totals"]
    print(f"\nToken usage (Claude Code + Codex) — {data['generated']}")
    print(f"{data['transcripts']} transcripts, {data['sessions']} sessions, "
          f"{fmt(data['messages'])} billed messages\n")
    print(f"  input (uncached) : {fmt(t['input']):>8}")
    print(f"  output           : {fmt(t['output']):>8}")
    print(f"  cache READ       : {fmt(t['cache_read']):>8}   (re-sent context — usually the largest)")
    print(f"  cache WRITE      : {fmt(t['cache_write']):>8}")
    print(f"  est. cost        : ${data['total_cost']:,}"
          + (f"  ({data['fallback_pct']}% priced at fallback rates)" if data['fallback_pct'] else ""))
    print(f"\n  startup bloat (fixed context re-sent each turn): "
          f"median {fmt(data['bloat']['median'])} / avg {fmt(data['bloat']['avg'])} tokens")
    if data.get("composition"):
        print("\n  Content composition (ESTIMATE — char-based, not billed tokens):")
        for label, toks, pct in data["composition"]:
            print(f"    {pct:>5.1f}%  {fmt(toks):>7}  {label}")
    print("\n  Top projects (by input volume):")
    for name, v, c in data["by_project"][:10]:
        tot = v["input"] + v["cache_read"] + v["cache_write"]
        print(f"    {fmt(tot):>8} in / {fmt(v['output']):>6} out  ${c:>8,.0f}  {name}")
    print()


# ---------------------------------------------------------------- value × cost

def assemble_directories(mangled_by_label, tokens_by_label, by_project_day_cost,
                         window_by_label, tool_by_label,
                         discovered=None, realdir_by_label=None, dir_index=None):
    """Build the unified per-directory rows (cost + tool-agnostic value)."""
    if discovered is None:
        discovered = {}
    if realdir_by_label is None:
        realdir_by_label = {}

    label_to_mangled = {}
    for mangled, label in mangled_by_label.items():
        label_to_mangled.setdefault(label, mangled)

    all_labels = set(mangled_by_label.values()) | set(discovered.values())

    rows = []
    value_store = _value.load_store()
    value_store_dirty = [False]
    for label in all_labels:
        mangled = label_to_mangled.get(label)
        real = realdir_by_label.get(label) \
               or (dir_index.get(mangled) if (dir_index and mangled) else None) \
               or (_value.resolve_real_dir(mangled) if mangled else None)
        start, end = window_by_label.get(label, (None, None))
        daycost = by_project_day_cost.get(label, {})
        _c = round(sum(daycost.values()), 2) if daycost else 0.0
        cost = _c if _c else None
        tool = tool_by_label.get(label)
        value = (_value.cached_dir_value(real, label, tool, start, end,
                                         store=value_store, dirty=value_store_dirty)
                 if real else _value._empty_value())
        if cost and value.get("commits"):
            value["cost_per_commit"] = round(cost / value["commits"], 2)
        if cost and value.get("prs"):
            value["cost_per_pr"] = round(cost / value["prs"], 2)
        rows.append({
            "dir": real, "label": label, "tool": tool,
            "cost": cost, "tokens": tokens_by_label.get(label, _empty()),
            "window": {"start": start, "end": end}, "value": value,
        })
    if value_store_dirty[0]:
        _value.save_store(value_store)
    rows.sort(key=lambda r: -(r["cost"] or 0))
    return rows


# ---------------------------------------------------------------- web UI

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>100xPrism — AI Economics</title>
<style>
:root{--ink:#0E1116;--surface:#171B22;--line:#262C36;--text:#E6E9EF;--muted:#8A93A2;
--cost:#E8B24A;--value:#5BD0A6;--warn:#E5704B;
--in:#58a6ff;--out:#f778ba;--cr:#3fb950;--cw:#d29922;
--m1:#58a6ff;--m2:#a371f7;--m3:#5BD0A6;--m4:#E8B24A;--m5:#f778ba;--m6:#8A93A2}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at 20% -10%,#18263a 0,transparent 34%),var(--ink);color:var(--text);
font:14px/1.55 'IBM Plex Sans',-apple-system,Segoe UI,Roboto,sans-serif}
.num,td.n,.money{font-family:'IBM Plex Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums}
header{padding:18px 28px;border-bottom:1px solid var(--line);display:flex;background:rgba(14,17,22,.88);
align-items:center;gap:16px;flex-wrap:wrap;position:sticky;top:0;z-index:10;backdrop-filter:blur(12px)}
h1{font-size:18px;margin:0}.sub{color:var(--muted);font-size:13px}
.wrap{padding:24px 28px 60px;max-width:1180px;margin:0 auto}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:24px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.card .lbl{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.card .val{font-size:26px;font-weight:600;margin-top:4px}
.card .note{color:var(--muted);font-size:12px;margin-top:6px}
.dot{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px;vertical-align:middle}
h2{font-size:14px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
margin:28px 0 12px;border-bottom:1px solid var(--line);padding-bottom:8px}
table{width:100%;border-collapse:collapse}
td,th{padding:7px 10px;text-align:right;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
th{color:var(--muted);font-weight:500;font-size:12px;text-transform:uppercase}
td:first-child,th:first-child{text-align:left}
.bar{height:9px;border-radius:5px;display:flex;overflow:hidden;background:#21262d;min-width:120px}
.bar span{display:block;height:100%}
.meter{background:#21262d;border-radius:6px;height:22px;position:relative;overflow:hidden;max-width:520px}
.meter b{position:absolute;left:0;top:0;bottom:0;border-radius:6px}
.meter em{position:absolute;left:10px;top:0;line-height:22px;font-style:normal;font-size:12px}
.legend{font-size:12px;color:var(--muted);margin:10px 0}.legend span{margin-right:16px}
button{background:var(--surface);color:var(--text);border:1px solid var(--line);border-radius:7px;
padding:6px 12px;cursor:pointer;font-size:13px}button:hover{border-color:var(--in)}
.muted{color:var(--muted)}
section{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
section h2{margin-top:0;border-bottom-color:var(--line)}
.cards2{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:8px 0 24px}
.wide{grid-column:1/-1}.table-wrap{overflow-x:auto}
.quality{display:flex;gap:10px 24px;flex-wrap:wrap;padding:12px 0 20px;color:var(--muted);font-size:12px}
.quality b{color:var(--text);font-weight:600}.rec{display:grid;grid-template-columns:auto 1fr;gap:5px 12px;padding:12px 0;border-bottom:1px solid var(--line)}
.rec:last-child{border-bottom:0}.rank{color:var(--cost);font:600 12px/1.4 'IBM Plex Mono',ui-monospace,monospace}.rec strong{font-size:14px}.action{color:var(--value);margin-top:3px}
@media(max-width:760px){.cards2{grid-template-columns:1fr}.wide{grid-column:auto}.wrap{padding:18px 14px 40px}header{padding:14px}.cards{grid-template-columns:1fr 1fr;gap:10px}.card .val{font-size:22px}td,th{padding:7px 8px}}
@media(max-width:430px){.cards{grid-template-columns:1fr}.sub{width:100%}}
.howto{margin:-4px 0 14px;font-size:13px;color:var(--muted)}
.howto summary{cursor:pointer;color:var(--text);user-select:none}
.howto ul{margin:10px 0 0;padding-left:18px;line-height:1.6}
.howto code{background:var(--surface);border:1px solid var(--line);border-radius:4px;padding:0 4px}
.badge{display:inline-block;font:600 10px/1 'IBM Plex Mono',ui-monospace,monospace;
padding:3px 5px;border:1px solid var(--line);border-radius:4px;color:var(--muted)}
#tip{position:fixed;z-index:1000;pointer-events:none;display:none;background:var(--surface);
border:1px solid var(--line);border-radius:6px;padding:6px 9px;font:12px/1.3 'IBM Plex Mono',ui-monospace,monospace;
color:var(--text);max-width:280px;box-shadow:0 4px 16px rgba(0,0,0,.5)}
</style></head><body>
<div id=tip role=tooltip></div>
<header><h1>100xPrism · AI Economics</h1>
<span class=sub id=meta></span>
<span style=margin-left:auto><button onclick=refresh()>↻ Rescan</button></span></header>
<div class=wrap id=app><p class=muted>Loading…</p></div>
<script>
const C={input:'var(--in)',output:'var(--out)',cache_read:'var(--cr)',cache_write:'var(--cw)'};
function fmt(n){n=+n;for(const[u,d]of[['B',1e9],['M',1e6],['K',1e3]])if(Math.abs(n)>=d)return(n/d).toFixed(1)+u;return''+Math.round(n);}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function bar(v){const tot=v.input+v.output+v.cache_read+v.cache_write||1;
 const seg=k=>`<span style="width:${100*v[k]/tot}%;background:${C[k]}"></span>`;
 return `<div class=bar>${seg('cache_read')}${seg('cache_write')}${seg('input')}${seg('output')}</div>`;}
function legend(){return `<div class=legend>
 <span><i class=dot style=background:var(--cr)></i>cache read</span>
 <span><i class=dot style=background:var(--cw)></i>cache write</span>
 <span><i class=dot style=background:var(--in)></i>input</span>
 <span><i class=dot style=background:var(--out)></i>output</span></div>`;}
function emptyState(msg){return `<p class=muted style="padding:24px 0">${esc(msg)}</p>`;}
function svgEl(w,h,inner,label){return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" role="img" aria-label="${esc(label)}" style="max-width:100%">${inner}</svg>`;}
function leverageChart(dirs){
 const unit=dirs.some(d=>d.cost!=null&&(d.value||{}).prs>0)?'merged PRs':'commits';
 const field=unit==='merged PRs'?'prs':'commits';
 const pts=dirs.filter(d=>d.cost!=null&&d.value&&(d.value[field]||0)>0)
   .map(d=>({x:d.cost,y:d.value[field],d}));
 if(!pts.length) return emptyState('No cost-bearing git outcomes yet.');
 const W=520,H=300,PL=50,PB=46,PR=36,PT=36;
 const mx=Math.max(...pts.map(p=>p.x),1), my=Math.max(...pts.map(p=>p.y),1);
 const X=x=>PL+(W-PL-PR)*x/mx, Y=y=>H-PB-(H-PB-PT)*y/my;
 const ratios=pts.map(p=>p.y/(p.x||1)).sort((a,b)=>a-b), r=ratios[ratios.length>>1]||1;
 const bline=`<line x1="${X(0)}" y1="${Y(0)}" x2="${X(mx)}" y2="${Y(Math.min(my,r*mx))}" stroke="var(--muted)" stroke-dasharray="4 4"/>`;
 const dots=pts.map(p=>{const above=p.y>=r*p.x; const col=above?'var(--value)':'var(--warn)';
   const tip=`${esc(p.d.label)} — $${p.x.toFixed(2)} · ${p.y} ${unit} · $${(p.x/p.y).toFixed(2)}/unit`;
   return `<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="5" fill="${col}" fill-opacity=".85" data-tip="${tip}" tabindex="0"/>`;}).join('');
 const ax=`<line x1="${PL}" y1="${H-PB}" x2="${W-PR}" y2="${H-PB}" stroke="var(--line)"/><line x1="${PL}" y1="${PT}" x2="${PL}" y2="${H-PB}" stroke="var(--line)"/>`;
 const tickAttrs='fill="var(--muted)" font-size="11"';
 const xTicks=`<text x="${PL}" y="${H-PB+14}" ${tickAttrs} text-anchor="middle">$0</text>`+
   `<text x="${W-PR}" y="${H-PB+14}" ${tickAttrs} text-anchor="middle">$${Math.round(mx)}</text>`;
 const yTicks=`<text x="${PL-6}" y="${H-PB}" ${tickAttrs} text-anchor="end" dominant-baseline="middle">0</text>`+
   `<text x="${PL-6}" y="${PT}" ${tickAttrs} text-anchor="end" dominant-baseline="middle">${Math.round(my)}</text>`;
 const xLabel=`<text x="${PL+(W-PL-PR)/2}" y="${H-2}" ${tickAttrs} text-anchor="middle">token cost ($) →</text>`;
 const yLabel=`<text x="${12}" y="${PT+(H-PB-PT)/2}" ${tickAttrs} text-anchor="middle" transform="rotate(-90,12,${PT+(H-PB-PT)/2})">↑ ${unit} shipped</text>`;
 return svgEl(W,H,ax+bline+dots+xTicks+yTicks+xLabel+yLabel,`${unit} shipped versus estimated token cost; dashed line is median observed outcomes per dollar, not break-even`);
}
function costOverTime(d){
 const bpd=d.by_project_day_cost||{}; const days=[...new Set(Object.values(bpd).flatMap(o=>Object.keys(o)))].sort();
 if(!days.length) return emptyState('No dated cost yet.');
 const labels=Object.keys(bpd); const W=520,H=200,PL=46,PB=30,PR=28,PT=28;
 const totalByDay=days.map(day=>labels.reduce((a,l)=>a+(bpd[l][day]||0),0));
 const maxC=Math.max(...totalByDay,1); const X=i=>PL+(W-PL-PR)*i/Math.max(days.length-1,1);
 const Y=v=>H-PB-(H-PB-PT)*v/maxC;
 const path=`M${days.map((day,i)=>`${X(i)},${Y(totalByDay[i])}`).join(' L')}`;
 const area=`${path} L${X(days.length-1)},${H-PB} L${X(0)},${H-PB} Z`;
 const tickAttrs='fill="var(--muted)" font-size="11"';
 const xLabels=`<text x="${PL}" y="${H-2}" ${tickAttrs} text-anchor="start">${esc(days[0].slice(5))}</text>`+
   (days.length>1?`<text x="${W-PR}" y="${H-2}" ${tickAttrs} text-anchor="end">${esc(days[days.length-1].slice(5))}</text>`:'');
 const yLabel=`<text x="${8}" y="${PT+(H-PB-PT)/2}" ${tickAttrs} text-anchor="middle" transform="rotate(-90,8,${PT+(H-PB-PT)/2})">$ / day</text>`;
 const yTick=`<text x="${PL-4}" y="${PT}" ${tickAttrs} text-anchor="end" dominant-baseline="middle">$${Math.round(maxC)}</text>`;
 const dots=days.map((day,i)=>`<circle cx="${X(i)}" cy="${Y(totalByDay[i])}" r="2.5" fill="var(--cost)" data-tip="$${Math.round(totalByDay[i])} on ${esc(day)}"/>`).join('');
 return svgEl(W,H,`<path d="${area}" fill="var(--cost)" fill-opacity=".18"/><path d="${path}" fill="none" stroke="var(--cost)" stroke-width="2"/>${dots}${xLabels}${yLabel}${yTick}`,
   'Daily token cost over time; x axis dates, y axis dollars per day');
}
function purposeSplit(t){
 if((t.cache_read+t.cache_write+t.input+t.output)===0) return emptyState('No token usage yet.');
 const parts=[['cache_read',t.cache_read,'var(--cr)'],['cache_write',t.cache_write,'var(--cw)'],
   ['input',t.input,'var(--in)'],['output',t.output,'var(--out)']];
 const sum=parts.reduce((a,p)=>a+p[1],0)||1; let x=0; const W=520,H=34;
 const segs=parts.map(([k,v,c])=>{const w=(W)*v/sum; const pct=Math.round(100*v/sum);
   const r=`<rect x="${x}" y="0" width="${w}" height="${H}" fill="${c}" data-tip="${esc(k)}: ${esc(fmt(v))} (${pct}%)"/>`; x+=w; return r;}).join('');
 return svgEl(W,H,segs,'Share of tokens by purpose: cache read, cache write, input, output');
}
function costByDir(dirs){
 const rows=dirs.filter(d=>d.cost!=null).slice(0,12); if(!rows.length) return emptyState('No cost yet.');
 const mx=Math.max(...rows.map(r=>r.cost),1); const H=rows.length*26+8,W=520;
 const bars=rows.map((r,i)=>{const w=(W-160)*r.cost/mx; const y=i*26+4;
   return `<text x="0" y="${y+14}" fill="var(--muted)" font-size="12">${esc(r.label.slice(-26))}</text>`+
     `<rect x="150" y="${y+3}" width="${w}" height="14" rx="3" fill="var(--cost)" data-tip="${esc(r.label)}: $${Math.round(r.cost)}" tabindex="0"/>`+
     `<text x="${156+w}" y="${y+14}" fill="var(--text)" font-size="11">$${Math.round(r.cost)}</text>`;}).join('');
 return svgEl(W,H,bars,'Estimated token cost by directory, highest first');
}
function donut(totals){
 const parts=[['cache_read',totals.cache_read,'var(--cr)'],['cache_write',totals.cache_write,'var(--cw)'],
   ['input',totals.input,'var(--in)'],['output',totals.output,'var(--out)']];
 const sum=parts.reduce((a,p)=>a+p[1],0); if(!sum) return emptyState('No token usage yet.');
 const W=180,H=180,cx=90,cy=90,r=70,rInner=42;
 const pt=(rad,a)=>[cx+rad*Math.cos(a),cy+rad*Math.sin(a)];
 const nonzero=parts.filter(p=>p[1]>0);
 let angle=-Math.PI/2, path='';
 if(nonzero.length===1){
  // A single 100%-share segment is a full circle: start===end for a lone SVG
  // arc command, which the spec treats as a zero-length (invisible) segment.
  // Split it into two half-circle arcs instead so the wedge actually renders.
  const[k,v,c]=nonzero[0];
  const a1=angle, aMid=angle+Math.PI, a2=angle+2*Math.PI;
  const[x1,y1]=pt(r,a1),[xm,ym]=pt(r,aMid),[x2,y2]=pt(r,a2);
  const[ix1,iy1]=pt(rInner,a1),[ixm,iym]=pt(rInner,aMid),[ix2,iy2]=pt(rInner,a2);
  path=`M${x1},${y1} A${r},${r} 0 1 1 ${xm},${ym} A${r},${r} 0 1 1 ${x2},${y2} `+
       `L${ix2},${iy2} A${rInner},${rInner} 0 1 0 ${ixm},${iym} A${rInner},${rInner} 0 1 0 ${ix1},${iy1} Z`;
  const center=`<text x="${cx}" y="${cy-2}" fill="var(--text)" text-anchor="middle" font-size="18">$${sum.toFixed(2)}</text><text x="${cx}" y="${cy+16}" fill="var(--muted)" text-anchor="middle" font-size="10">list-price spend</text>`;
  return svgEl(W,H,`<path d="${path}" fill="${c}" data-tip="${esc(k)}: $${v.toFixed(2)} (100%)"/>${center}`,
    'Estimated dollar spend share by token purpose');
 }
 for(const[k,v,c]of parts){ if(!v) continue;
   const frac=v/sum, a1=angle, a2=angle+frac*2*Math.PI; angle=a2;
   const[x1,y1]=pt(r,a1),[x2,y2]=pt(r,a2);
   const[ix1,iy1]=pt(rInner,a1),[ix2,iy2]=pt(rInner,a2);
   const large=frac>0.5?1:0;
   path+=`<path d="M${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} L${ix2},${iy2} A${rInner},${rInner} 0 ${large} 0 ${ix1},${iy1} Z" fill="${c}" data-tip="${esc(k)}: $${v.toFixed(2)} (${Math.round(100*frac)}%)"/>`;
 }
 path+=`<text x="${cx}" y="${cy-2}" fill="var(--text)" text-anchor="middle" font-size="18">$${sum.toFixed(2)}</text><text x="${cx}" y="${cy+16}" fill="var(--muted)" text-anchor="middle" font-size="10">list-price spend</text>`;
 return svgEl(W,H,path,'Estimated dollar spend share by token purpose');
}
function budgetBar(block,label){
 if(block.limit==null) return '';
 const pct=Math.min(100,(block.fraction||0)*100);
 const col=block.level==='alert'?'var(--warn)':block.level==='warn'?'var(--cw)':'var(--value)';
 return `<div style="margin:6px 0"><div class=muted style="font-size:11px;margin-bottom:2px">${esc(label)}: $${block.spend.toFixed(0)} / $${block.limit.toFixed(0)}</div>
   <div class=meter style="height:10px"><b style="width:${pct}%;background:${col}"></b></div></div>`;
}
function sessionsTable(rows){
 if(!rows.length) return emptyState('No sessions in the last 30 days.');
 let h='<table><tr><th>session</th><th>project</th><th>tool</th><th>msgs</th><th>cost</th></tr>';
 for(const r of rows.slice(0,20)){
  h+=`<tr><td class=muted>${esc(r.session_id.slice(0,8))}</td><td>${esc(r.project)}</td>`+
     `<td>${toolBadge(r.tool)}</td><td class=n>${r.msgs}</td><td class=money>$${r.cost.toFixed(2)}</td></tr>`;
 }
 return h+'</table>';
}
function skillsTable(rows){
 if(!rows.length) return emptyState('No skill attribution yet.');
 let h='<table><tr><th>skill</th><th>invocations</th><th>cost</th><th>$/invocation</th><th></th></tr>';
 for(const r of rows.slice(0,20)){
  const perInv=r.cost/(r.invocations||1);
  h+=`<tr><td>${esc(r.skill)}</td><td class=n>${r.invocations}</td><td class=money>$${r.cost.toFixed(2)}</td>`+
     `<td class=money>$${perInv.toFixed(3)}</td><td>${r.exact?'<span class=badge title="exact — from Claude Code\\'s native attribution">exact</span>':'<span class=badge title="attributed — heuristic segmentation">attr.</span>'}</td></tr>`;
 }
 return h+'</table>';
}
function handoffTable(rows){
 if(!rows.length) return '';
 let h='<h2>Pair-loop handoff runs</h2><table><tr><th>run</th><th>rounds</th><th>coder $</th><th>reviewer $</th><th>total $</th><th>outcome</th><th>PR</th></tr>';
 for(const r of rows){
  h+=`<tr><td class=muted>${esc(r.task||r.run_id)}</td><td class=n>${r.rounds}</td>`+
     `<td class=money>$${r.coder_cost.toFixed(2)}</td><td class=money>$${r.reviewer_cost.toFixed(2)}</td>`+
     `<td class=money>$${r.total_cost.toFixed(2)}</td><td>${esc(r.outcome||'—')}</td>`+
     `<td>${r.pr?('#'+r.pr):'—'}</td></tr>`;
 }
 return h+'</table>';
}
function suggestionsCard(rows){
 if(!rows.length) return '';
 let h='<section style="margin:24px 0"><h2>Recommended next actions <span class=muted style="text-transform:none;font-weight:400">— preserves agent autonomy</span></h2>';
 for(const s of rows){h+=`<div class=rec><div class=rank>~$${s.impact_usd.toFixed(2)}</div><div><strong>${esc(s.title)}</strong><div class=muted>${esc(s.message)}</div><div class=action>Do: ${esc(s.action)}</div></div></div>`;}
 return h+'</section>';
}
function stackedByModel(d){
 const raw=d.by_day_model_cost||{}, days=Object.keys(raw).sort().slice(-30); if(!days.length) return emptyState('No dated cost yet.');
 const modelTotals={}; for(const day of days)for(const[m,c]of Object.entries(raw[day]))modelTotals[m]=(modelTotals[m]||0)+c;
 const models=Object.keys(modelTotals).sort((a,b)=>modelTotals[b]-modelTotals[a]).slice(0,5), hasOther=Object.keys(modelTotals).length>5;
 const series=[...models,...(hasOther?['Other']:[])], colors=['var(--m1)','var(--m2)','var(--m3)','var(--m4)','var(--m5)','var(--m6)'];
 const values=days.map(day=>series.map(m=>m==='Other'?Object.entries(raw[day]).filter(([x])=>!models.includes(x)).reduce((a,[,v])=>a+v,0):(raw[day][m]||0)));
 const totals=values.map(v=>v.reduce((a,x)=>a+x,0)), max=Math.max(...totals,1), W=720,H=230,PL=48,PB=36,PR=18,PT=20;
 const slot=(W-PL-PR)/days.length,bw=Math.max(2,slot*.72),Y=v=>(H-PB-PT)*v/max; let bars='';
 values.forEach((vals,i)=>{let used=0; vals.forEach((v,j)=>{const h=Y(v),x=PL+i*slot+(slot-bw)/2,y=H-PB-used-h;bars+=`<rect x="${x}" y="${y}" width="${bw}" height="${Math.max(0,h)}" fill="${colors[j]}" data-tip="${esc(days[i])} · ${esc(series[j])}: $${v.toFixed(2)}" tabindex="0"/>`;used+=h;});});
 const ticks=`<text x="${PL}" y="${H-8}" fill="var(--muted)" font-size="11">${esc(days[0].slice(5))}</text><text x="${W-PR}" y="${H-8}" fill="var(--muted)" font-size="11" text-anchor="end">${esc(days[days.length-1].slice(5))}</text><text x="${PL-5}" y="${PT+3}" fill="var(--muted)" font-size="11" text-anchor="end">$${max.toFixed(0)}</text>`;
 const leg=series.map((m,i)=>`<span><i class=dot style="background:${colors[i]}"></i>${esc(m)}</span>`).join('');
 return svgEl(W,H,bars+ticks,'Daily estimated list-price cost stacked by model for the last 30 active days')+`<div class=legend>${leg}</div>`;
}
function toolBadge(t){const m={'claude-code':'CC','codex':'CX','cursor':'CU','antigravity':'AG'}; return `<span class=badge title="${esc(t||'unknown')}">${esc(m[t]||'?')}</span>`;}
function activityTable(activity){const rows=(activity||{}).sessions||[], byTool=(activity||{}).by_tool||{}; if(!rows.length)return '';
 const summary=Object.entries(byTool).map(([tool,v])=>`${tool}: ${v.sessions} sessions · ${v.projects} projects${v.messages?' · '+v.messages+' messages':''}${v.artifacts?' · '+v.artifacts+' artifacts':''}`).join(' | ');
 let h=`<section style="margin:24px 0"><h2>Activity coverage without token counters</h2><p class=muted>${esc(summary)}. These sources improve project/session coverage but never enter token cost.</p><div class=table-wrap><table><tr><th>date</th><th>tool</th><th>project</th><th>session</th><th>messages</th><th>artifacts</th></tr>`;
 for(const r of rows.slice(0,30)){h+=`<tr><td>${esc(r.day||'—')}</td><td>${toolBadge(r.tool)}</td><td>${esc(r.project||'unmapped')}</td><td class=muted>${esc((r.session_id||'').slice(0,8))}</td><td>${r.messages==null?'—':r.messages}</td><td>${r.artifacts==null?'—':r.artifacts}</td></tr>`;}
 return h+'</table></div></section>';}
function dirsTable(dirs){
 let h=`<h2>All directories <span class=muted style="text-transform:none;font-weight:400">— token economics × observable shipped outcomes</span></h2>`;
 h+=`<details class=howto><summary>How this is calculated</summary>
   <ul>
     <li><b style="color:var(--cost)">Cost</b> is computed from exact local token counters per model using standard API list prices. It is not a subscription invoice; unknown models are visibly marked through pricing coverage.</li>
     <li><b style="color:var(--value)">Outcomes</b> are observed over the same active-date window. Git repos use commits, deduplicated merged PRs, releases, and changed files. Non-repos use modified-file counts and are explicitly estimates.</li>
     <li><b>Coverage</b> includes Claude Code and Codex transcripts plus agentic directories discovered by marker files. A dash means no supported local token source, never zero spend.</li>
   </ul></details>`;
 h+=`<div class=table-wrap><table><tr><th>directory</th><th>tool</th><th>list-price $</th><th>observable outcomes</th><th>unit economics</th></tr>`;
 for(const d of dirs){
  const v=d.value||{}; const removed=!d.dir;
  const shipped = removed ? '<span class=muted>(removed)</span>'
    : v.kind==='git' ? esc(`${v.commits||0} commits${v.prs?'·'+v.prs+' PRs':''}`)
    : v.kind==='fs' ? esc(`${v.fs_files} files`) : '—';
  const lbl = removed
    ? `<span class=muted title="directory no longer on disk — value can't be computed">${esc(d.label)}</span>`
    : esc(d.label);
  h+=`<tr><td>${lbl}</td><td>${toolBadge(d.tool)}</td>`+
     `<td class=money>${d.cost==null?'<span class=muted>—</span>':'$'+Math.round(d.cost).toLocaleString()}</td>`+
     `<td style="color:var(--value)">${shipped}</td>`+
     `<td class=muted>${v.cost_per_pr!=null?'$'+v.cost_per_pr.toFixed(2)+'/PR':v.cost_per_commit!=null?'$'+v.cost_per_commit.toFixed(2)+'/commit':'—'}</td></tr>`;
 }
 return h+'</table></div>';
}
async function load(){render(await (await fetch('/api/data')).json());}
async function refresh(){document.getElementById('app').innerHTML='<p class=muted>Rescanning…</p>';render(await (await fetch('/api/refresh')).json());}
function money(c){return c==null?'<span class=muted>—</span>':'$'+(+c).toLocaleString(undefined,{maximumFractionDigits:0});}
function money2(c){return c==null?'<span class=muted>—</span>':'$'+(+c).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});}
function qualityStrip(d){const q=d.data_quality||{},u=q.usage_sources||{},a=q.activity_sources||{},v=q.value_sources||{},w=q.window||{};
 const activity=Object.entries(a).map(([k,x])=>`${esc(k)} ${x.sessions}`).join(' · ');
 return `<div class=quality aria-label="Data provenance"><span><b>${Object.entries(u).map(([k,n])=>`${esc(k)} ${n}`).join(' · ')||'No metered sources'}</b> records with provider token counters</span><span><b>${activity||'No activity-only sources'}</b> activity sessions without counters</span><span><b>${q.pricing_coverage_pct||0}%</b> tokens matched to a named price</span><span><b>${q.outcome_cost_coverage_pct||0}%</b> spend joined to git outcomes</span><span><b>${v.git||0} git · ${v.fs||0} filesystem</b> outcome sources</span><span>${w.start?`${esc(w.start)} → ${esc(w.end)}`:'No dated usage'}</span></div>`;}
function render(d){
 document.getElementById('meta').textContent=
  `${d.transcripts} source records · ${d.sessions} metered sessions · ${(d.activity||{}).session_count||0} activity-only · updated ${d.generated}`;
 const t=d.totals, p=d.period_cost||{}, e=d.economics||{};
 const card=(lbl,val,note,col)=>`<div class=card><div class=lbl>${col?`<i class=dot style=background:${col}></i>`:''}${lbl}</div>
   <div class=val>${val}</div><div class=note>${note||''}</div></div>`;
 const W=200000, mw=Math.min(100,100*d.bloat.median/W);
 let h=`<div class=cards>
   ${card('today',money2(p.today),'estimated list-price spend','var(--cost)')}
   ${card('last 7 days',money2(p.week),'estimated list-price spend','var(--cost)')}
   ${card('last 30 days',money2(p.month),'estimated list-price spend','var(--cost)')}
   ${card('$ / merged PR',money2(e.cost_per_pr),`${e.prs||0} observed PRs · matched spend only`,'var(--value)')}
   ${card('$ / commit',money2(e.cost_per_commit),`${e.commits||0} observed commits · not business ROI`,'var(--value)')}
  </div>${qualityStrip(d)}`;
 h+=`<div class=cards2>
   <section><h2>Outcome efficiency <span class=muted style="text-transform:none;font-weight:400">— no synthetic value score</span></h2>${leverageChart(d.directories||[])}</section>
   <section><h2>Cost by directory</h2>${costByDir(d.directories||[])}</section>
   <section class=wide><h2>Daily list-price cost by model</h2>${stackedByModel(d)}</section>
   <section><h2>Dollar spend by token purpose</h2>${donut(d.cost_by_purpose||{})}${legend()}</section>
   <section><h2>Token volume by purpose</h2>${purposeSplit(d.totals)}${legend()}</section>
 </div>`;
 h+=`<section style="margin-bottom:24px"><h2>Budget</h2>
   ${d.budget.daily.limit==null&&d.budget.weekly.limit==null
     ? '<p class=muted>No budget configured — add "budget" to ~/.100xprism/config.json.</p>'
     : budgetBar(d.budget.daily,'today')+budgetBar(d.budget.weekly,'last 7 days')}
   <p class=muted style="margin-top:8px">Pricing catalog checked ${esc((d.pricing||{}).as_of||'unknown')}. ${d.fallback_pct?`${d.fallback_pct}% of tokens use conservative fallback pricing.`:'All model tokens matched a named rate.'} Subscription plans and provider credits are not reconstructed.</p>
 </section>`;
 h+=handoffTable(d.handoff_runs||[]);
 h+=activityTable(d.activity);
 h+=`<h2>Sessions <span class=muted style="text-transform:none;font-weight:400">— top 50 by cost, last 30 days</span></h2>${sessionsTable(d.by_session||[])}`;
 h+=`<h2>By skill <span class=muted style="text-transform:none;font-weight:400">— "exact" from Claude Code's native attribution, "attr." from command-marker segmentation</span></h2>${skillsTable(d.by_skill||[])}`;
 h+=`<h2>Main vs subagent</h2><p>main $${(d.main_subagent_split.main_cost||0).toFixed(2)} · subagent $${(d.main_subagent_split.subagent_cost||0).toFixed(2)}</p>`;
 h+=suggestionsCard(d.suggestions||[]);
 h+=dirsTable(d.directories||[]);
 h+=`<h2>Startup bloat — fixed context re-sent every turn</h2>
   <div class=meter><b style="width:${mw}%;background:${mw>30?'var(--cw)':'var(--cr)'}"></b>
   <em>median ${fmt(d.bloat.median)} of 200K window (${(d.bloat.median/W*100).toFixed(1)}%)</em></div>
   <p class=muted style=margin-top:8px>avg ${fmt(d.bloat.avg)} · lower is better. This is system prompt + tool/skill/agent descriptions + SessionStart injections, read on every turn.</p>`;
 if(d.composition&&d.composition.length){
  const CC=['#58a6ff','#f778ba','#3fb950','#d29922','#a371f7','#ff7b72','#8b949e'];
  const ct=d.composition.reduce((a,r)=>a+r[1],0)||1;
  let segs='',rows='';
  d.composition.forEach((r,i)=>{const col=CC[i%CC.length];
   segs+=`<span style="width:${100*r[1]/ct}%;background:${col}"></span>`;
   rows+=`<tr><td><i class=dot style=background:${col}></i>${esc(r[0])}</td><td>${fmt(r[1])}</td><td>${r[2]}%</td></tr>`;});
  h+=`<h2>Content composition <span class=muted style="text-transform:none;font-weight:400">— estimate, char-based (not billed tokens)</span></h2>
   <div class=bar style="height:14px;margin-bottom:12px">${segs}</div>
   <table><tr><th>content type</th><th>est. tokens</th><th>share</th></tr>${rows}</table>
   <p class=muted style=margin-top:8px>The API bills per-turn aggregates, so this approximates where your conversation <em>text volume</em> goes (chars÷4): code written, files read, command output/logs, model prose, prompts. Directional, not exact.</p>`;
 }
 h+=`<h2>By model</h2><table><tr><th>model</th><th>mix</th><th>cache read</th><th>output</th></tr>`;
 for(const[name,v]of d.by_model){h+=`<tr><td>${esc(name)}</td><td>${bar(v)}</td>
   <td>${fmt(v.cache_read)}</td><td>${fmt(v.output)}</td></tr>`;}
 h+='</table>';
 const days=d.by_day.slice(-30);
 h+=`<h2>Last ${days.length} active days</h2><table><tr><th>day</th><th>mix</th><th>read</th><th>out</th></tr>`;
 for(const[day,v]of days.reverse()){h+=`<tr><td>${esc(day)}</td><td>${bar(v)}</td>
   <td>${fmt(v.cache_read)}</td><td>${fmt(v.output)}</td></tr>`;}
 h+='</table>';
 document.getElementById('app').innerHTML=h;
}
load();
setInterval(load, 30000);  // auto-refresh every 30s — matches the server's 30s rescan cadence
document.addEventListener('mousemove',e=>{const el=e.target.closest('[data-tip]');const tip=document.getElementById('tip');
  if(el){tip.textContent=el.getAttribute('data-tip');tip.style.display='block';
    let x=e.clientX+12,y=e.clientY+12;tip.style.left=Math.min(x,innerWidth-tip.offsetWidth-8)+'px';tip.style.top=y+'px';}
  else{tip.style.display='none';}});
document.addEventListener('focusin',e=>{const el=e.target.closest&&e.target.closest('[data-tip]');const tip=document.getElementById('tip');
  if(el){const r=el.getBoundingClientRect();tip.textContent=el.getAttribute('data-tip');tip.style.display='block';
    tip.style.left=r.left+'px';tip.style.top=(r.bottom+6)+'px';}});
document.addEventListener('focusout',()=>{document.getElementById('tip').style.display='none';});
</script></body></html>"""


_build_lock = threading.Lock()


def _rebuild():
    with _build_lock:
        Handler.data = build(verbose=False)
    threading.Thread(target=lambda: _summaries.backfill(), daemon=True).start()
    return Handler.data


def _client_data(data):
    """Token data for the browser. Trim per-day cost to the dirs we chart."""
    top = [d["label"] for d in data.get("directories", [])[:12]]
    bpd = {k: v for k, v in data.get("by_project_day_cost", {}).items() if k in top}
    out = {k: v for k, v in data.items() if k != "by_project_day_cost"}
    out["by_project_day_cost"] = bpd
    return out


class Handler(BaseHTTPRequestHandler):
    data = None

    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api/refresh"):
            self._send(json.dumps(_client_data(_rebuild())))
        elif self.path.startswith("/api/data"):
            if Handler.data is None:
                _rebuild()
            self._send(json.dumps(_client_data(Handler.data)))
        else:
            self._send(PAGE, "text/html; charset=utf-8")


def _token_summary() -> str | None:
    """Return a short cached-token summary string (+ budget glyph), or None."""
    cc_cache = claude_code.load_cache()
    cx_cache = codex.load_cache()
    if not cc_cache and not cx_cache:
        return None
    tot = _empty()
    today_str = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    today_by_model, week_models = defaultdict(_empty), defaultdict(_empty)
    for cache in (cc_cache, cx_cache):
        for s in cache.values():
            t = s.get("totals", {})
            _add(tot, t.get("input", 0), t.get("output", 0), t.get("cache_read", 0), t.get("cache_write", 0))
            for day, models in s.get("by_day_model", {}).items():
                for model, d in models.items():
                    if day == today_str:
                        _add(today_by_model[model], d["input"], d["output"], d["cache_read"], d["cache_write"])
                    if day >= week_start:
                        _add(week_models[model], d["input"], d["output"], d["cache_read"], d["cache_write"])
    if not any(tot.values()):
        return None
    by_model_total = _bucket_by_model(cc_cache, cx_cache)
    cost, _ = pricing.cost_by_model(by_model_total)
    today_cost, _ = pricing.cost_by_model(today_by_model)
    week_cost, _ = pricing.cost_by_model(week_models)
    budget = _budget.budget_summary(today_cost, week_cost)
    suffix = _budget.oneline_suffix(budget)
    line = f"{fmt(tot['output'])} out · {fmt(tot['cache_read'])} ctx · ~${cost:,.0f}"
    if suffix:
        line += f" · {suffix}"
    return line


def _bucket_by_model(cc_cache, cx_cache):
    agg = defaultdict(_empty)
    for cache in (cc_cache, cx_cache):
        for s in cache.values():
            for model, d in s.get("by_model", {}).items():
                _add(agg[model], d["input"], d["output"], d["cache_read"], d["cache_write"])
    return dict(agg)


def _oneline():
    """Fast cache-only summary line for shell startup. Silent if no cache yet."""
    s = _token_summary()
    if s:
        print(f"100xPrism tokens (as of last scan): {s} · run `100x-tokens` for the dashboard")


def _port_in_use(port):
    """True if something is already listening on 127.0.0.1:port (a running dash)."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def _command_for_pid(pid):
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="], capture_output=True,
            text=True, timeout=2, check=False)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _owned_dashboard_pids(port):
    """Return only processes that can be verified as this dashboard script."""
    candidates = set()
    try:
        with open(PID_FILE, encoding="utf-8") as f:
            record = json.load(f)
        if int(record.get("port", -1)) == port:
            candidates.add(int(record["pid"]))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        pass
    # Compatibility with dashboard processes started before the PID file existed.
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=2, check=False)
        candidates.update(int(line) for line in result.stdout.splitlines() if line.isdigit())
    except (OSError, subprocess.SubprocessError):
        pass
    script = os.path.realpath(__file__)
    owned = []
    for pid in candidates:
        if pid != os.getpid() and script in _command_for_pid(pid):
            owned.append(pid)
    return owned


def _stop_previous_dashboard(port, timeout=3.0):
    """Stop a prior owned UI/daemon, without touching an unrelated port owner."""
    stopped = []
    for pid in _owned_dashboard_pids(port):
        try:
            os.kill(pid, signal.SIGTERM)
            stopped.append(pid)
        except (OSError, ProcessLookupError):
            continue
    deadline = time.time() + timeout
    for pid in stopped:
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.05)
        else:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    try:
        os.remove(PID_FILE)
    except OSError:
        pass
    return stopped


def _write_pid(port):
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    tmp = PID_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "port": port,
                   "script": os.path.realpath(__file__)}, f)
    os.replace(tmp, PID_FILE)


def _remove_pid():
    try:
        with open(PID_FILE, encoding="utf-8") as f:
            record = json.load(f)
        if int(record.get("pid", -1)) == os.getpid():
            os.remove(PID_FILE)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass


def ensure_daemon(port: int) -> str | None:
    """
    Ensure the dashboard is running as a background daemon.
    Returns a one-line status string, or None if opt-out is set.
    Never raises.
    """
    try:
        if os.environ.get("PRISM_NO_DASHBOARD"):
            return None
        url = f"http://127.0.0.1:{port}"
        s = _token_summary()
        suffix = f"  · {s}" if s else ""
        if _port_in_use(port):
            return f"📊 token + value dashboard live → {url}{suffix}"
        # A recorded owned process that is no longer listening is stale/hung;
        # stop it before creating the replacement daemon.
        _stop_previous_dashboard(port)
        # Not running — spawn a detached background process
        logpath = os.path.join(HOME, ".claude", ".token-dashboard.log")
        log = open(logpath, "a")
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--no-open", "--port", str(port)],
            stdout=log, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True)
        log.close()
        return f"📊 token + value dashboard starting → {url}{suffix}  (first scan runs in the background)"
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--print", action="store_true", dest="text")
    ap.add_argument("--oneline", action="store_true",
                    help="one fast summary line from cache (no rescan) — for shell startup")
    ap.add_argument("--ensure-daemon", action="store_true",
                    help="ensure dashboard is running as a background daemon; print URL + status")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    if args.oneline:
        _oneline()
        return

    if args.ensure_daemon:
        line = ensure_daemon(args.port)
        if line:
            print(line)
        return

    if not os.path.isdir(PROJECTS_DIR):
        print(f"No transcripts found at {PROJECTS_DIR}", file=sys.stderr)
        sys.exit(1)

    url = f"http://127.0.0.1:{args.port}"

    # An explicit launch replaces an older owned UI/daemon. Shell-startup calls to
    # --ensure-daemon remain idempotent and do not churn a healthy server.
    if not args.text:
        stopped = _stop_previous_dashboard(args.port)
        if stopped:
            print(f"Stopped previous token dashboard ({', '.join(map(str, stopped))})")
        if _port_in_use(args.port):
            print(f"Port {args.port} is occupied by another service; not stopping it.",
                  file=sys.stderr)
            return

    print("Scanning transcripts (first run is slow; later runs use the cache)...", file=sys.stderr)
    data = build(verbose=True)

    if args.text:
        print_summary(data)
        return

    Handler.data = data
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError:
        # Lost a startup race with another session — point at the live one.
        print(f"Token dashboard already running → {url}  (covers all sessions/repos)")
        if not args.no_open:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return
    _write_pid(args.port)
    print(f"\nToken dashboard → {url}  (Ctrl-C to stop) — all sessions & repos on this machine")

    def _auto_refresh():
        while True:
            time.sleep(REFRESH_SECONDS)
            try:
                data = _rebuild()
                today_str = datetime.now().strftime("%Y-%m-%d")
                _budget.maybe_notify(data["budget"], today_str)
            except Exception:
                pass

    threading.Thread(target=_auto_refresh, daemon=True).start()

    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        srv.server_close()
        _remove_pid()


if __name__ == "__main__":
    main()
