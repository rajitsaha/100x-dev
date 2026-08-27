#!/usr/bin/env python3
"""
_config.py — shared ~/.100xprism/config.json loader with schema defaults.

Single source of truth for user-editable settings: budget limits (consumed by
_budget.py / token-dashboard.py) and pair-loop roles (consumed by pair-loop.py).
The file is entirely optional — every key has a default, and a missing or
malformed file silently falls back to DEFAULTS rather than raising.
"""
import copy
import json
import os

HOME = os.path.expanduser("~")
CONFIG_PATH = os.path.join(HOME, ".100xprism", "config.json")

DEFAULTS = {
    "budget": {"daily_usd": None, "weekly_usd": None, "per_run_usd": None},
    # fallback_models: the model the reviewer runs when the configured CLI is
    # missing and we fall back to another vendor — often the coder's own.
    # Pinning a model here *reduces* the chance the reviewer runs the coder's
    # own model, which would make the review a self-review. It does not
    # guarantee it: nothing compares this value to the coder's model, so pick
    # one you don't code with. `sonnet` is a CLI alias that resolves to the
    # current latest Sonnet, so it doesn't go stale on release.
    "pair_loop": {"coder": "claude", "reviewer": "codex", "max_rounds": 3,
                  "pr_final_round": False,
                  # Pi independence: different provider required when both roles
                  # are pi. Same-provider different-model is an explicit fallback.
                  "coder_provider": None, "coder_model": None,
                  "reviewer_provider": None, "reviewer_model": None,
                  "fallback_models": {"claude": "sonnet", "codex": "gpt-5.6-luna",
                                      "cursor": "composer-2.5", "pi": "gemini-2.5-flash"}},
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
    # deepcopy, not dict(): a shallow copy would share nested dicts (e.g.
    # pair_loop.fallback_models) with DEFAULTS, so any caller mutating the
    # returned config would corrupt the defaults for the rest of the process.
    cfg = copy.deepcopy(DEFAULTS)
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
                # Merge one level deeper for nested dicts. A plain update()
                # replaces them wholesale, so overriding a single key of
                # pair_loop.fallback_models would drop the other vendor and
                # fail at lookup time.
                for key, value in values.items():
                    if isinstance(value, dict) and isinstance(cfg[section].get(key), dict):
                        cfg[section][key].update(value)
                    else:
                        cfg[section][key] = value
            # else: known section with a non-dict value (e.g. `"budget": null`)
            # -> keep the default dict, consistent with "malformed input never
            # raises" for the whole-file case.
        else:
            cfg[section] = values
    return cfg
