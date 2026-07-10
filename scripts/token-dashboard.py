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
instance covers every session and every repo/directory on the machine. Launching
it again (from any repo, any session) just opens the already-running URL.

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
import socket
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
import run_manifest  # noqa: E402
import _budget  # noqa: E402
import _suggest  # noqa: E402

HOME = os.path.expanduser("~")
PROJECTS_DIR = claude_code.SOURCE_DIR
REFRESH_SECONDS = 30  # auto-rebuild cadence; mtime/size cache makes a no-op pass cheap


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
    cc_summaries = claude_code.scan(verbose=verbose)
    cx_summaries = codex.scan(verbose=verbose)
    all_summaries = cc_summaries + cx_summaries

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
        if s.get("session_id"):
            by_session.append({
                "session_id": s["session_id"], "project": proj, "tool": s.get("tool"),
                "cost": round(file_cost, 4), "msgs": s.get("msgs", 0), "mtime": s.get("mtime", 0),
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
        if days:
            lo, hi = window_by_label.get(label, (days[0], days[-1]))
            window_by_label[label] = (min(lo, days[0]), max(hi, days[-1]))
    tool_by_label = {lbl: "+".join(sorted(tools)) for lbl, tools in tool_by_label.items()}

    discovered, dir_index = _value.cached_scan()
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

    handoff_runs = _build_handoff_runs(all_summaries)

    dataset = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "transcripts": len(all_summaries),
        "sessions": sessions,
        "messages": total_msgs,
        "totals": totals,
        "total_cost": round(total_cost, 2),
        "fallback_pct": fallback_pct,
        "bloat": {"median": int(median_fixed), "avg": int(avg_fixed), "samples": n},
        "composition": composition,
        "by_project": sorted(
            ([k, v, round(pricing.cost_of(v), 2)] for k, v in by_project.items()),
            key=lambda r: -(r[1]["input"] + r[1]["cache_read"] + r[1]["cache_write"]),
        )[:25],
        "by_day": sorted(([k, v] for k, v in by_day.items() if k != "unknown")),
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
    }
    dataset["suggestions"] = [
        {"impact_usd": round(s.impact_usd, 2), "message": s.message}
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
        value = (_value.cached_dir_value(real, label, tool, start, end)
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
    rows.sort(key=lambda r: -(r["cost"] or 0))
    return rows


# ---------------------------------------------------------------- web UI

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>Claude Code — Token Usage</title>
<style>
:root{--ink:#0E1116;--surface:#171B22;--line:#262C36;--text:#E6E9EF;--muted:#8A93A2;
--cost:#E8B24A;--value:#5BD0A6;--warn:#E5704B;
--in:#58a6ff;--out:#f778ba;--cr:#3fb950;--cw:#d29922}
*{box-sizing:border-box}
body{margin:0;background:var(--ink);color:var(--text);
font:14px/1.55 'IBM Plex Sans',-apple-system,Segoe UI,Roboto,sans-serif}
.num,td.n,.money{font-family:'IBM Plex Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums}
header{padding:20px 28px;border-bottom:1px solid var(--line);display:flex;
align-items:baseline;gap:16px;flex-wrap:wrap}
h1{font-size:18px;margin:0}.sub{color:var(--muted);font-size:13px}
.wrap{padding:24px 28px;max-width:1100px;margin:0 auto}
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
@media(max-width:760px){.cards2{grid-template-columns:1fr}}
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
<header><h1>Claude Code · Token Usage</h1>
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
 const pts=dirs.filter(d=>d.cost!=null&&d.value).map(d=>({x:d.cost,
   y:(d.value.commits||0)+3*(d.value.prs||0)+(d.value.fs_files||0?1:0), d}));
 if(!pts.length) return emptyState('No cost-bearing directories yet.');
 const W=520,H=300,PL=50,PB=46,PR=36,PT=36;
 const mx=Math.max(...pts.map(p=>p.x),1), my=Math.max(...pts.map(p=>p.y),1);
 const X=x=>PL+(W-PL-PR)*x/mx, Y=y=>H-PB-(H-PB-PT)*y/my;
 const ratios=pts.map(p=>p.y/(p.x||1)).sort((a,b)=>a-b), r=ratios[ratios.length>>1]||1;
 const bline=`<line x1="${X(0)}" y1="${Y(0)}" x2="${X(mx)}" y2="${Y(r*mx)}" stroke="var(--muted)" stroke-dasharray="4 4"/>`;
 const dots=pts.map(p=>{const above=p.y>=r*p.x; const col=above?'var(--value)':'var(--warn)';
   const tip=`${esc(p.d.label)} — $${Math.round(p.x)} · ${p.d.value.commits||0} commits · ${p.d.value.prs||0} PRs`;
   return `<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="5" fill="${col}" fill-opacity=".85" data-tip="${tip}" tabindex="0"/>`;}).join('');
 const ax=`<line x1="${PL}" y1="${H-PB}" x2="${W-PR}" y2="${H-PB}" stroke="var(--line)"/><line x1="${PL}" y1="${PT}" x2="${PL}" y2="${H-PB}" stroke="var(--line)"/>`;
 const tickAttrs='fill="var(--muted)" font-size="11"';
 const xTicks=`<text x="${PL}" y="${H-PB+14}" ${tickAttrs} text-anchor="middle">$0</text>`+
   `<text x="${W-PR}" y="${H-PB+14}" ${tickAttrs} text-anchor="middle">$${Math.round(mx)}</text>`;
 const yTicks=`<text x="${PL-6}" y="${H-PB}" ${tickAttrs} text-anchor="end" dominant-baseline="middle">0</text>`+
   `<text x="${PL-6}" y="${PT}" ${tickAttrs} text-anchor="end" dominant-baseline="middle">${Math.round(my)}</text>`;
 const xLabel=`<text x="${PL+(W-PL-PR)/2}" y="${H-2}" ${tickAttrs} text-anchor="middle">token cost ($) →</text>`;
 const yLabel=`<text x="${12}" y="${PT+(H-PB-PT)/2}" ${tickAttrs} text-anchor="middle" transform="rotate(-90,12,${PT+(H-PB-PT)/2})">↑ value shipped (commits + PRs)</text>`;
 return svgEl(W,H,ax+bline+dots+xTicks+yTicks+xLabel+yLabel,'Value shipped (y, commits+PRs) versus token cost (x, dollars); dots above the dashed break-even line ship more per token');
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
  return svgEl(W,H,`<path d="${path}" fill="${c}" data-tip="${esc(k)}: ${esc(fmt(v))} (100%)"/>`,
    'Donut chart: share of tokens by purpose');
 }
 for(const[k,v,c]of parts){ if(!v) continue;
   const frac=v/sum, a1=angle, a2=angle+frac*2*Math.PI; angle=a2;
   const[x1,y1]=pt(r,a1),[x2,y2]=pt(r,a2);
   const[ix1,iy1]=pt(rInner,a1),[ix2,iy2]=pt(rInner,a2);
   const large=frac>0.5?1:0;
   path+=`<path d="M${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} L${ix2},${iy2} A${rInner},${rInner} 0 ${large} 0 ${ix1},${iy1} Z" fill="${c}" data-tip="${esc(k)}: ${esc(fmt(v))} (${Math.round(100*frac)}%)"/>`;
 }
 return svgEl(W,H,path,'Donut chart: share of tokens by purpose');
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
 let h='<h2>Suggestions <span class=muted style="text-transform:none;font-weight:400">— ranked by estimated $ impact</span></h2><ul style="padding-left:18px;line-height:1.8">';
 for(const s of rows){ h+=`<li>${esc(s.message)} <span class=muted>(~$${s.impact_usd.toFixed(2)})</span></li>`; }
 return h+'</ul>';
}
function stackedByModel(d){
 const days=d.by_day.map(r=>r[0]); if(!days.length) return emptyState('No dated cost yet.');
 const W=520,H=200,PL=46,PB=30,PR=28,PT=20;
 // Per-day-per-model split isn't shipped to the client to keep payload small
 // (the by_model legend still reflects exact totals) — this chart shows the
 // RELATIVE daily shape of total token volume as a proxy for daily cost.
 const totalByDay=d.by_day.map(r=>r[1].input+r[1].output+r[1].cache_read+r[1].cache_write);
 const maxT=Math.max(...totalByDay,1); const X=i=>PL+(W-PL-PR)*i/Math.max(days.length-1,1);
 const Y=v=>H-PB-(H-PB-PT)*v/maxT;
 const path=`M${days.map((day,i)=>`${X(i)},${Y(totalByDay[i])}`).join(' L')}`;
 const area=`${path} L${X(days.length-1)},${H-PB} L${X(0)},${H-PB} Z`;
 const tickAttrs='fill="var(--muted)" font-size="11"';
 const xLabels=`<text x="${PL}" y="${H-2}" ${tickAttrs}>${esc(days[0].slice(5))}</text>`+
   (days.length>1?`<text x="${W-PR}" y="${H-2}" ${tickAttrs} text-anchor="end">${esc(days[days.length-1].slice(5))}</text>`:'');
 return svgEl(W,H,`<path d="${area}" fill="var(--cost)" fill-opacity=".18"/><path d="${path}" fill="none" stroke="var(--cost)" stroke-width="2"/>${xLabels}`,
   'Daily total token volume over time (shape proxy for cost)');
}
function toolBadge(t){const m={'claude-code':'CC','codex':'CX'}; return `<span class=badge title="${esc(t||'unknown')}">${esc(m[t]||'?')}</span>`;}
function dirsTable(dirs){
 let h=`<h2>All directories <span class=muted style="text-transform:none;font-weight:400">— cost (amber) × value shipped (green); — = no local token data for that tool</span></h2>`;
 h+=`<details class=howto><summary>How this is calculated</summary>
   <ul>
     <li><b style="color:var(--cost)">Cost</b> — each directory's token spend over its <em>active days</em>, priced at editable list rates (output $75/M, input $15/M, cache-write $18.75/M, cache-read $1.5/M). Directional, not your actual bill. Only Claude Code records local token data, so other tools show <span class=muted>—</span>.</li>
     <li><b style="color:var(--value)">Value</b> — tool-agnostic, over the same date window. Git repos: commits, merged PRs (counted from <code>(#n)</code> in commit subjects), files changed, lines added/removed. Non-repos: count of files modified (an estimate). The <em>AI note</em> is a one-line summary from your local <code>claude</code> CLI.</li>
     <li><b>Which directories</b> — every dir that spent Claude tokens, <em>plus</em> a machine-wide scan for agent files (CLAUDE.md, AGENTS.md, GEMINI.md, .cursorrules, …), so projects built with any tool — or no tokens at all — still appear.</li>
   </ul></details>`;
 h+=`<table><tr><th>directory</th><th>tool</th><th>est $</th><th>value (shipped)</th><th>AI note</th></tr>`;
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
     `<td class=muted>${v.summary?esc(v.summary):'<span class=muted>—</span>'}</td></tr>`;
 }
 return h+'</table>';
}
async function load(){render(await (await fetch('/api/data')).json());}
async function refresh(){document.getElementById('app').innerHTML='<p class=muted>Rescanning…</p>';render(await (await fetch('/api/refresh')).json());}
function money(c){return c==null?'<span class=muted>—</span>':'$'+(+c).toLocaleString(undefined,{maximumFractionDigits:0});}
function render(d){
 document.getElementById('meta').textContent=
  `${d.transcripts} transcripts · ${d.sessions} sessions · updated ${d.generated}`;
 const t=d.totals, max=Math.max(...d.bloat.window?[]:[1]);
 const card=(lbl,val,note,col)=>`<div class=card><div class=lbl>${col?`<i class=dot style=background:${col}></i>`:''}${lbl}</div>
   <div class=val>${val}</div><div class=note>${note||''}</div></div>`;
 const W=200000, mw=Math.min(100,100*d.bloat.median/W);
 let h=`<div class=cards>
   ${card('cache read',fmt(t.cache_read),'re-sent context (cheap/token, huge volume)','var(--cr)')}
   ${card('output',fmt(t.output),'model generations — costliest per token','var(--out)')}
   ${card('cache write',fmt(t.cache_write),'context written on a miss','var(--cw)')}
   ${card('input',fmt(t.input),'new uncached text','var(--in)')}
   ${card('est. cost','$'+d.total_cost.toLocaleString(),'rough, list rates (editable)')}
  </div>`;
 h+=`<div class=cards2>
   <section><h2>Leverage — value vs cost</h2>${leverageChart(d.directories||[])}</section>
   <section><h2>Cost over time</h2>${costOverTime(d)}</section>
   <section><h2>Token-purpose split</h2>${purposeSplit(d.totals)}${legend()}</section>
   <section><h2>Cost by directory</h2>${costByDir(d.directories||[])}</section>
 </div>`;
 h+=`<section style="margin-bottom:24px"><h2>Budget</h2>
   ${d.budget.daily.limit==null&&d.budget.weekly.limit==null
     ? '<p class=muted>No budget configured — add "budget" to ~/.100xprism/config.json.</p>'
     : budgetBar(d.budget.daily,'today')+budgetBar(d.budget.weekly,'last 7 days')}
   ${d.fallback_pct?`<p class=muted style="margin-top:8px">${d.fallback_pct}% of spend priced at fallback (unrecognized model) rates.</p>`:''}
 </section>`;
 h+=`<div class=cards2>
   <section><h2>Spend by purpose</h2>${donut(t)}${legend()}</section>
   <section><h2>Daily volume</h2>${stackedByModel(d)}</section>
 </div>`;
 h+=handoffTable(d.handoff_runs||[]);
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
        # Not running — spawn a detached background process
        import subprocess
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

    # Singleton: one dashboard serves EVERY session/repo on this machine (it reads
    # the global ~/.claude/projects). If one is already up, just open that URL.
    if not args.text and _port_in_use(args.port):
        print(f"Token dashboard already running → {url}  (covers all sessions/repos)")
        if not args.no_open:
            try:
                webbrowser.open(url)
            except Exception:
                pass
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


if __name__ == "__main__":
    main()
