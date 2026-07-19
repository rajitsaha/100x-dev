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
        "totals": {"input": 100, "output": 100, "cache_read": 300, "cache_write": 0},
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
        self.assertTrue(any("fixed tokens" in s.message for s in out))

    def test_startup_bloat_rule_silent_below_threshold(self):
        data = _base_data(bloat={"median": 5000, "avg": 5000, "samples": 10})
        out = _suggest.suggestions(data)
        self.assertFalse(any("fixed tokens" in s.message for s in out))

    def test_model_tiering_rule_fires_for_expensive_light_sessions(self):
        data = _base_data(by_session=[
            {"session_id": "a", "tool": "claude-code", "msgs": 2, "cost": 0.80,
             "models": ["claude-opus-4-8"], "model_costs": {"claude-opus-4-8": 0.80}},
            {"session_id": "b", "tool": "claude-code", "msgs": 2, "cost": 0.75,
             "models": ["claude-fable-5"], "model_costs": {"claude-fable-5": 0.75}},
        ])
        out = _suggest.suggestions(data)
        self.assertTrue(any("premium models" in s.message for s in out))

    def test_cache_hygiene_rule_fires_for_low_cache_share(self):
        data = _base_data(totals={"input": 900, "output": 100, "cache_read": 100, "cache_write": 0})
        out = _suggest.suggestions(data)
        self.assertTrue(any("Cache reads" in s.message for s in out))

    def test_read_delegation_rule_fires_for_high_files_read_share(self):
        data = _base_data(composition=[["code / files read", 400000, 40.0], ["your prompts", 600000, 60.0]])
        out = _suggest.suggestions(data)
        self.assertTrue(any("raw file reads" in s.message for s in out))

    def test_skill_outlier_rule_fires_for_dominant_expensive_skill(self):
        data = _base_data(by_skill=[
            {"skill": "expensive-skill", "cost": 30.0, "invocations": 3, "exact": True},
            {"skill": "cheap-skill-a", "cost": 1.0, "invocations": 5, "exact": True},
            {"skill": "cheap-skill-b", "cost": 1.2, "invocations": 6, "exact": True},
        ])
        out = _suggest.suggestions(data)
        self.assertTrue(any("expensive-skill" in s.message for s in out))

    def test_output_rule_preserves_reasoning_and_tools(self):
        data = _base_data(cost_by_purpose={"input": 1.0, "output": 8.0,
                                           "cache_read": 1.0, "cache_write": 0.0})
        out = _suggest.suggestions(data)
        suggestion = next(s for s in out if s.title == "Compress narration, not reasoning")
        self.assertIn("tool calls", suggestion.action)

    def test_loop_cap_rule_fires_for_repeated_zero_finding_final_rounds(self):
        data = _base_data(handoff_runs=[
            {"run_id": "r1", "rounds": 3, "reviewer_cost": 0.5, "final_round_findings": 0},
            {"run_id": "r2", "rounds": 2, "reviewer_cost": 0.4, "final_round_findings": 0},
        ])
        out = _suggest.suggestions(data)
        self.assertTrue(any("zero-finding" in s.message for s in out))

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
