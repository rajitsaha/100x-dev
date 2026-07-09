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
