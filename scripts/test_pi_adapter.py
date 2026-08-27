#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adapters.pi as pi  # noqa: E402


class TestPiAdapter(unittest.TestCase):
    def test_scan_missing_dir_is_empty(self):
        original = pi.SOURCE_DIR
        pi.SOURCE_DIR = "/definitely/missing/pi-sessions"
        try:
            self.assertEqual(pi.scan(), [])
        finally:
            pi.SOURCE_DIR = original

    def test_parse_file_extracts_usage_and_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sess.jsonl")
            with open(path, "w") as f:
                f.write(json.dumps({
                    "session_id": "abc",
                    "cwd": tmp,
                    "timestamp": "2026-08-18T12:00:00Z",
                    "model": "gemini-2.5-flash",
                    "usage": {"input_tokens": 10, "output_tokens": 4, "cached_tokens": 2},
                }) + "\n")
            row = pi.parse_file(path)
        self.assertEqual(row["session_id"], "abc")
        self.assertEqual(row["tool"], "pi")
        self.assertEqual(row["totals"]["input"], 10)
        self.assertEqual(row["totals"]["output"], 4)
        self.assertEqual(row["totals"]["cache_read"], 2)
        self.assertIn("gemini-2.5-flash", row["by_model"])
        self.assertEqual(row["by_day"]["2026-08-18"]["input"], 10)

    def test_parse_file_preserves_native_camel_case_cache_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "native.jsonl")
            with open(path, "w") as f:
                f.write(json.dumps({
                    "sessionId": "native",
                    "timestamp": "2026-08-18T12:00:00Z",
                    "usage": {"input": 100, "output": 50, "cacheRead": 40, "cacheWrite": 5},
                }) + "\n")
            row = pi.parse_file(path)
        self.assertEqual(row["totals"], {
            "input": 100, "output": 50, "cache_read": 40, "cache_write": 5,
        })

    def test_parse_file_without_usage_stays_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "empty.jsonl")
            with open(path, "w") as f:
                f.write(json.dumps({"role": "user", "content": "hi"}) + "\n")
            row = pi.parse_file(path)
        self.assertEqual(row["totals"], {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0})
        self.assertEqual(row["msgs"], 0)


if __name__ == "__main__":
    unittest.main()
