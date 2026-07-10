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
        self.assertEqual(rates, next(r for k, r in pricing.RATES if k == "sonnet"))

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
        sonnet_rates = next(r for k, r in pricing.RATES if k == "sonnet")
        expected_sonnet = 1_000_000 / 1_000_000 * sonnet_rates["input"]
        expected_fallback = 500_000 / 1_000_000 * pricing._FALLBACK_RATES["output"]
        self.assertAlmostEqual(total, expected_sonnet + expected_fallback, places=6)
        self.assertEqual(fallback_tokens, 500_000)

    def test_gpt_5_pattern_matches_dotted_minor_versions(self):
        rates, is_fallback = pricing.rates_for_model("gpt-5.5")
        self.assertFalse(is_fallback)
        self.assertEqual(rates, next(r for k, r in pricing.RATES if k == "gpt-5"))


if __name__ == "__main__":
    unittest.main()
