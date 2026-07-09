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
