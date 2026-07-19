#!/usr/bin/env python3
import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapters import antigravity, cursor


class CursorActivityTest(unittest.TestCase):
    def test_collects_messages_without_inventing_tokens(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "projects", "Users-test-project",
                                "agent-transcripts", "session-1", "session-1.jsonl")
            os.makedirs(os.path.dirname(path))
            with open(path, "w") as f:
                f.write(json.dumps({"role": "user", "message": {"content": "fix it"}}) + "\n")
                f.write(json.dumps({"role": "assistant", "message": {"content": "done"}}) + "\n")
            real_project = os.path.join(root, "real-project")
            os.makedirs(real_project)
            row = cursor.parse_file(path, {"-Users-test-project": real_project})
            self.assertTrue(row["activity_only"])
            self.assertEqual(row["activity"]["messages"], 2)
            self.assertEqual(row["activity"]["user_messages"], 1)
            self.assertEqual(sum(row["totals"].values()), 0)
            self.assertEqual(row["tool"], "cursor")
            self.assertEqual(row["cwd"], real_project)

    def test_scan_absent_is_empty(self):
        original = cursor.SOURCE_DIR
        cursor.SOURCE_DIR = "/definitely/missing/cursor"
        try:
            self.assertEqual(cursor.scan(), [])
        finally:
            cursor.SOURCE_DIR = original


class AntigravityActivityTest(unittest.TestCase):
    def test_maps_artifact_session_to_workspace_without_tokens(self):
        with tempfile.TemporaryDirectory() as root:
            session_id = "11111111-2222-3333-4444-555555555555"
            source = os.path.join(root, "antigravity")
            brain = os.path.join(source, "brain", session_id)
            conversations = os.path.join(source, "conversations")
            workspace_root = os.path.join(root, "workspace-storage")
            workspace = os.path.join(workspace_root, "abc")
            project = os.path.join(root, "project")
            os.makedirs(brain)
            os.makedirs(conversations)
            os.makedirs(workspace)
            os.makedirs(project)
            with open(os.path.join(brain, "task.md.metadata.json"), "w") as f:
                json.dump({"updatedAt": "2026-07-18T01:02:03Z"}, f)
            with open(os.path.join(conversations, session_id + ".pb"), "wb") as f:
                f.write(b"protobuf")
            with open(os.path.join(workspace, "workspace.json"), "w") as f:
                json.dump({"folder": "file://" + project}, f)
            con = sqlite3.connect(os.path.join(workspace, "state.vscdb"))
            con.execute("CREATE TABLE ItemTable (key TEXT, value BLOB)")
            con.execute("INSERT INTO ItemTable VALUES (?, ?)",
                        ("antigravity.session", ("session=" + session_id).encode()))
            con.commit()
            con.close()

            original = antigravity.SOURCE_DIR, antigravity.WORKSPACE_DIR
            antigravity.SOURCE_DIR, antigravity.WORKSPACE_DIR = source, workspace_root
            try:
                rows = antigravity.scan()
            finally:
                antigravity.SOURCE_DIR, antigravity.WORKSPACE_DIR = original
            row = rows[0]
            self.assertEqual(row["cwd"], project)
            self.assertEqual(row["activity"]["day"], "2026-07-18")
            self.assertEqual(row["activity"]["artifacts"], 1)
            self.assertEqual(sum(row["totals"].values()), 0)
            self.assertTrue(row["activity_only"])


if __name__ == "__main__":
    unittest.main()
