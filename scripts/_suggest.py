#!/usr/bin/env python3
"""
_suggest.py — rule-based, offline cost-reduction suggestions.

Each rule is a pure function `data -> Suggestion|None` operating on the
token-dashboard.build() dataset. No LLM calls: every message is built from the
user's actual numbers already present in the dataset. Impact estimates are
rough proxies (documented per rule), not guarantees — they exist to RANK
suggestions, not to promise exact savings.
"""
from collections import namedtuple

Suggestion = namedtuple("Suggestion", "impact_usd title message action")


def _blended_rate(data):
    total_tokens = sum(data.get("totals", {}).values())
    return (data.get("total_cost", 0) / total_tokens) if total_tokens else 0.0


def _startup_bloat(data):
    bloat = data.get("bloat", {})
    median = bloat.get("median", 0)
    sessions = data.get("sessions", 0)
    if median <= 15000 or sessions == 0:
        return None
    rate = _blended_rate(data)
    impact = median * sessions * rate
    return Suggestion(
        impact, "Shrink fixed context",
        f"~{median // 1000}K fixed tokens load at session start; the observed-session "
        f"opportunity is ~${impact:,.0f} at the blended list-price rate.",
        "Keep AI-native workflows, but move rarely used instructions to on-demand skills "
        "and remove duplicate MCP/tool descriptions.")


def _model_tiering(data):
    premium_markers = ("fable", "opus", "gpt-5.5", "gpt-5.6")
    light_expensive = []
    for session in data.get("by_session", []):
        premium_cost = sum(
            cost for model, cost in session.get("model_costs", {}).items()
            if any(marker in model.lower() for marker in premium_markers)
        )
        if session.get("msgs", 0) < 5 and premium_cost > 0.50:
            light_expensive.append((session, premium_cost))
    if not light_expensive:
        return None
    impact = sum(cost for _, cost in light_expensive)
    return Suggestion(
        impact, "Route short tasks by difficulty",
        f"{len(light_expensive)} short sessions (<5 billed messages) used premium models "
        f"and cost ${impact:.2f}.",
        "Keep premium models for ambiguous or high-risk work; route deterministic edits, "
        "lookups, and formatting to a capable lower-cost model.")


def _cache_hygiene(data):
    t = data.get("totals", {})
    inp, cr = t.get("input", 0), t.get("cache_read", 0)
    if inp + cr == 0:
        return None
    share = cr / (inp + cr)
    if share >= 0.70:
        return None
    # Rough $/1K-token delta between the input rate and the cache-read rate
    # (~$13/1M is close to the Opus-tier gap in pricing.py) — not a per-model
    # exact figure, just a proxy to rank this suggestion against the others.
    impact = inp * 0.013 / 1000
    return Suggestion(
        impact, "Stabilize reusable context",
        f"Cache reads are {share*100:.0f}% of input volume; more uncached repetition costs "
        f"roughly ${impact:.2f} at the ranking proxy rate.",
        "Keep system instructions stable within a task and start a fresh session only at a "
        "real task boundary; this preserves tool use while improving cache reuse.")


def _read_delegation(data):
    comp = {row[0]: row[1] for row in data.get("composition", [])}
    total = sum(comp.values())
    if not total:
        return None
    files_read = comp.get("code / files read", 0)
    share = files_read / total
    if share <= 0.30:
        return None
    impact = files_read * 0.25 / 1_000_000 * 15.0  # assume 25% reducible, input-rate proxy
    return Suggestion(
        impact, "Narrow file retrieval",
        f"{share*100:.0f}% of estimated conversation text volume is raw file reads; a 25% "
        f"reduction ranks at ~${impact:.2f}.",
        "Use repository search and symbol/index lookups first, then read only relevant ranges. "
        "The agent remains autonomous without carrying entire files in context.")


def _skill_outlier(data):
    by_skill = data.get("by_skill", [])
    if len(by_skill) < 2:
        return None
    rates = [(s["skill"], s["cost"] / max(s["invocations"], 1)) for s in by_skill]
    rates.sort(key=lambda x: -x[1])
    top_skill, top_rate = rates[0]
    rest = sorted(c for _, c in rates[1:])
    median = rest[len(rest) // 2] if rest else 0
    if median == 0 or top_rate < 3 * median:
        return None
    n = next(s["invocations"] for s in by_skill if s["skill"] == top_skill)
    impact = (top_rate - median) * n
    return Suggestion(
        impact, "Right-size an expensive skill",
        f"'{top_skill}' costs ${top_rate:.2f}/invocation versus a ${median:.2f} peer median.",
        "Keep the skill, but move examples and reference material behind progressive, "
        "on-demand reads and tighten its default output contract.")


def _output_verbosity(data):
    spend = data.get("cost_by_purpose", {})
    total = sum(spend.values())
    output = spend.get("output", 0)
    if total == 0 or output / total < 0.50:
        return None
    # A conservative 20% verbosity reduction. This is a ranking estimate, not
    # a claim that reasoning or tool-use tokens can all be removed.
    impact = output * 0.20
    return Suggestion(
        impact, "Compress narration, not reasoning",
        f"Model output is {output / total * 100:.0f}% of estimated spend; a conservative "
        f"20% reduction ranks at ~${impact:.2f}.",
        "Keep planning, tool calls, tests, and self-checks; ask for terse progress updates, "
        "diff-first explanations, and one complete final handoff.")


def _loop_cap(data):
    runs = data.get("handoff_runs", [])
    zero_final = [r for r in runs if r.get("final_round_findings") == 0 and r.get("rounds", 0) >= 2]
    if len(zero_final) < 2:
        return None
    impact = sum(r.get("reviewer_cost", 0) for r in zero_final)
    return Suggestion(
        impact, "Stop review loops on convergence",
        f"{len(zero_final)} pair-loop runs ended with a zero-finding review round; those "
        f"reviewer rounds cost ${impact:.2f}.",
        "Retain independent AI review, but stop after an approval or a zero-finding round "
        "instead of spending a fixed maximum number of rounds.")


RULES = [_startup_bloat, _model_tiering, _cache_hygiene, _read_delegation,
         _skill_outlier, _output_verbosity, _loop_cap]


def suggestions(data, limit=5):
    out = []
    for rule in RULES:
        s = rule(data)
        if s and s.impact_usd > 0:
            out.append(s)
    out.sort(key=lambda s: -s.impact_usd)
    return out[:limit]
