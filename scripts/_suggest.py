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

Suggestion = namedtuple("Suggestion", "impact_usd message")


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
    return Suggestion(impact, f"Each session starts with ~{median // 1000}K tokens of fixed "
                       f"context (~${impact:,.0f} across your last {sessions} sessions) — "
                       f"trim CLAUDE.md / skill descriptions.")


def _model_tiering(data):
    light_expensive = [s for s in data.get("by_session", [])
                        if s.get("msgs", 0) < 5 and s.get("tool") == "claude-code"
                        and s.get("cost", 0) > 0.50]
    if not light_expensive:
        return None
    impact = sum(s["cost"] for s in light_expensive)
    return Suggestion(impact, f"{len(light_expensive)} short sessions (<5 messages) cost "
                       f"${impact:.2f} on premium-tier models — re-tier quick/simple "
                       f"sessions to Sonnet or Haiku.")


def _cache_hygiene(data):
    t = data.get("totals", {})
    inp, cr = t.get("input", 0), t.get("cache_read", 0)
    if inp + cr == 0:
        return None
    share = cr / (inp + cr)
    if share >= 0.50:
        return None
    # Rough $/1K-token delta between the input rate and the cache-read rate
    # (~$13/1M is close to the Opus-tier gap in pricing.py) — not a per-model
    # exact figure, just a proxy to rank this suggestion against the others.
    impact = inp * 0.013 / 1000
    return Suggestion(impact, f"Cache reads are only {share*100:.0f}% of input volume — "
                       f"longer-lived sessions and stable system prompts raise this and "
                       f"cut cost per turn.")


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
    return Suggestion(impact, f"{share*100:.0f}% of token volume is raw file reads — "
                       f"delegate broad searches to Explore subagents instead of reading "
                       f"whole files inline.")


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
    return Suggestion(impact, f"'{top_skill}' costs ${top_rate:.2f}/invocation vs "
                       f"${median:.2f} median — inspect its prompt size.")


def _loop_cap(data):
    runs = data.get("handoff_runs", [])
    zero_final = [r for r in runs if r.get("final_round_findings") == 0 and r.get("rounds", 0) >= 2]
    if len(zero_final) < 2:
        return None
    impact = sum(r.get("reviewer_cost", 0) for r in zero_final)
    return Suggestion(impact, f"{len(zero_final)} pair-loop runs converged with a final "
                       f"round that found nothing — lower the round cap.")


RULES = [_startup_bloat, _model_tiering, _cache_hygiene, _read_delegation,
         _skill_outlier, _loop_cap]


def suggestions(data, limit=5):
    out = []
    for rule in RULES:
        s = rule(data)
        if s and s.impact_usd > 0:
            out.append(s)
    out.sort(key=lambda s: -s.impact_usd)
    return out[:limit]
