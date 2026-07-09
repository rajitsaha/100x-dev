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

    def test_attribution_skill_interrupts_marker_segment_then_marker_resumes(self):
        # A `<command-name>` marker opens a boundary-heuristic segment. A line
        # with a real `attributionSkill` in the middle of that segment must be
        # credited exactly to its own skill (not the marker), and must NOT
        # clear the carried-forward marker state — the marker resumes crediting
        # on the next line that has no attributionSkill and no new marker.
        path = self._write([
            _line("user", "<command-name>/model</command-name>\n<command-message>model</command-message>"),
            _line("assistant", "switched model", usage={"input_tokens": 30, "output_tokens": 3,
                                                          "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}),
            _line("assistant", "invoking skill", usage={"input_tokens": 200, "output_tokens": 20,
                                                          "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                  attribution_skill="superpowers:brainstorming"),
            _line("assistant", "back to model work", usage={"input_tokens": 15, "output_tokens": 2,
                                                              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}),
        ])
        s = claude_code.parse_file(path)
        # exact-attribution line goes only to its own skill's bucket
        self.assertEqual(s["by_skill"]["superpowers:brainstorming"]["input"], 200)
        self.assertIn("superpowers:brainstorming", s["skill_exact"])
        # the marker's bucket is unaffected by the attributionSkill line's usage
        # and resumes on the line after it: 30 (before) + 15 (after) = 45
        self.assertEqual(s["by_skill"]["/model"]["input"], 45)
        self.assertNotIn("/model", s["skill_exact"])

    def test_two_command_markers_in_sequence_second_marker_takes_over(self):
        # Two different `<command-name>` markers appear one after another;
        # usage after the second marker must go to the second marker's key,
        # not leak into the first marker's bucket.
        path = self._write([
            _line("user", "<command-name>/model</command-name>\n<command-message>model</command-message>"),
            _line("assistant", "switched model", usage={"input_tokens": 10, "output_tokens": 1,
                                                          "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}),
            _line("user", "<command-name>/commit</command-name>\n<command-message>commit</command-message>"),
            _line("assistant", "committing", usage={"input_tokens": 25, "output_tokens": 4,
                                                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}),
        ])
        s = claude_code.parse_file(path)
        self.assertEqual(s["by_skill"]["/model"]["input"], 10)
        self.assertEqual(s["by_skill"]["/commit"]["input"], 25)
        self.assertNotIn("/commit", s["skill_exact"])
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
