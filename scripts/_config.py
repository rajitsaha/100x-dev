#!/usr/bin/env python3
"""
_config.py — shared ~/.100xprism/config.json loader with schema defaults.

Single source of truth for user-editable settings: budget limits (consumed by
_budget.py / token-dashboard.py) and pair-loop roles (consumed by pair-loop.py).
The file is entirely optional — every key has a default, and a missing or
malformed file silently falls back to DEFAULTS rather than raising.
"""
import json
import os

HOME = os.path.expanduser("~")
CONFIG_PATH = os.path.join(HOME, ".100xprism", "config.json")

DEFAULTS = {
    "budget": {"daily_usd": None, "weekly_usd": None, "per_run_usd": None},
    "pair_loop": {"coder": "claude", "reviewer": "codex", "max_rounds": 3,
                  "pr_final_round": False},
    "github": {
        "enabled": False,
        "users": [],
        "repos": [],
        "max_repos": 12,
        "max_prs_per_repo": 30,
        "max_pr_file_fetches_per_repo": 3,
        "max_user_repos_per_user": 20,
    },
}


def load_config():
    """Return the on-disk config deep-merged (per top-level section) over
    DEFAULTS. Missing file, unreadable file, or malformed JSON -> DEFAULTS."""
    cfg = {section: dict(values) for section, values in DEFAULTS.items()}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            user = json.load(f)
    except (OSError, ValueError):
        return cfg
    if not isinstance(user, dict):
        return cfg
    for section, values in user.items():
        if section in cfg:
            if isinstance(values, dict):
                cfg[section].update(values)
            # else: known section with a non-dict value (e.g. `"budget": null`)
            # -> keep the default dict, consistent with "malformed input never
            # raises" for the whole-file case.
        else:
            cfg[section] = values
    return cfg
