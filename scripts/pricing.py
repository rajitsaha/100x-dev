#!/usr/bin/env python3
"""
pricing.py — per-model $/1M-token rates and cost calculation.

Shared by token-dashboard.py (dashboard cost) and run-cost.py (pair-loop budget
checks) so both price sessions identically. Rates are matched by substring against
a lowercased model id, first match wins in RATES order — list more specific
patterns before broader ones that could also match (e.g. "gpt-5" before a
hypothetical bare "gpt"). Model ids matching nothing are priced at FALLBACK_KEY's
rates and counted separately so callers can flag what fraction of spend is an
estimate rather than a real per-model price.

Values below are LIST PRICES AT TIME OF WRITING ($ per 1M tokens) — verify against
current published pricing before relying on them for real budgeting decisions.
"""

RATES = [
    ("fable-5", {"input": 25.0, "output": 100.0, "cache_read": 2.5, "cache_write": 31.25}),
    ("opus-4", {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75}),
    ("sonnet", {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75}),
    ("haiku", {"input": 1.0, "output": 5.0, "cache_read": 0.1, "cache_write": 1.25}),
    ("gpt-5", {"input": 1.25, "output": 10.0, "cache_read": 0.125, "cache_write": 1.25}),
    ("o4", {"input": 10.0, "output": 40.0, "cache_read": 2.5, "cache_write": 10.0}),
    ("o3", {"input": 10.0, "output": 40.0, "cache_read": 2.5, "cache_write": 10.0}),
    ("gpt-4.1", {"input": 2.0, "output": 8.0, "cache_read": 0.5, "cache_write": 2.0}),
]
FALLBACK_KEY = "opus-4"
_FALLBACK_RATES = next(r for k, r in RATES if k == FALLBACK_KEY)

TOKEN_KEYS = ("input", "output", "cache_read", "cache_write")


def rates_for_model(model_id):
    """Return (rates_dict, is_fallback) for a model id. Unknown ids fall back to
    FALLBACK_KEY's rates and are flagged so callers can surface the estimate."""
    mid = (model_id or "").lower()
    for pattern, rates in RATES:
        if pattern in mid:
            return rates, False
    return _FALLBACK_RATES, True


def cost_of(tokens, model_id=None):
    """tokens: {input,output,cache_read,cache_write} -> dollars for one model."""
    rates, _ = rates_for_model(model_id)
    return sum(tokens.get(k, 0) / 1_000_000 * rates[k] for k in TOKEN_KEYS)


def cost_by_model(by_model):
    """by_model: {model_id: {input,output,cache_read,cache_write}}.
    Returns (total_cost, fallback_priced_tokens) — the latter is the token count
    priced at fallback rates because the model id matched no known pattern."""
    total = 0.0
    fallback_tokens = 0
    for model_id, tok in by_model.items():
        rates, is_fallback = rates_for_model(model_id)
        total += sum(tok.get(k, 0) / 1_000_000 * rates[k] for k in TOKEN_KEYS)
        if is_fallback:
            fallback_tokens += sum(tok.get(k, 0) for k in TOKEN_KEYS)
    return total, fallback_tokens
