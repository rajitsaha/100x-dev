# Token Economics v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship accurate per-model cost, session/skill/subagent attribution, a real Codex adapter, run-manifest ingestion, budgets with three alert surfaces, git-native value ratios, and a rule-based cost-reduction suggestions panel — landing on the existing `scripts/token-dashboard.py` dashboard.

**Architecture:** Two new per-tool adapters (`scripts/adapters/claude_code.py`, `scripts/adapters/codex.py`) each own glob + incremental cache + parse and return a common summary shape; `token-dashboard.py`'s `build()` merges both adapters' summaries and does all cross-cutting aggregation (per-model pricing via `scripts/pricing.py`, value ratios via `scripts/_value.py`, budgets via `scripts/_budget.py`/`scripts/_config.py`, suggestions via `scripts/_suggest.py`, handoff-run costs via `scripts/run_manifest.py`). The dashboard UI is a single-file inline-SVG/vanilla-JS page, extended in place.

**Tech Stack:** Python 3 stdlib only (no third-party deps), `unittest` for tests, existing `node --test` / `npm run check` gate.

## Global Constraints

- Zero third-party dependencies (matches every existing `scripts/*.py`).
- Fully offline — no network calls except the existing non-blocking local `claude` CLI shellout in `scripts/_summaries.py` (untouched by this plan).
- Every "estimate" or "attributed" number must say so in code comments and in the UI — do not present estimates as billed truth (existing convention, `token-dashboard.py:17-19`).
- Pricing values in `scripts/pricing.py` are illustrative at plan-authoring time — verify against current published pricing during Task 1 and correct if stale.
- All new/changed scripts must keep `python3 scripts/token-dashboard.py --print` and `scripts/test_value.py` passing.
- Run `python3 hooks/gate-pass.py` in its own bash call before commits that trigger the commit hook (per repo convention) — never chained with the commit command.

---

### Task 1: Per-model pricing (`scripts/pricing.py`)

**Files:**
- Create: `scripts/pricing.py`
- Test: `scripts/test_pricing.py`

**Interfaces:**
- Produces: `pricing.TOKEN_KEYS` (tuple `("input","output","cache_read","cache_write")`), `pricing.rates_for_model(model_id: str|None) -> (dict, bool)` (rates dict + `is_fallback` flag), `pricing.cost_of(tokens: dict, model_id: str|None=None) -> float`, `pricing.cost_by_model(by_model: dict[str, dict]) -> (float, int)` (total cost, fallback-priced token count).

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_pricing.py
#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pricing


