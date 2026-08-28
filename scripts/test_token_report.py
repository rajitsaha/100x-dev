import json
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TokenReportTests(unittest.TestCase):
    def test_registry_declares_measurement_kind_for_every_tool(self):
        from adapters.registry import collectors

        rows = collectors()
        self.assertEqual([row.tool for row in rows], [
            "claude-code", "codex", "cursor", "antigravity", "pi",
        ])
        self.assertEqual({row.measurement for row in rows}, {"exact", "activity_only", "best_effort"})

    def test_report_never_prices_activity_only_rows(self):
        import token_report

        class Fake:
            tool = "cursor"
            measurement = "activity_only"
            source = "fixture"
            limitations = ("no counters",)

            @staticmethod
            def scan(verbose=False, **kwargs):
                return [{
                    "tool": "cursor",
                    "session_id": "s1",
                    "project": "p",
                    "totals": {"input": 100, "output": 20, "cache_read": 0, "cache_write": 0},
                    "activity_only": True,
                    "activity": {"messages": 2},
                }]

        report = token_report.build_report([Fake()])
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["totals"], {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0})
        self.assertEqual(report["sources"][0]["measurement"], "activity_only")
        self.assertEqual(report["sources"][0]["sessions"], 1)

    def test_report_preserves_exact_counters_and_provenance(self):
        import token_report

        class Fake:
            tool = "codex"
            measurement = "exact"
            source = "fixture-jsonl"
            limitations = ("cache writes unavailable",)

            @staticmethod
            def scan(verbose=False, **kwargs):
                return [{
                    "tool": "codex",
                    "session_id": "s2",
                    "project": "p",
                    "totals": {"input": 10, "output": 4, "cache_read": 3, "cache_write": 0},
                }]

        report = token_report.build_report([Fake()])
        self.assertEqual(report["totals"]["input"], 10)
        self.assertEqual(report["sources"][0]["source"], "fixture-jsonl")
        self.assertEqual(report["sources"][0]["limitations"], ["cache writes unavailable"])
        json.dumps(report)


if __name__ == "__main__":
    unittest.main()
