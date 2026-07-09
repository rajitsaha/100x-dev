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