class TestPricing(unittest.TestCase):
    def test_known_model_not_flagged_fallback(self):
        rates, is_fallback = pricing.rates_for_model("claude-sonnet-4-5-20251001")
        self.assertFalse(is_fallback)
        self.assertEqual(rates, dict(r for k, r in pricing.RATES if k == "sonnet"))

    def test_unknown_model_falls_back_and_is_flagged(self):
        rates, is_fallback = pricing.rates_for_model("some-future-model-xyz")
        self.assertTrue(is_fallback)
        self.assertEqual(rates, pricing._FALLBACK_RATES)

    def test_none_model_falls_back(self):
        rates, is_fallback = pricing.rates_for_model(None)
        self.assertTrue(is_fallback)

    def test_cost_of_uses_matched_model_rate(self):
        tokens = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_write": 0}
        haiku_cost = pricing.cost_of(tokens, "claude-haiku-4-5-20251001")
        opus_cost = pricing.cost_of(tokens, "claude-opus-4-8")
        self.assertLess(haiku_cost, opus_cost)

    def test_cost_by_model_sums_across_models_and_flags_fallback_tokens(self):
        by_model = {
            "claude-sonnet-4-5": {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_write": 0},
            "totally-unknown-model": {"input": 0, "output": 500_000, "cache_read": 0, "cache_write": 0},
        }
        total, fallback_tokens = pricing.cost_by_model(by_model)
        sonnet_rates = dict(r for k, r in pricing.RATES if k == "sonnet")
        expected_sonnet = 1_000_000 / 1_000_000 * sonnet_rates["input"]
        expected_fallback = 500_000 / 1_000_000 * pricing._FALLBACK_RATES["output"]
        self.assertAlmostEqual(total, expected_sonnet + expected_fallback, places=6)
        self.assertEqual(fallback_tokens, 500_000)

    def test_gpt_5_pattern_matches_dotted_minor_versions(self):
        rates, is_fallback = pricing.rates_for_model("gpt-5.5")
        self.assertFalse(is_fallback)
        self.assertEqual(rates, dict(r for k, r in pricing.RATES if k == "gpt-5"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_pricing.py`
Expected: `ModuleNotFoundError: No module named 'pricing'`

- [ ] **Step 3: Implement `scripts/pricing.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_pricing.py -v`
Expected: 6 tests, all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/pricing.py scripts/test_pricing.py
git commit -m "feat(pricing): per-model rate table with fallback flagging"
```

---

### Task 2: Shared config loader (`scripts/_config.py`)

**Files:**
- Create: `scripts/_config.py`
- Test: `scripts/test_config.py`

**Interfaces:**
- Produces: `_config.CONFIG_PATH`, `_config.DEFAULTS` (dict with `budget` and `pair_loop` sections), `_config.load_config() -> dict` (defaults deep-merged under any `~/.100xprism/config.json` present).
- Consumed by: Task 8 (`_budget.py`), Plan 2 pair-loop tasks (`pair_loop` section).

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_config.py
#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self._orig_path = _config.CONFIG_PATH
        self._tmp = tempfile.mkdtemp()
        _config.CONFIG_PATH = os.path.join(self._tmp, "config.json")

    def tearDown(self):
        _config.CONFIG_PATH = self._orig_path

    def test_missing_file_returns_defaults(self):
        cfg = _config.load_config()
        self.assertIsNone(cfg["budget"]["daily_usd"])
        self.assertEqual(cfg["pair_loop"]["coder"], "claude")
        self.assertEqual(cfg["pair_loop"]["max_rounds"], 3)

    def test_partial_user_config_merges_over_defaults(self):
        with open(_config.CONFIG_PATH, "w") as f:
            json.dump({"budget": {"daily_usd": 50}}, f)
        cfg = _config.load_config()
        self.assertEqual(cfg["budget"]["daily_usd"], 50)
        self.assertIsNone(cfg["budget"]["weekly_usd"])  # untouched default
        self.assertEqual(cfg["pair_loop"]["reviewer"], "codex")  # untouched section

    def test_pair_loop_role_override(self):
        with open(_config.CONFIG_PATH, "w") as f:
            json.dump({"pair_loop": {"coder": "codex", "reviewer": "claude"}}, f)
        cfg = _config.load_config()
        self.assertEqual(cfg["pair_loop"]["coder"], "codex")
        self.assertEqual(cfg["pair_loop"]["reviewer"], "claude")
        self.assertEqual(cfg["pair_loop"]["max_rounds"], 3)  # default preserved

    def test_malformed_json_falls_back_to_defaults(self):
        with open(_config.CONFIG_PATH, "w") as f:
            f.write("{not json")
        cfg = _config.load_config()
        self.assertEqual(cfg, {k: dict(v) for k, v in _config.DEFAULTS.items()})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_config.py`
Expected: `ModuleNotFoundError: No module named '_config'`

- [ ] **Step 3: Implement `scripts/_config.py`**

```python
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
        if section in cfg and isinstance(values, dict):
            cfg[section].update(values)
        else:
            cfg[section] = values
    return cfg
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_config.py -v`
Expected: 4 tests, all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/_config.py scripts/test_config.py
git commit -m "feat(config): shared ~/.100xprism/config.json loader with defaults"
```

---

### Task 3: Claude Code adapter — parse/cache/scan + attribution

**Files:**
- Modify: `scripts/adapters/claude_code.py` (currently 15 lines, `iter_dir_days` only — rewritten to own the full parse pipeline moved out of `token-dashboard.py:128-233`)
- Test: `scripts/test_claude_code_adapter.py`

**Interfaces:**
- Consumes: nothing from other new modules (uses `_value.project_label`, `_value.mangle_path`).
- Produces: `claude_code.TOOL = "claude-code"`, `claude_code.SOURCE_DIR`, `claude_code.CACHE_FILE`, `claude_code.CACHE_VERSION = 4`, `claude_code.parse_file(path: str) -> dict` with keys `totals, by_day, by_model, by_day_model, comp, msgs, turns, first_fixed, session_id, main_tokens, subagent_tokens, by_skill, skill_invocations, skill_exact`, `claude_code.scan(verbose=False) -> list[dict]` (adds `mtime, size, project, projdir, tool` to each summary), `claude_code.iter_dir_days(summaries) -> Iterator[Usage]` (unchanged interface, reads `by_day` from the richer summaries).

Real transcript fields verified against `~/.claude/projects/*/*.jsonl` on this machine (2026-07-09): `sessionId` (also duplicated as `session_id`), `isSidechain` (bool), `attributionSkill` / `attributionPlugin` (set natively by Claude Code when a Skill tool is active — exact, not heuristic), `message.content` may contain `<command-name>/xyz</command-name>` for built-in slash commands that are *not* skills (these don't set `attributionSkill`, so they need the existing heuristic fallback).

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_claude_code_adapter.py
#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "adapters"))
import adapters.claude_code as claude_code


def _line(role, content, usage=None, session_id="s1", ts="2026-07-09T10:00:00Z",
          is_sidechain=False, attribution_skill=None):
    msg = {"role": role, "content": content, "model": "claude-sonnet-4-5-20251001"}
    if usage:
        msg["usage"] = usage
    o = {"type": role, "message": msg, "sessionId": session_id, "timestamp": ts,
         "isSidechain": is_sidechain}
    if attribution_skill:
        o["attributionSkill"] = attribution_skill
    return json.dumps(o) + "\n"


class TestClaudeCodeAdapter(unittest.TestCase):
    def _write(self, lines):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as f:
            f.writelines(lines)
        self.addCleanup(os.remove, path)
        return path

    def test_basic_token_aggregation(self):
        path = self._write([
            _line("user", "hi", usage=None),
            _line("assistant", "hello", usage={"input_tokens": 100, "output_tokens": 50,
                                                "cache_read_input_tokens": 10,
                                                "cache_creation_input_tokens": 5}),
        ])
        s = claude_code.parse_file(path)
        self.assertEqual(s["totals"], {"input": 100, "output": 50, "cache_read": 10, "cache_write": 5})
        self.assertEqual(s["session_id"], "s1")

    def test_sidechain_tokens_split_from_main(self):
        path = self._write([
            _line("assistant", "main work", usage={"input_tokens": 100, "output_tokens": 10,
                                                     "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                  is_sidechain=False),
            _line("assistant", "subagent work", usage={"input_tokens": 40, "output_tokens": 5,
                                                         "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                  is_sidechain=True),
        ])
        s = claude_code.parse_file(path)
        self.assertEqual(s["main_tokens"]["input"], 100)
        self.assertEqual(s["subagent_tokens"]["input"], 40)

    def test_attribution_skill_is_used_directly(self):
        path = self._write([
            _line("assistant", "doing skill work", usage={"input_tokens": 200, "output_tokens": 20,
                                                            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                  attribution_skill="superpowers:brainstorming"),
        ])
        s = claude_code.parse_file(path)
        self.assertEqual(s["by_skill"]["superpowers:brainstorming"]["input"], 200)
        self.assertIn("superpowers:brainstorming", s["skill_exact"])
        self.assertEqual(s["skill_invocations"]["superpowers:brainstorming"], 1)

    def test_command_name_fallback_segments_when_no_attribution_skill(self):
        path = self._write([
            _line("user", "<command-name>/model</command-name>\n<command-message>model</command-message>"),
            _line("assistant", "switched model", usage={"input_tokens": 30, "output_tokens": 5,
                                                          "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}),
        ])
        s = claude_code.parse_file(path)
        self.assertEqual(s["by_skill"]["/model"]["input"], 30)
        self.assertNotIn("/model", s["skill_exact"])

    def test_by_day_model_breakdown(self):
        path = self._write([
            _line("assistant", "x", usage={"input_tokens": 10, "output_tokens": 1,
                                            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                  ts="2026-07-09T10:00:00Z"),
        ])
        s = claude_code.parse_file(path)
        self.assertEqual(s["by_day_model"]["2026-07-09"]["claude-sonnet-4-5-20251001"]["input"], 10)

    def test_scan_adds_metadata_and_caches(self):
        tmp = tempfile.mkdtemp()
        proj_dir = os.path.join(tmp, "-Users-x-proj")
        os.makedirs(proj_dir)
        path = os.path.join(proj_dir, "sess1.jsonl")
        with open(path, "w") as f:
            f.write(_line("assistant", "x", usage={"input_tokens": 10, "output_tokens": 1,
                                                     "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}))
        orig_source, orig_cache = claude_code.SOURCE_DIR, claude_code.CACHE_FILE
        claude_code.SOURCE_DIR = tmp
        claude_code.CACHE_FILE = os.path.join(tmp, "cache.json")
        try:
            summaries = claude_code.scan(verbose=False)
            self.assertEqual(len(summaries), 1)
            self.assertEqual(summaries[0]["tool"], "claude-code")
            self.assertEqual(summaries[0]["projdir"], "-Users-x-proj")
            # second scan should hit cache (mtime/size unchanged) and return identical data
            summaries2 = claude_code.scan(verbose=False)
            self.assertEqual(summaries2[0]["totals"], summaries[0]["totals"])
        finally:
            claude_code.SOURCE_DIR, claude_code.CACHE_FILE = orig_source, orig_cache


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_claude_code_adapter.py`
Expected: `AttributeError: module 'adapters.claude_code' has no attribute 'parse_file'`

- [ ] **Step 3: Implement `scripts/adapters/claude_code.py`**

```python
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
user turn as a fallback — attribution for that path is a boundary heuristic
(usage between one marker and the next), same honesty convention as the existing
character-count composition estimate below.
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import _value  # noqa: E402 — project_label / mangle_path

from . import Usage  # noqa: E402

TOOL = "claude-code"
HOME = os.path.expanduser("~")
SOURCE_DIR = os.path.join(HOME, ".claude", "projects")
CACHE_FILE = os.path.join(HOME, ".claude", ".token-dashboard-cache.json")
CACHE_VERSION = 4  # bump -> re-parse all transcripts (attribution fields added)

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
    prev_skill = None

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
        role = ""
        if isinstance(m, dict):
            role = m.get("role") or o.get("type") or ""
            _classify(role, m.get("content"), comp, tool_names)
            text = _extract_text(m.get("content"))
            cmd = _COMMAND_RE.search(text) if text else None
            current_skill_marker = cmd.group(1) if cmd else None
        else:
            current_skill_marker = None

        attr_skill = o.get("attributionSkill") or current_skill_marker
        if attr_skill:
            if attr_skill != prev_skill:
                skill_invocations[attr_skill] += 1
            if o.get("attributionSkill"):
                skill_exact.add(attr_skill)
        if current_skill_marker or o.get("attributionSkill"):
            prev_skill = attr_skill

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
        with open(CACHE_FILE, "w") as f:
            json.dump({"version": CACHE_VERSION, "files": files}, f)
    except Exception as e:
        print(f"warning: could not write claude_code cache: {e}", file=sys.stderr)


def scan(verbose=False):
    """Glob + incrementally parse every Claude Code transcript. Returns a list of
    per-file summary dicts with mtime/size/project/projdir/tool added."""
    cache = load_cache()
    paths = glob.glob(os.path.join(SOURCE_DIR, "*", "*.jsonl"))
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
        summary["project"] = project_label(p)
        summary["projdir"] = os.path.basename(os.path.dirname(p))
        summary["tool"] = TOOL
        new_cache[p] = summary
        reparsed += 1
        if verbose and reparsed % 200 == 0:
            print(f"  parsed {reparsed} new/changed claude transcripts...", file=sys.stderr)
    save_cache(new_cache)
    if verbose:
        print(f"claude_code: scanned {len(paths)} transcripts ({reparsed} re-parsed, "
              f"{len(paths) - reparsed} cached)", file=sys.stderr)
    return list(new_cache.values())


def iter_dir_days(file_summaries):
    """Yield one Usage per (transcript dir, day) from already-parsed summaries."""
    for s in file_summaries:
        projdir = s.get("projdir") or ""
        for day, d in (s.get("by_day") or {}).items():
            yield Usage(projdir, day, d.get("input", 0), d.get("output", 0),
                        d.get("cache_read", 0), d.get("cache_write", 0), TOOL)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_claude_code_adapter.py -v`
Expected: 6 tests, all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/adapters/claude_code.py scripts/test_claude_code_adapter.py
git commit -m "feat(adapters): claude_code owns full parse pipeline + session/subagent/skill attribution"
```

---

### Task 4: Codex adapter — real implementation + adapter registry update

**Files:**
- Modify: `scripts/adapters/codex.py` (currently a stub, `scripts/adapters/codex.py:1-15`)
- Modify: `scripts/adapters/__init__.py:13` (no change needed — `ADAPTERS = [claude_code, codex]` already lists both; verify still correct)
- Test: `scripts/test_codex_adapter.py`

**Interfaces:**
- Produces: same shape as `claude_code.scan()` — `codex.scan(verbose=False) -> list[dict]` with keys `totals, by_day, by_model, by_day_model, comp (empty), msgs, turns, first_fixed (0), session_id, main_tokens, subagent_tokens (empty), by_skill (empty), skill_invocations (empty), skill_exact (empty), mtime, size, project, projdir, tool="codex"`. Empty-list return when `~/.codex/sessions` doesn't exist.

Codex rollout format verified against a real local session (`~/.codex/sessions/2026/07/04/rollout-*.jsonl`, CLI v0.142.5) on 2026-07-09: `session_meta.payload` has `session_id`/`id` and `cwd`; `turn_context.payload.model` gives the active model per turn; `event_msg` lines with `payload.type == "token_count"` carry `payload.info.total_token_usage` — confirmed **cumulative** across the session (monotonically non-decreasing across 6 consecutive events in the sample file). Codex/OpenAI's cache accounting folds cached tokens into `input_tokens` (unlike Claude's separate cache-read count), so `input` here is `input_tokens - cached_input_tokens`. Codex exposes no cache-write count — always `0`, a documented limitation, not a bug.

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_codex_adapter.py
#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adapters.codex as codex


def _rollout_lines():
    return [
        json.dumps({"timestamp": "2026-07-09T10:00:00.000Z", "type": "session_meta",
                    "payload": {"session_id": "abc-123", "id": "abc-123",
                                "cwd": "/Users/x/proj"}}) + "\n",
        json.dumps({"timestamp": "2026-07-09T10:00:01.000Z", "type": "turn_context",
                    "payload": {"model": "gpt-5.5"}}) + "\n",
        json.dumps({"timestamp": "2026-07-09T10:00:05.000Z", "type": "event_msg",
                    "payload": {"type": "token_count", "info": {"total_token_usage": {
                        "input_tokens": 1000, "cached_input_tokens": 200,
                        "output_tokens": 100, "total_tokens": 1100}}}}) + "\n",
        json.dumps({"timestamp": "2026-07-09T10:00:10.000Z", "type": "event_msg",
                    "payload": {"type": "token_count", "info": {"total_token_usage": {
                        "input_tokens": 3000, "cached_input_tokens": 1200,
                        "output_tokens": 250, "total_tokens": 3250}}}}) + "\n",
    ]


class TestCodexAdapter(unittest.TestCase):
    def _write(self, lines):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as f:
            f.writelines(lines)
        self.addCleanup(os.remove, path)
        return path

    def test_cumulative_deltas_computed_correctly(self):
        s = codex.parse_file(self._write(_rollout_lines()))
        # first event: input_tokens=1000, cached=200 -> cache_read=200, input=800
        # second event delta: (3000-1000)=2000 total-in, (1200-200)=1000 cached -> input=1000, cache_read=1000
        self.assertEqual(s["totals"]["cache_read"], 200 + 1000)
        self.assertEqual(s["totals"]["input"], 800 + 1000)
        self.assertEqual(s["totals"]["output"], 100 + 150)
        self.assertEqual(s["totals"]["cache_write"], 0)

    def test_session_metadata_captured(self):
        s = codex.parse_file(self._write(_rollout_lines()))
        self.assertEqual(s["session_id"], "abc-123")
        self.assertEqual(s["cwd"], "/Users/x/proj")

    def test_model_from_turn_context_used_for_by_model(self):
        s = codex.parse_file(self._write(_rollout_lines()))
        self.assertIn("gpt-5.5", s["by_model"])
        self.assertEqual(s["by_model"]["gpt-5.5"]["output"], 250)

    def test_scan_returns_empty_when_no_sessions_dir(self):
        orig = codex.SOURCE_DIR
        codex.SOURCE_DIR = "/nonexistent/path/xyz"
        try:
            self.assertEqual(codex.scan(verbose=False), [])
        finally:
            codex.SOURCE_DIR = orig

    def test_scan_adds_metadata(self):
        tmp = tempfile.mkdtemp()
        day_dir = os.path.join(tmp, "2026", "07", "09")
        os.makedirs(day_dir)
        path = os.path.join(day_dir, "rollout-x.jsonl")
        with open(path, "w") as f:
            f.writelines(_rollout_lines())
        orig_source, orig_cache = codex.SOURCE_DIR, codex.CACHE_FILE
        codex.SOURCE_DIR = tmp
        codex.CACHE_FILE = os.path.join(tmp, "cache.json")
        try:
            summaries = codex.scan(verbose=False)
            self.assertEqual(len(summaries), 1)
            self.assertEqual(summaries[0]["tool"], "codex")
            self.assertTrue(summaries[0]["project"].endswith("proj"))
        finally:
            codex.SOURCE_DIR, codex.CACHE_FILE = orig_source, orig_cache


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_codex_adapter.py`
Expected: `AttributeError: module 'adapters.codex' has no attribute 'parse_file'`

- [ ] **Step 3: Implement `scripts/adapters/codex.py`**

```python
"""
Codex cost adapter — parses ~/.codex/sessions/**/rollout-*.jsonl.

Verified against a real Codex CLI (v0.142.5) rollout on 2026-07-09: each file is
one session, containing `session_meta` (session_id, cwd), `turn_context`
(per-turn `model`), and `event_msg`/`token_count` events whose
`info.total_token_usage` is a CUMULATIVE running total for the session (confirmed
monotonically non-decreasing across consecutive events in the sample file). Per-
event token counts are therefore deltas between consecutive readings, not the
readings themselves.

Codex/OpenAI's cache accounting folds cached tokens INTO `input_tokens` (unlike
Claude Code's separate cache_read, which is additional to input) — so `input`
here is computed as `input_tokens - cached_input_tokens` to line up with our
(input, cache_read) split. Codex exposes no cache-write count; cache_write is
always 0 for this adapter — a documented limitation, not a bug.
"""
import glob
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import _value  # noqa: E402

from . import Usage  # noqa: E402

TOOL = "codex"
HOME = os.path.expanduser("~")
SOURCE_DIR = os.path.join(HOME, ".codex", "sessions")
CACHE_FILE = os.path.join(HOME, ".claude", ".token-dashboard-codex-cache.json")
CACHE_VERSION = 1


def _empty():
    return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}


def _add(dst, i, o, cr, cw):
    dst["input"] += i
    dst["output"] += o
    dst["cache_read"] += cr
    dst["cache_write"] += cw


def parse_file(path):
    """Aggregate one Codex rollout into the same summary shape claude_code.parse_file
    produces (minus fields Codex has no data for: composition, first_fixed,
    subagent/skill attribution)."""
    totals = _empty()
    by_day = defaultdict(_empty)
    by_model = defaultdict(_empty)
    by_day_model = defaultdict(lambda: defaultdict(_empty))
    session_id = None
    cwd = None
    current_model = "unknown"
    prev_cum = None
    msgs = 0

    for line in open(path, errors="ignore"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if not isinstance(o, dict):
            continue
        t = o.get("type")
        if t == "session_meta":
            payload = o.get("payload") or {}
            session_id = payload.get("session_id") or payload.get("id")
            cwd = payload.get("cwd")
            continue
        if t == "turn_context":
            model = (o.get("payload") or {}).get("model")
            if model:
                current_model = model
            continue
        if t != "event_msg":
            continue
        payload = o.get("payload") or {}
        if payload.get("type") != "token_count":
            continue
        cum = (payload.get("info") or {}).get("total_token_usage")
        if not isinstance(cum, dict):
            continue
        if prev_cum is None:
            d_in_total = cum.get("input_tokens", 0)
            d_cr = cum.get("cached_input_tokens", 0)
            d_out = cum.get("output_tokens", 0)
        else:
            d_in_total = cum.get("input_tokens", 0) - prev_cum.get("input_tokens", 0)
            d_cr = cum.get("cached_input_tokens", 0) - prev_cum.get("cached_input_tokens", 0)
            d_out = cum.get("output_tokens", 0) - prev_cum.get("output_tokens", 0)
        prev_cum = cum
        if d_in_total <= 0 and d_out <= 0 and d_cr <= 0:
            continue  # duplicate/unchanged event (e.g. an end-of-session repeat)
        d_cr = max(d_cr, 0)
        d_in = max(d_in_total - d_cr, 0)
        d_out = max(d_out, 0)
        msgs += 1
        _add(totals, d_in, d_out, d_cr, 0)
        _add(by_model[current_model], d_in, d_out, d_cr, 0)
        day = (o.get("timestamp") or "")[:10] or "unknown"
        _add(by_day[day], d_in, d_out, d_cr, 0)
        _add(by_day_model[day][current_model], d_in, d_out, d_cr, 0)

    return {
        "totals": totals,
        "by_day": dict(by_day),
        "by_model": dict(by_model),
        "by_day_model": {d: dict(models) for d, models in by_day_model.items()},
        "comp": {},
        "msgs": msgs,
        "turns": msgs,
        "first_fixed": 0,
        "session_id": session_id,
        "main_tokens": dict(totals),
        "subagent_tokens": _empty(),
        "by_skill": {},
        "skill_invocations": {},
        "skill_exact": [],
        "cwd": cwd,
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
        with open(CACHE_FILE, "w") as f:
            json.dump({"version": CACHE_VERSION, "files": files}, f)
    except Exception as e:
        print(f"warning: could not write codex cache: {e}", file=sys.stderr)


def _project_label(cwd):
    return _value.project_label_for_path(cwd) if cwd else "unknown"


def scan(verbose=False):
    """Glob + incrementally parse every Codex rollout. Returns [] if Codex has
    never been used locally (no ~/.codex/sessions dir)."""
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
        summary["project"] = _project_label(cwd)
        summary["projdir"] = (_value.mangle_path(os.path.abspath(os.path.expanduser(cwd)))
                               if cwd else "unknown")
        summary["tool"] = TOOL
        new_cache[p] = summary
        reparsed += 1
    save_cache(new_cache)
    if verbose:
        print(f"codex: scanned {len(paths)} rollouts ({reparsed} re-parsed, "
              f"{len(paths) - reparsed} cached)", file=sys.stderr)
    return list(new_cache.values())


def iter_dir_days(file_summaries):
    for s in file_summaries:
        projdir = s.get("projdir") or ""
        for day, d in (s.get("by_day") or {}).items():
            yield Usage(projdir, day, d.get("input", 0), d.get("output", 0),
                        d.get("cache_read", 0), d.get("cache_write", 0), TOOL)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_codex_adapter.py -v`
Expected: 5 tests, all PASS

- [ ] **Step 5: Verify `scripts/adapters/__init__.py` still matches**

Read `scripts/adapters/__init__.py` — confirm `ADAPTERS = [claude_code, codex]` (line 13) and the `Usage` namedtuple are unchanged; both adapters now import `Usage` from `.` (this package). No edit needed if already correct; if the docstring still calls codex "a documented stub," update it:

```python
"""Cost adapters: per-tool sources of (dir, day, token) usage.

Both `claude_code` and `codex` are real, incremental-cache-backed parsers of
their tool's local transcript format. Cursor / Antigravity expose no local
token data, so they have no adapter — their directories still appear via the
value layer.
"""
```

- [ ] **Step 6: Commit**

```bash
git add scripts/adapters/codex.py scripts/adapters/__init__.py scripts/test_codex_adapter.py
git commit -m "feat(adapters): implement real Codex cost adapter (cumulative token_count deltas)"
```

---

### Task 5: Value layer — merged-PR detection, releases, ratios

**Files:**
- Modify: `scripts/_value.py:100-201` (`_PR_RE`, `git_value`, `_empty_value`), `scripts/_value.py:25` (`STORE_VERSION`)
- Test: extend `scripts/test_value.py`

**Interfaces:**
- Produces: `_value.git_value(repo, start, end)` now also returns `"releases": [str]` and a `"prs"` count derived from the union of squash-merge subjects and real merge commits (more accurate than the old regex-only count, same key name — no caller changes needed). `_value._empty_value()` gains `"releases": []`.
- Consumed by: Task 6 (`assemble_directories` computes `cost_per_commit`/`cost_per_pr` from `value["commits"]`/`value["prs"]` + the row's `cost` — those two keys are NOT added inside `_value.py`, since cost is only known at the join site in `token-dashboard.py`).

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_value.py` (uses the existing `git()` helper already defined at the top of that file):

```python
class TestMergedPRsAndReleases(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        git(self.repo, "init", "-q")
        git(self.repo, "commit", "--allow-empty", "-m", "init")

    def test_squash_pr_subject_counted(self):
        git(self.repo, "commit", "--allow-empty", "-m", "feat: add thing (#42)")
        v = _value.git_value(self.repo, None, None)
        self.assertEqual(v["prs"], 1)

    def test_real_merge_commit_counted(self):
        git(self.repo, "checkout", "-b", "feature", "-q")
        git(self.repo, "commit", "--allow-empty", "-m", "work")
        git(self.repo, "checkout", "-", "-q")
        git(self.repo, "merge", "--no-ff", "feature", "-m", "Merge pull request #7 from x/feature")
        v = _value.git_value(self.repo, None, None)
        self.assertEqual(v["prs"], 1)

    def test_squash_and_merge_dedup_by_number(self):
        git(self.repo, "commit", "--allow-empty", "-m", "feat: thing (#9)")
        git(self.repo, "checkout", "-b", "feature2", "-q")
        git(self.repo, "commit", "--allow-empty", "-m", "work2")
        git(self.repo, "checkout", "-", "-q")
        git(self.repo, "merge", "--no-ff", "feature2", "-m", "Merge pull request #9 duplicate-number-test")
        v = _value.git_value(self.repo, None, None)
        self.assertEqual(v["prs"], 1)  # same PR number from two commit shapes -> deduped

    def test_release_tags_in_window(self):
        git(self.repo, "tag", "v1.0.0")
        v = _value.git_value(self.repo, None, None)
        self.assertIn("v1.0.0", v["releases"])

    def test_empty_value_has_releases_key(self):
        self.assertEqual(_value._empty_value()["releases"], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_value.py -v`
Expected: new tests FAIL (`KeyError: 'releases'` / `prs` count mismatches)

- [ ] **Step 3: Implement the `_value.py` changes**

Modify `scripts/_value.py`:

```python
# replace line 25
STORE_VERSION = 3

# replace line 102 (_PR_RE) — add a capturing variant alongside the existing one
_PR_RE = re.compile(r"\(#\d+\)")
_PR_NUM_RE = re.compile(r"#(\d+)")


# insert after git_value's helper section (after line 150, before "fs fallback" comment)
def _merged_prs(repo, start, end):
    """PR numbers from real merge commits within the window (the --no-merges log
    used for `subjects` excludes these, so this is a separate pass)."""
    args = ["log", "--merges", "--pretty=%s"]
    if start:
        args.append(f"--since={start} 00:00:00")
    if end:
        args.append(f"--until={end} 23:59:59")
    try:
        subjects = [s for s in _git(repo, *args).stdout.splitlines() if s]
    except (OSError, subprocess.SubprocessError):
        return set()
    numbers = set()
    for s in subjects:
        m = _PR_NUM_RE.search(s)
        if m:
            numbers.add(m.group(1))
    return numbers


def _release_tags(repo, start, end):
    """Tags created within the window (best-effort: uses tag *creation* date via
    for-each-ref, not commit date)."""
    try:
        r = _git(repo, "for-each-ref", "refs/tags", "--sort=-creatordate",
                 "--format=%(creatordate:short) %(refname:short)")
    except (OSError, subprocess.SubprocessError):
        return []
    tags = []
    for line in r.stdout.splitlines():
        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue
        date, name = parts
        if (not start or date >= start) and (not end or date <= end):
            tags.append(name)
    return tags


# replace git_value (lines 118-150) in full
def git_value(repo, start, end):
    """Windowed git activity, or None if `repo` is not a git work tree."""
    try:
        if _git(repo, "rev-parse", "--is-inside-work-tree").returncode != 0:
            return None
        args = ["log", "--no-merges", "--pretty=%s"]
        if start:
            args.append(f"--since={start} 00:00:00")
        if end:
            args.append(f"--until={end} 23:59:59")
        subjects = [s for s in _git(repo, *args).stdout.splitlines() if s]
        nargs = ["log", "--no-merges", "--numstat", "--pretty=tformat:"]
        if start:
            nargs.append(f"--since={start} 00:00:00")
        if end:
            nargs.append(f"--until={end} 23:59:59")
        files, ins, dele = set(), 0, 0
        for ln in _git(repo, *nargs).stdout.splitlines():
            parts = ln.split("\t")
            if len(parts) == 3:
                a, d, path = parts
                files.add(path)
                ins += int(a) if a.isdigit() else 0
                dele += int(d) if d.isdigit() else 0
        squash_prs = {m.group(1) for s in subjects for m in [_PR_NUM_RE.search(s)] if m}
        merge_prs = _merged_prs(repo, start, end)
        merged_pr_numbers = squash_prs | merge_prs
        releases = _release_tags(repo, start, end)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return {
        "commits": len(subjects),
        "prs": len(merged_pr_numbers),
        "files": len(files), "insertions": ins, "deletions": dele,
        "subjects": subjects[:5],
        "releases": releases,
    }


# replace _empty_value (lines 184-187)
def _empty_value():
    return {"kind": "none", "commits": 0, "prs": 0, "files": 0,
            "insertions": 0, "deletions": 0, "subjects": [], "fs_files": 0,
            "releases": [], "summary": None}
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_value.py -v`
Expected: all tests (existing + new) PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/_value.py scripts/test_value.py
git commit -m "feat(value): merge-commit PR detection dedup, release-tag mining, STORE_VERSION 3"
```

---

### Task 6: Dashboard `build()` rewire — merged adapters, per-model cost, attribution, ratios

**Files:**
- Modify: `scripts/token-dashboard.py:33-331` (imports, `RATES`/`_empty`/`_add`/composition helpers/`parse_file`/`load_cache`/`save_cache`/`build`/`assemble_directories` — the parse/cache functions move out per Task 3/4; `build`/`assemble_directories` are rewritten)
- Test: extend `scripts/test_value.py` (it already loads `token-dashboard.py` by path as `td`) with a new `TestBuildIntegration` class

**Interfaces:**
- Consumes: `pricing.cost_by_model`, `adapters.claude_code.scan`, `adapters.codex.scan`, `_value.git_value`/`cached_dir_value` (unchanged calls) plus the new `releases` key.
- Produces: `build()` dataset gains `by_session` (top 50 by cost, last 30 days), `by_skill` (sorted list of `{skill, cost, invocations, exact}`), `main_subagent_split` (`{"main_cost":, "subagent_cost":}`), `fallback_pct` (share of total tokens priced at fallback rates), `directories[i].value.cost_per_commit` / `cost_per_pr` (computed at the join, not inside `_value.py`). `total_cost` is now computed via `pricing.cost_by_model(by_model)` instead of the old flat `RATES` sum. The `rates` field in the dataset is dropped (per-model now, not one flat table) — dashboard JS must not reference `d.rates` afterward (verified in Task 10).

- [ ] **Step 1: Write the failing test**

```python
# appended to scripts/test_value.py

class TestBuildIntegration(unittest.TestCase):
    """Exercises build() against a fake ~/.claude/projects tree (claude_code
    adapter only — codex.scan() safely returns [] when ~/.codex/sessions is
    absent in the test's patched HOME)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj_dir = os.path.join(self.tmp, "claude", "projects", "-Users-x-proj")
        os.makedirs(self.proj_dir)
        session = {
            "type": "assistant",
            "message": {"role": "assistant", "content": "done",
                        "model": "claude-sonnet-4-5-20251001",
                        "usage": {"input_tokens": 1000, "output_tokens": 200,
                                  "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0}},
            "sessionId": "sess-abc", "timestamp": "2026-07-09T10:00:00Z",
            "isSidechain": False,
        }
        with open(os.path.join(self.proj_dir, "sess-abc.jsonl"), "w") as f:
            f.write(json.dumps(session) + "\n")

        import adapters.claude_code as claude_code
        import adapters.codex as codex
        self.claude_code = claude_code
        self.codex = codex
        self._orig_source = claude_code.SOURCE_DIR
        self._orig_cache = claude_code.CACHE_FILE
        self._orig_codex_source = codex.SOURCE_DIR
        claude_code.SOURCE_DIR = os.path.join(self.tmp, "claude", "projects")
        claude_code.CACHE_FILE = os.path.join(self.tmp, "cc-cache.json")
        codex.SOURCE_DIR = os.path.join(self.tmp, "nonexistent-codex")

    def tearDown(self):
        self.claude_code.SOURCE_DIR = self._orig_source
        self.claude_code.CACHE_FILE = self._orig_cache
        self.codex.SOURCE_DIR = self._orig_codex_source

    def test_build_produces_by_session_and_by_skill_and_split(self):
        data = td.build(verbose=False)
        self.assertTrue(any(s["session_id"] == "sess-abc" for s in data["by_session"]))
        self.assertIn("main_subagent_split", data)
        self.assertGreaterEqual(data["main_subagent_split"]["main_cost"], 0)
        self.assertIn("fallback_pct", data)
        self.assertGreater(data["total_cost"], 0)
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_value.py -v`
Expected: `AttributeError` / `KeyError: 'by_session'` (build() doesn't yet expose these keys)

- [ ] **Step 3: Rewrite `scripts/token-dashboard.py`'s data layer**

Replace `scripts/token-dashboard.py:33-331` (everything from the imports down through the end of `assemble_directories`) with:

```python
import argparse
import glob
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
        except (OSError, ValueError):
            continue
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
```

Note: `pricing.cost_of` (single-model helper, used for the unchanged `by_project` display which was already an approximation mixing models) stays as a convenience wrapper — `by_project`'s cost column keeps its pre-existing "rough" framing.

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_value.py -v`
Expected: all tests, including `TestBuildIntegration`, PASS

Run: `python3 scripts/token-dashboard.py --print`
Expected: prints without traceback (real data on this machine — verifies the rewrite against production transcripts, not just fixtures)

- [ ] **Step 5: Commit**

```bash
git add scripts/token-dashboard.py scripts/test_value.py
git commit -m "feat(dashboard): rewire build() onto merged adapters, per-model cost, attribution, ratios"
```

---

### Task 7: Run-manifest schema, join, and `run-cost.py` CLI

**Files:**
- Create: `scripts/run_manifest.py`
- Create: `scripts/run-cost.py`
- Test: `scripts/test_run_manifest.py`

**Interfaces:**
- Produces: `run_manifest.SCHEMA_VERSION = 1`, `run_manifest.RUNS_DIR`, `run_manifest.new_manifest(run_id, task, cwd, branch, coder, reviewer, reviewer_fallback=False) -> dict`, `run_manifest.manifest_path(run_id) -> str`, `run_manifest.save_manifest(manifest)`, `run_manifest.load_manifest(run_id_or_path) -> dict`, `run_manifest.list_manifests() -> list[str]`, `run_manifest.add_round(manifest, role, tool, session_id=None) -> dict` (mutates + saves), `run_manifest.close_round(manifest, round_, **fields)`, `run_manifest.close_run(manifest, verdict, merged=None)`, `run_manifest.round_cost(round_, summaries, pricing_mod, cwd=None) -> float`, `run_manifest.run_cost(manifest, summaries) -> {"total":, "coder":, "reviewer":}`.
- Consumed by: Task 6 (`_build_handoff_runs`), Plan 2's pair-loop CLI, `run-cost.py`.

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_run_manifest.py
#!/usr/bin/env python3
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_manifest
import pricing


class TestRunManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = run_manifest.RUNS_DIR
        run_manifest.RUNS_DIR = self.tmp

    def tearDown(self):
        run_manifest.RUNS_DIR = self._orig

    def test_new_manifest_shape(self):
        m = run_manifest.new_manifest("run1", "fix bug", "/repo", "feat/x", "claude", "codex")
        self.assertEqual(m["v"], 1)
        self.assertEqual(m["rounds"], [])
        self.assertEqual(m["outcome"]["verdict"], None)

    def test_save_and_load_roundtrip(self):
        m = run_manifest.new_manifest("run1", "fix bug", "/repo", "feat/x", "claude", "codex")
        run_manifest.save_manifest(m)
        loaded = run_manifest.load_manifest("run1")
        self.assertEqual(loaded["run_id"], "run1")

    def test_add_round_increments_n_correctly(self):
        m = run_manifest.new_manifest("run1", "t", "/repo", "b", "claude", "codex")
        r1 = run_manifest.add_round(m, "coder", "claude", session_id="s1")
        self.assertEqual(r1["n"], 1)
        run_manifest.close_round(m, r1, findings_addressed=0)
        r2 = run_manifest.add_round(m, "reviewer", "codex", session_id="s2")
        self.assertEqual(r2["n"], 1)  # same round number as its paired coder round
        run_manifest.close_round(m, r2, findings=2, verdict="CHANGES_REQUESTED")
        r3 = run_manifest.add_round(m, "coder", "claude", session_id="s3")
        self.assertEqual(r3["n"], 2)

    def test_partial_manifest_survives_reload(self):
        m = run_manifest.new_manifest("run1", "t", "/repo", "b", "claude", "codex")
        run_manifest.add_round(m, "coder", "claude", session_id="s1")
        reloaded = run_manifest.load_manifest("run1")
        self.assertEqual(len(reloaded["rounds"]), 1)
        self.assertIsNone(reloaded["rounds"][0]["ended"])

    def test_list_manifests_returns_all_saved(self):
        run_manifest.save_manifest(run_manifest.new_manifest("a", "t", "/r", "b", "claude", "codex"))
        run_manifest.save_manifest(run_manifest.new_manifest("b", "t", "/r", "b", "claude", "codex"))
        self.assertEqual(len(run_manifest.list_manifests()), 2)

    def test_run_cost_joins_by_session_id(self):
        m = run_manifest.new_manifest("run1", "t", "/repo", "b", "claude", "codex")
        r1 = run_manifest.add_round(m, "coder", "claude", session_id="s1")
        run_manifest.close_round(m, r1)
        r2 = run_manifest.add_round(m, "reviewer", "codex", session_id="s2")
        run_manifest.close_round(m, r2)
        summaries = [
            {"session_id": "s1", "by_model": {"claude-sonnet-4-5": {"input": 1_000_000, "output": 0,
                                                                     "cache_read": 0, "cache_write": 0}},
             "project": "repo", "mtime": 0},
            {"session_id": "s2", "by_model": {"gpt-5.5": {"input": 0, "output": 1_000_000,
                                                           "cache_read": 0, "cache_write": 0}},
             "project": "repo", "mtime": 0},
        ]
        result = run_manifest.run_cost(m, summaries)
        sonnet_rates = dict(r for k, r in pricing.RATES if k == "sonnet")
        gpt5_rates = dict(r for k, r in pricing.RATES if k == "gpt-5")
        self.assertAlmostEqual(result["coder"], sonnet_rates["input"], places=4)
        self.assertAlmostEqual(result["reviewer"], gpt5_rates["output"], places=4)
        self.assertAlmostEqual(result["total"], result["coder"] + result["reviewer"], places=4)

    def test_run_cost_falls_back_to_time_window_when_no_session_match(self):
        m = run_manifest.new_manifest("run1", "t", "/repo", "b", "claude", "codex")
        r1 = run_manifest.add_round(m, "coder", "claude", session_id=None)
        run_manifest.close_round(m, r1)
        m["rounds"][0]["started"] = "2026-07-09T10:00:00Z"
        m["rounds"][0]["ended"] = "2026-07-09T10:10:00Z"
        import time as _time
        import calendar
        in_window_mtime = calendar.timegm((2026, 7, 9, 10, 5, 0))
        summaries = [{"session_id": None, "project": "repo",
                      "by_model": {"claude-sonnet-4-5": {"input": 100_000, "output": 0,
                                                          "cache_read": 0, "cache_write": 0}},
                      "mtime": in_window_mtime}]
        result = run_manifest.run_cost(m, summaries)
        self.assertGreater(result["coder"], 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_run_manifest.py`
Expected: `ModuleNotFoundError: No module named 'run_manifest'`

- [ ] **Step 3: Implement `scripts/run_manifest.py`**

```python
#!/usr/bin/env python3
"""
run_manifest.py — schema v1 reader/writer + session-cost join for pair-loop runs.

Manifest files live at ~/.100xprism/handoff-runs/<run-id>.json, one per pair-loop
run, written incrementally (atomic rename) by the pair-loop skill so a crashed run
still leaves an ingestable partial manifest. Single source of truth for the
schema and for joining a run's rounds to token cost — both the dashboard
(aggregate view, token-dashboard.py) and run-cost.py (a running loop's own
budget check) use it.
"""
import glob
import json
import os
import tempfile
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
RUNS_DIR = os.path.join(HOME, ".100xprism", "handoff-runs")
SCHEMA_VERSION = 1


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_manifest(run_id, task, cwd, branch, coder, reviewer, reviewer_fallback=False):
    return {
        "v": SCHEMA_VERSION, "run_id": run_id, "task": task, "cwd": cwd,
        "branch": branch, "pr": None, "coder": coder, "reviewer": reviewer,
        "reviewer_fallback": reviewer_fallback, "rounds": [],
        "outcome": {"verdict": None, "rounds": 0, "merged": None},
    }


def manifest_path(run_id):
    return os.path.join(RUNS_DIR, f"{run_id}.json")


def save_manifest(manifest):
    os.makedirs(RUNS_DIR, exist_ok=True)
    path = manifest_path(manifest["run_id"])
    fd, tmp = tempfile.mkstemp(dir=RUNS_DIR, prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    os.replace(tmp, path)


def load_manifest(run_id_or_path):
    path = run_id_or_path if str(run_id_or_path).endswith(".json") else manifest_path(run_id_or_path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_manifests():
    return sorted(glob.glob(os.path.join(RUNS_DIR, "*.json")))


def add_round(manifest, role, tool, session_id=None):
    """Start a new round (paired coder+reviewer rounds share the same `n`;
    a fresh coder round after a reviewer verdict starts the next `n`)."""
    if not manifest["rounds"]:
        n = 1
    else:
        last = manifest["rounds"][-1]
        n = last["n"] if (last["role"] == "coder" and role == "reviewer") else last["n"] + 1
    round_ = {"n": n, "role": role, "tool": tool, "session_id": session_id,
              "started": _now(), "ended": None}
    manifest["rounds"].append(round_)
    save_manifest(manifest)
    return round_


def close_round(manifest, round_, **fields):
    round_["ended"] = _now()
    round_.update(fields)
    save_manifest(manifest)


def close_run(manifest, verdict, merged=None):
    manifest["outcome"] = {
        "verdict": verdict,
        "rounds": manifest["rounds"][-1]["n"] if manifest["rounds"] else 0,
        "merged": merged,
    }
    save_manifest(manifest)


# ------------------------------------------------------------- cost join

def _parse_ts(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")


def round_cost(round_, summaries, pricing_mod, cwd=None):
    """Cost of one round: exact session-id match; else time-window overlap
    against summaries whose file mtime falls inside [started, ended] AND whose
    project label overlaps `cwd` (best-effort; returns 0.0 if nothing matches —
    never guesses)."""
    sid = round_.get("session_id")
    if sid:
        for s in summaries:
            if s.get("session_id") == sid:
                cost, _ = pricing_mod.cost_by_model(s.get("by_model", {}))
                return cost
    if not (round_.get("started") and round_.get("ended")):
        return 0.0
    start, end = _parse_ts(round_["started"]), _parse_ts(round_["ended"])
    total = 0.0
    for s in summaries:
        if cwd and s.get("project") and (cwd not in s["project"] and s["project"] not in cwd):
            continue
        mtime = s.get("mtime")
        if mtime is None:
            continue
        file_dt = datetime.utcfromtimestamp(mtime)
        if start <= file_dt <= end:
            c, _ = pricing_mod.cost_by_model(s.get("by_model", {}))
            total += c
    return total


def run_cost(manifest, summaries):
    """Total $ for a run, split by role: {"total":, "coder":, "reviewer":}."""
    import pricing as pricing_mod
    cwd = manifest.get("cwd")
    total, by_role = 0.0, {"coder": 0.0, "reviewer": 0.0}
    for r in manifest["rounds"]:
        c = round_cost(r, summaries, pricing_mod, cwd=cwd)
        total += c
        by_role[r["role"]] = by_role.get(r["role"], 0.0) + c
    return {"total": round(total, 4), "coder": round(by_role["coder"], 4),
            "reviewer": round(by_role["reviewer"], 4)}
```

`import pricing as pricing_mod` inside `run_cost` (rather than at module top) avoids a hard dependency for callers that only need the manifest read/write half; both `token-dashboard.py` and `run-cost.py` already put `scripts/` on `sys.path` before importing `run_manifest`, so the local import resolves correctly.

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_run_manifest.py -v`
Expected: 7 tests, all PASS

- [ ] **Step 5: Implement `scripts/run-cost.py`**

```python
#!/usr/bin/env python3
"""
run-cost.py — print a pair-loop run's cost so far.

Used by the pair-loop skill's per-round budget check (Plan: pair-loop-handoff-
skill) and standalone for inspecting a run.

Usage: python3 scripts/run-cost.py <run-id-or-manifest-path>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_manifest  # noqa: E402
import adapters.claude_code as claude_code  # noqa: E402
import adapters.codex as codex  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print("usage: run-cost.py <run-id-or-manifest-path>", file=sys.stderr)
        sys.exit(1)
    manifest = run_manifest.load_manifest(sys.argv[1])
    summaries = claude_code.scan(verbose=False) + codex.scan(verbose=False)
    result = run_manifest.run_cost(manifest, summaries)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Manual verification**

Run: `python3 -c "
import sys, os
sys.path.insert(0, 'scripts')
import run_manifest
m = run_manifest.new_manifest('smoke-test', 'manual check', os.getcwd(), 'main', 'claude', 'codex')
run_manifest.save_manifest(m)
print(open(run_manifest.manifest_path('smoke-test')).read())
os.remove(run_manifest.manifest_path('smoke-test'))
"`
Expected: prints valid JSON matching the schema, no traceback

- [ ] **Step 7: Commit**

```bash
git add scripts/run_manifest.py scripts/run-cost.py scripts/test_run_manifest.py
git commit -m "feat(manifest): pair-loop run schema v1, session-cost join, run-cost.py CLI"
```

---

### Task 8: Budgets — config-driven thresholds, oneline glyph, daemon notification

**Files:**
- Create: `scripts/_budget.py`
- Modify: `scripts/token-dashboard.py` — `_token_summary()`/`_oneline()` (post-Task-6 versions), `ensure_daemon()`, `_auto_refresh()`
- Test: `scripts/test_budget.py`

**Interfaces:**
- Produces: `_budget.WARN_FRACTION = 0.8`, `_budget.status_for(spend, limit) -> (fraction|None, level|None)`, `_budget.budget_summary(today_spend, week_spend) -> dict` (used by `build()`, Task 6), `_budget.maybe_notify(summary, today_str, notifier=None) -> list[str]` (fired threshold keys; `notifier` injectable for tests), `_budget.oneline_suffix(summary) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_budget.py
#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _budget
import _config


class TestBudget(unittest.TestCase):
    def setUp(self):
        self._orig_config = _config.CONFIG_PATH
        self._orig_alert = _budget.ALERT_STATE_PATH
        tmp = tempfile.mkdtemp()
        _config.CONFIG_PATH = os.path.join(tmp, "config.json")
        _budget.ALERT_STATE_PATH = os.path.join(tmp, "alert-state.json")

    def tearDown(self):
        _config.CONFIG_PATH = self._orig_config
        _budget.ALERT_STATE_PATH = self._orig_alert

    def test_status_for_no_limit_is_inert(self):
        frac, level = _budget.status_for(40, None)
        self.assertIsNone(frac)
        self.assertIsNone(level)

    def test_status_for_under_warn_threshold(self):
        frac, level = _budget.status_for(10, 50)
        self.assertIsNone(level)

    def test_status_for_warn_threshold(self):
        frac, level = _budget.status_for(41, 50)
        self.assertEqual(level, "warn")

    def test_status_for_alert_threshold(self):
        frac, level = _budget.status_for(51, 50)
        self.assertEqual(level, "alert")

    def test_budget_summary_absent_config_is_all_none(self):
        summary = _budget.budget_summary(10, 20)
        self.assertIsNone(summary["daily"]["limit"])
        self.assertIsNone(summary["daily"]["level"])

    def test_budget_summary_uses_config(self):
        with open(_config.CONFIG_PATH, "w") as f:
            json.dump({"budget": {"daily_usd": 50, "weekly_usd": 250}}, f)
        summary = _budget.budget_summary(41, 100)
        self.assertEqual(summary["daily"]["level"], "warn")
        self.assertIsNone(summary["weekly"]["level"])

    def test_maybe_notify_fires_once_per_day(self):
        summary = {"daily": {"limit": 50, "spend": 51, "fraction": 1.02, "level": "alert"},
                   "weekly": {"limit": None, "spend": 0, "fraction": None, "level": None}}
        fired_msgs = []
        fired = _budget.maybe_notify(summary, "2026-07-09", notifier=fired_msgs.append)
        self.assertEqual(fired, ["daily_alert"])
        self.assertEqual(len(fired_msgs), 1)
        # same day again -> deduped
        fired2 = _budget.maybe_notify(summary, "2026-07-09", notifier=fired_msgs.append)
        self.assertEqual(fired2, [])
        self.assertEqual(len(fired_msgs), 1)

    def test_oneline_suffix_shows_glyph_only_when_configured(self):
        no_budget = _budget.budget_summary(10, 20)
        self.assertEqual(_budget.oneline_suffix(no_budget), "")
        with open(_config.CONFIG_PATH, "w") as f:
            json.dump({"budget": {"daily_usd": 50}}, f)
        warn_summary = _budget.budget_summary(41, 20)
        self.assertIn("⚠", _budget.oneline_suffix(warn_summary))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_budget.py`
Expected: `ModuleNotFoundError: No module named '_budget'`

- [ ] **Step 3: Implement `scripts/_budget.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_budget.py -v`
Expected: 8 tests, all PASS

- [ ] **Step 5: Wire into `--oneline` and the daemon**

Modify `scripts/token-dashboard.py`'s `_token_summary()` / `_oneline()` / `_auto_refresh()` (post-Task-6 line numbers — locate by function name):

```python
def _token_summary():
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
    cost, _ = pricing.cost_by_model({m: v for m, v in tot.items()} and _bucket_by_model(cc_cache, cx_cache))
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
```

Simplify: replace the awkward `cost, _ = pricing.cost_by_model(... and _bucket_by_model(...))` line with a plain call:

```python
    by_model_total = _bucket_by_model(cc_cache, cx_cache)
    cost, _ = pricing.cost_by_model(by_model_total)
```

(place this line before the `today_cost`/`week_cost` computation and delete the earlier malformed one-liner).

Update `_oneline()` (unchanged signature, now benefits from the richer `_token_summary()`):

```python
def _oneline():
    """Fast cache-only summary line for shell startup. Silent if no cache yet."""
    s = _token_summary()
    if s:
        print(f"100xPrism tokens (as of last scan): {s} · run `100x-tokens` for the dashboard")
```

Update `_auto_refresh()` (inside `main()`) to fire the daemon notification after each rebuild:

```python
    def _auto_refresh():
        while True:
            time.sleep(REFRESH_SECONDS)
            try:
                data = _rebuild()
                today_str = datetime.now().strftime("%Y-%m-%d")
                _budget.maybe_notify(data["budget"], today_str)
            except Exception:
                pass
```

- [ ] **Step 6: Manual verification**

Run: `python3 scripts/token-dashboard.py --oneline`
Expected: prints a line (or nothing if no cache yet) with no traceback; if `~/.100xprism/config.json` has a `budget.daily_usd` set, the line includes a `today $.../$...` fragment.

- [ ] **Step 7: Commit**

```bash
git add scripts/_budget.py scripts/token-dashboard.py scripts/test_budget.py
git commit -m "feat(budget): config-driven thresholds, oneline glyph, daemon osascript alert"
```

---

### Task 9: Suggestions engine (`scripts/_suggest.py`)

**Files:**
- Create: `scripts/_suggest.py`
- Test: `scripts/test_suggest.py`

**Interfaces:**
- Produces: `_suggest.Suggestion` (namedtuple `impact_usd, message`), `_suggest.RULES` (list of rule functions), `_suggest.suggestions(data: dict, limit=5) -> list[Suggestion]`, sorted by `impact_usd` descending.
- Consumes: the `build()` dataset shape from Task 6 (`bloat`, `sessions`, `by_session`, `totals`, `total_cost`, `composition`, `by_skill`, `handoff_runs`).

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_suggest.py
#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _suggest


def _base_data(**overrides):
    d = {
        "bloat": {"median": 5000, "avg": 5000, "samples": 10},
        "sessions": 10,
        "by_session": [],
        "totals": {"input": 100, "output": 100, "cache_read": 100, "cache_write": 0},
        "total_cost": 10.0,
        "composition": [],
        "by_skill": [],
        "handoff_runs": [],
    }
    d.update(overrides)
    return d


class TestSuggest(unittest.TestCase):
    def test_no_suggestions_for_healthy_data(self):
        self.assertEqual(_suggest.suggestions(_base_data()), [])

    def test_startup_bloat_rule_fires_above_threshold(self):
        data = _base_data(bloat={"median": 20000, "avg": 20000, "samples": 10})
        out = _suggest.suggestions(data)
        self.assertTrue(any("trim CLAUDE.md" in s.message for s in out))

    def test_startup_bloat_rule_silent_below_threshold(self):
        data = _base_data(bloat={"median": 5000, "avg": 5000, "samples": 10})
        out = _suggest.suggestions(data)
        self.assertFalse(any("trim CLAUDE.md" in s.message for s in out))

    def test_model_tiering_rule_fires_for_expensive_light_sessions(self):
        data = _base_data(by_session=[
            {"session_id": "a", "tool": "claude-code", "msgs": 2, "cost": 0.80},
            {"session_id": "b", "tool": "claude-code", "msgs": 2, "cost": 0.75},
        ])
        out = _suggest.suggestions(data)
        self.assertTrue(any("re-tier" in s.message for s in out))

    def test_cache_hygiene_rule_fires_for_low_cache_share(self):
        data = _base_data(totals={"input": 900, "output": 100, "cache_read": 100, "cache_write": 0})
        out = _suggest.suggestions(data)
        self.assertTrue(any("Cache reads" in s.message for s in out))

    def test_read_delegation_rule_fires_for_high_files_read_share(self):
        data = _base_data(composition=[["code / files read", 400000, 40.0], ["your prompts", 600000, 60.0]])
        out = _suggest.suggestions(data)
        self.assertTrue(any("Explore subagents" in s.message for s in out))

    def test_skill_outlier_rule_fires_for_dominant_expensive_skill(self):
        data = _base_data(by_skill=[
            {"skill": "expensive-skill", "cost": 30.0, "invocations": 3, "exact": True},
            {"skill": "cheap-skill-a", "cost": 1.0, "invocations": 5, "exact": True},
            {"skill": "cheap-skill-b", "cost": 1.2, "invocations": 6, "exact": True},
        ])
        out = _suggest.suggestions(data)
        self.assertTrue(any("expensive-skill" in s.message for s in out))

    def test_loop_cap_rule_fires_for_repeated_zero_finding_final_rounds(self):
        data = _base_data(handoff_runs=[
            {"run_id": "r1", "rounds": 3, "reviewer_cost": 0.5, "final_round_findings": 0},
            {"run_id": "r2", "rounds": 2, "reviewer_cost": 0.4, "final_round_findings": 0},
        ])
        out = _suggest.suggestions(data)
        self.assertTrue(any("lower the round cap" in s.message for s in out))

    def test_suggestions_sorted_by_impact_descending(self):
        data = _base_data(
            bloat={"median": 20000, "avg": 20000, "samples": 10},
            totals={"input": 900, "output": 100, "cache_read": 100, "cache_write": 0},
        )
        out = _suggest.suggestions(data)
        impacts = [s.impact_usd for s in out]
        self.assertEqual(impacts, sorted(impacts, reverse=True))

    def test_limit_caps_results(self):
        data = _base_data(
            bloat={"median": 20000, "avg": 20000, "samples": 10},
            totals={"input": 900, "output": 100, "cache_read": 100, "cache_write": 0},
            composition=[["code / files read", 400000, 40.0]],
        )
        out = _suggest.suggestions(data, limit=1)
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_suggest.py`
Expected: `ModuleNotFoundError: No module named '_suggest'`

- [ ] **Step 3: Implement `scripts/_suggest.py`**

```python
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
    if share >= 0.70:
        return None
    impact = inp * 0.013 / 1  # rough $/token delta between input and cache-read rates
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_suggest.py -v`
Expected: 9 tests, all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/_suggest.py scripts/test_suggest.py
git commit -m "feat(suggest): rule-based offline cost-reduction suggestions"
```

---

### Task 10: Dashboard UI redesign — KPI strip, donut, stacked area, tables, 30s refresh

**Files:**
- Modify: `scripts/token-dashboard.py` — the `PAGE` string (dashboard HTML/CSS/JS) and `_client_data()`
- Modify: `docs/token-optimization.md` (drop stale `/api/value` and flat-`RATES` references, document the new attribution/budget/suggestion features)
- Modify: `docs/USAGE.md:407-432` ("Monitoring token usage" section)
- Modify: `README.md:86-102` ("Token & value economics" section)

**Interfaces:**
- Consumes: every dataset key produced by Task 6 (`budget`, `by_session`, `by_skill`, `main_subagent_split`, `handoff_runs`, `fallback_pct`, `suggestions`).
- No behavior contract beyond "renders without throwing and reflects the dataset" — this task is UI wiring, verified visually + via `--print`/`--oneline`, not unit tests (consistent with the existing file's lack of JS tests).

- [ ] **Step 1: Update `_client_data()` to pass through the new keys**

`scripts/token-dashboard.py`'s `_client_data()` currently trims only `by_project_day_cost`. Extend it to leave the new keys untouched (no trimming needed — `by_session` is already capped at 50, `by_skill`/`handoff_runs` are naturally small):

```python
def _client_data(data):
    """Token data for the browser. Trim per-day cost to the dirs we chart."""
    top = [d["label"] for d in data.get("directories", [])[:12]]
    bpd = {k: v for k, v in data.get("by_project_day_cost", {}).items() if k in top}
    out = {k: v for k, v in data.items() if k != "by_project_day_cost"}
    out["by_project_day_cost"] = bpd
    return out
```

(No change needed — confirm by reading; the dict comprehension already passes through every other key unmodified.)

- [ ] **Step 2: Add new SVG chart functions to the `PAGE` JS**

Insert after the existing `costByDir` function (`token-dashboard.py`, in the `<script>` block):

```javascript
function donut(totals){
 const parts=[['cache_read',totals.cache_read,'var(--cr)'],['cache_write',totals.cache_write,'var(--cw)'],
   ['input',totals.input,'var(--in)'],['output',totals.output,'var(--out)']];
 const sum=parts.reduce((a,p)=>a+p[1],0); if(!sum) return emptyState('No token usage yet.');
 const W=180,H=180,cx=90,cy=90,r=70,rInner=42; let angle=-Math.PI/2, path='';
 for(const[k,v,c]of parts){ if(!v) continue;
   const frac=v/sum, a1=angle, a2=angle+frac*2*Math.PI; angle=a2;
   const x1=cx+r*Math.cos(a1),y1=cy+r*Math.sin(a1),x2=cx+r*Math.cos(a2),y2=cy+r*Math.sin(a2);
   const ix1=cx+rInner*Math.cos(a1),iy1=cy+rInner*Math.sin(a1),ix2=cx+rInner*Math.cos(a2),iy2=cy+rInner*Math.sin(a2);
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
```

Add the daily-volume chart:

```javascript
function stackedByModel(d){
 const days=d.by_day.map(r=>r[0]); if(!days.length) return emptyState('No dated cost yet.');
 const models=[...new Set(d.by_model.map(r=>r[0]))].slice(0,6);
 const CC=['#58a6ff','#f778ba','#3fb950','#d29922','#a371f7','#ff7b72'];
 const W=520,H=200,PL=46,PB=30,PR=28,PT=20;
 // approximate per-day-per-model split using each day's overall mix (dataset does not
 // ship a full by_day_model matrix to the client to keep payload small) — the by_model
 // legend still reflects exact totals; this chart shows RELATIVE daily shape.
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
```

- [ ] **Step 3: Wire the new sections into `render()`**

Modify the `render(d)` function: replace the four-card block + add budget/donut/handoff/attribution/suggestions sections. Insert after the existing `cards2` block (leverage/cost-over-time/purpose-split/cost-by-dir) and before `dirsTable`:

```javascript
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
```

Update the client refresh interval (`load(); setInterval(load, 300000);` near the end of the script) to 30 s:

```javascript
load();
setInterval(load, 30000);  // auto-refresh every 30s — matches the server's 30s rescan cadence
```

Also remove the now-dead reference: search the `PAGE` string for `d.rates` — the old code never actually referenced `d.rates` in JS (it was display-only via the `'est. cost','$'+d.total_cost...` card), so no removal is needed; confirm with `grep -n "d.rates" scripts/token-dashboard.py` returning nothing.

- [ ] **Step 4: Manual verification**

Run: `python3 scripts/token-dashboard.py --no-open &` then `sleep 2 && curl -s http://127.0.0.1:8787/api/data | python3 -m json.tool | head -50` — confirm `budget`, `by_session`, `by_skill`, `handoff_runs`, `suggestions`, `fallback_pct`, `main_subagent_split` keys are present and well-formed. Then `curl -s http://127.0.0.1:8787/ | grep -c "donut\|stackedByModel\|budgetBar"` — expect 3+ matches. Kill the background server: `kill %1`.

Open `http://127.0.0.1:8787/` in a browser (or screenshot via the `run` skill if available) to visually confirm the new sections render without a blank page or console error.

- [ ] **Step 5: Update docs**

`docs/token-optimization.md`: replace the "Value, not just cost" and adapter-stub paragraphs to reflect the real Codex adapter, per-model pricing, and the new attribution/suggestions/budget features; remove the `/api/value` non-existent-route confusion (there never was one — no change needed there) and update "No tool attributes tokens to a specific skill/plugin" (no longer true — replace with a description of `attributionSkill`-based exact attribution + the command-marker fallback).

`docs/USAGE.md:407-432`: update the "Monitoring token usage" section with the budget config example and the suggestions panel.

`README.md:86-102`: mention Codex cost tracking, budgets, and suggestions alongside the existing token/value economics blurb.

- [ ] **Step 6: Run the full test suite + gate**

Run: `node --test && python3 scripts/test_pricing.py && python3 scripts/test_config.py && python3 scripts/test_claude_code_adapter.py && python3 scripts/test_codex_adapter.py && python3 scripts/test_value.py && python3 scripts/test_run_manifest.py && python3 scripts/test_budget.py && python3 scripts/test_suggest.py`
Expected: everything PASS

Run: `python3 hooks/gate-pass.py` (own bash call, not chained with the commit)

- [ ] **Step 7: Commit**

```bash
git add scripts/token-dashboard.py docs/token-optimization.md docs/USAGE.md README.md
git commit -m "feat(dashboard): compact redesign — budget bar, donut, daily volume, session/skill/handoff tables, suggestions, 30s refresh"
```

---

## Sequencing note for Plan 2

`docs/superpowers/plans/2026-07-09-pair-loop-handoff-skill.md` depends on `scripts/run_manifest.py` (Task 7), `scripts/run-cost.py` (Task 7), and the `pair_loop` section of `scripts/_config.py` (Task 2) — all landed by the end of this plan. Execute this plan to completion (through Task 10) before starting Plan 2.
