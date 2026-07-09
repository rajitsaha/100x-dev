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


def _reset_rollout_lines():
    """Simulates a mid-session context-compaction reset: event 2's cumulative
    values are LOWER than event 1's, then event 3 resumes counting up from
    event 2's (post-reset) baseline."""
    return [
        json.dumps({"timestamp": "2026-07-09T10:00:00.000Z", "type": "session_meta",
                    "payload": {"session_id": "reset-1", "id": "reset-1",
                                "cwd": "/Users/x/proj"}}) + "\n",
        json.dumps({"timestamp": "2026-07-09T10:00:01.000Z", "type": "turn_context",
                    "payload": {"model": "gpt-5.5"}}) + "\n",
        # event 1: baseline -> input=800, cache_read=200, output=100
        json.dumps({"timestamp": "2026-07-09T10:00:05.000Z", "type": "event_msg",
                    "payload": {"type": "token_count", "info": {"total_token_usage": {
                        "input_tokens": 1000, "cached_input_tokens": 200,
                        "output_tokens": 100, "total_tokens": 1100}}}}) + "\n",
        # event 2: RESET — all three fields drop below event 1's readings.
        # Should be treated as a new baseline: input=400, cache_read=100, output=50
        json.dumps({"timestamp": "2026-07-09T10:05:00.000Z", "type": "event_msg",
                    "payload": {"type": "token_count", "info": {"total_token_usage": {
                        "input_tokens": 500, "cached_input_tokens": 100,
                        "output_tokens": 50, "total_tokens": 550}}}}) + "\n",
        # event 3: deltas against event 2's (post-reset) baseline, NOT event 1's.
        # input=max((900-500)-(300-100),0)=200, cache_read=300-100=200, output=120-50=70
        json.dumps({"timestamp": "2026-07-09T10:06:00.000Z", "type": "event_msg",
                    "payload": {"type": "token_count", "info": {"total_token_usage": {
                        "input_tokens": 900, "cached_input_tokens": 300,
                        "output_tokens": 120, "total_tokens": 1200}}}}) + "\n",
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

    def test_cumulative_counter_reset_treated_as_new_baseline(self):
        s = codex.parse_file(self._write(_reset_rollout_lines()))
        totals = s["totals"]

        # (a) no negative numbers anywhere in totals
        for key, val in totals.items():
            self.assertGreaterEqual(val, 0, f"{key} went negative: {val}")

        # (b) the reset event's tokens are still counted, not clamped to 0:
        #     event1 (800/200/100) + event2-as-new-baseline (400/100/50)
        #     + event3-vs-event2 (200/200/70)
        self.assertEqual(totals["input"], 800 + 400 + 200)
        self.assertEqual(totals["cache_read"], 200 + 100 + 200)
        self.assertEqual(totals["output"], 100 + 50 + 70)

        # (c) event 3 deltas against event 2's (post-reset) baseline, not
        #     event 1's pre-reset baseline — verified implicitly by the exact
        #     totals above (a delta against event 1 would give different,
        #     larger numbers for input/output and wrongly-clamped negatives
        #     for cache_read).
        self.assertEqual(s["msgs"], 3)

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
