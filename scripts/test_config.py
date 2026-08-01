#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

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
        self.assertEqual(cfg["github"]["enabled"], False)
        self.assertEqual(cfg["github"]["max_repos"], 12)
        self.assertEqual(cfg["github"]["users"], [])
        self.assertEqual(cfg["github"]["repos"], [])
        self.assertEqual(cfg["github"]["max_pr_file_fetches_per_repo"], 3)

    def test_partial_user_config_merges_over_defaults(self):
        with open(_config.CONFIG_PATH, "w") as f:
            json.dump({"budget": {"daily_usd": 50}}, f)
        cfg = _config.load_config()
        self.assertEqual(cfg["budget"]["daily_usd"], 50)
        self.assertIsNone(cfg["budget"]["weekly_usd"])  # untouched default
        self.assertEqual(cfg["pair_loop"]["reviewer"], "codex")  # untouched section
        self.assertEqual(cfg["github"]["max_prs_per_repo"], 30)  # untouched section

    def test_github_config_override(self):
        with open(_config.CONFIG_PATH, "w") as f:
            json.dump({"github": {"enabled": True, "max_repos": 3,
                                  "users": ["octocat"],
                                  "repos": ["acme/example-service"]}}, f)
        cfg = _config.load_config()
        self.assertEqual(cfg["github"]["enabled"], True)
        self.assertEqual(cfg["github"]["max_repos"], 3)
        self.assertEqual(cfg["github"]["users"], ["octocat"])
        self.assertEqual(cfg["github"]["repos"], ["acme/example-service"])
        self.assertEqual(cfg["github"]["max_prs_per_repo"], 30)
        self.assertEqual(cfg["github"]["max_pr_file_fetches_per_repo"], 3)

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

    def test_non_dict_section_value_falls_back_to_default(self):
        """Important #3 regression: a user config like {"budget": null} — plausible,
        a user might write this believing it "disables" the section — must not
        be passed through as-is (that crashes every caller that does
        cfg["budget"].get(...)). It should silently keep the default dict for
        that section, consistent with the malformed-whole-file contract."""
        with open(_config.CONFIG_PATH, "w") as f:
            json.dump({"budget": None, "pair_loop": {"coder": "codex"}}, f)
        cfg = _config.load_config()
        self.assertIsInstance(cfg["budget"], dict)
        self.assertEqual(cfg["budget"], _config.DEFAULTS["budget"])
        # unaffected sibling section still applies its override normally
        self.assertEqual(cfg["pair_loop"]["coder"], "codex")
        self.assertEqual(cfg["pair_loop"]["reviewer"], "codex")  # untouched default
        # must not raise when callers do cfg["budget"].get(...)
        self.assertIsNone(cfg["budget"].get("daily_usd"))

class TestNestedMerge(unittest.TestCase):
    """pair_loop.fallback_models is the first nested dict in the schema.

    A shallow update() would replace it wholesale, so overriding one vendor
    would silently drop the other and fail at lookup time — exactly when the
    fallback matters most.
    """

    def _load_with(self, user_cfg):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(user_cfg, f)
            with mock.patch.object(_config, "CONFIG_PATH", path):
                return _config.load_config()

    def test_partial_nested_override_keeps_other_keys(self):
        cfg = self._load_with({"pair_loop": {"fallback_models": {"claude": "opus"}}})
        self.assertEqual(cfg["pair_loop"]["fallback_models"]["claude"], "opus")
        self.assertEqual(cfg["pair_loop"]["fallback_models"]["codex"], "gpt-5.6-luna",
                         "overriding one vendor must not drop the other")

    def test_sibling_keys_still_default(self):
        cfg = self._load_with({"pair_loop": {"fallback_models": {"codex": "gpt-5.5"}}})
        self.assertEqual(cfg["pair_loop"]["coder"], "claude")
        self.assertEqual(cfg["pair_loop"]["max_rounds"], 3)

    def test_returned_config_is_not_aliased_to_defaults(self):
        # A shallow copy would share the nested dict with DEFAULTS, so a caller
        # mutating its config would corrupt defaults process-wide.
        cfg = self._load_with({})
        cfg["pair_loop"]["fallback_models"]["claude"] = "MUTATED"
        self.assertEqual(_config.DEFAULTS["pair_loop"]["fallback_models"]["claude"], "sonnet")

if __name__ == "__main__":
    unittest.main()
