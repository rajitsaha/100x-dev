#!/usr/bin/env python3
"""
_budget.py — spend-vs-budget threshold checks and the daemon's alert dedupe.

Thresholds: WARN at 80% of a configured limit, ALERT at 100%. No configured
limit -> the feature is inert for that period (status_for returns (None, None)).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _config  # noqa: E402

HOME = os.path.expanduser("~")
ALERT_STATE_PATH = os.path.join(HOME, ".100xprism", "alert-state.json")
WARN_FRACTION = 0.8


def status_for(spend, limit):
    """(fraction, level) for one budget limit. level: None | 'warn' | 'alert'."""
    if not limit:
        return None, None
    frac = spend / limit
    if frac >= 1.0:
        return frac, "alert"
    if frac >= WARN_FRACTION:
        return frac, "warn"
    return frac, None


def budget_summary(today_spend, week_spend):
    cfg = _config.load_config()["budget"]
    daily, weekly = cfg.get("daily_usd"), cfg.get("weekly_usd")
    d_frac, d_level = status_for(today_spend, daily)
    w_frac, w_level = status_for(week_spend, weekly)
    return {
        "daily": {"limit": daily, "spend": round(today_spend, 2), "fraction": d_frac, "level": d_level},
        "weekly": {"limit": weekly, "spend": round(week_spend, 2), "fraction": w_frac, "level": w_level},
    }


def _load_alert_state():
    try:
        with open(ALERT_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_alert_state(state):
    try:
        os.makedirs(os.path.dirname(ALERT_STATE_PATH), exist_ok=True)
        tmp = ALERT_STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, ALERT_STATE_PATH)
    except OSError:
        pass


def _osascript_notify(message):
    import subprocess
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "100xPrism budget"'],
            capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass


def maybe_notify(summary, today_str, notifier=None):
    """Fire one notification per (period, level) per day. `notifier` is
    injectable for tests; defaults to an osascript display-notification call.
    Returns the list of threshold keys that fired."""
    if notifier is None:
        notifier = _osascript_notify
    state = _load_alert_state()
    fired = []
    for period in ("daily", "weekly"):
        block = summary[period]
        level = block["level"]
        if not level:
            continue
        key = f"{period}_{level}"
        if state.get(key) == today_str:
            continue
        pct = int(round((block["fraction"] or 0) * 100))
        msg = f"{period.title()} spend at {pct}% of ${block['limit']:.0f} budget (${block['spend']:.2f})"
        notifier(msg)
        state[key] = today_str
        fired.append(key)
    if fired:
        _save_alert_state(state)
    return fired


def oneline_suffix(summary):
    """`⚠`/`‼` glyph text appended to the --oneline shell summary."""
    parts = []
    for period, tag in (("daily", "today"), ("weekly", "7d")):
        block = summary[period]
        if block["limit"] is None:
            continue
        glyph = "‼" if block["level"] == "alert" else ("⚠" if block["level"] == "warn" else "")
        piece = f"{tag} ${block['spend']:.0f}/${block['limit']:.0f}"
        if glyph:
            piece += f" {glyph}"
        parts.append(piece)
    return " · ".join(parts)
