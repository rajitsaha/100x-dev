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

    def test_scan_collects_flat_and_nested_jsonl_only(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "projects")
            project = os.path.join(source, "Users-test-project", "agent-transcripts")
            nested = os.path.join(project, "session-nested")
            os.makedirs(nested)
            with open(os.path.join(project, "session-flat.jsonl"), "w") as f:
                f.write(json.dumps({"role": "user", "message": "flat"}) + "\n")
            with open(os.path.join(nested, "session-nested.jsonl"), "w") as f:
                f.write(json.dumps({"role": "assistant", "message": "nested"}) + "\n")
            with open(os.path.join(project, "legacy.txt"), "w") as f:
                f.write("legacy transcript\n")

            original = cursor.SOURCE_DIR
            cursor.SOURCE_DIR = source
            try:
                rows = cursor.scan()
            finally:
                cursor.SOURCE_DIR = original

            self.assertEqual({row["session_id"] for row in rows},
                             {"session-flat", "session-nested"})
            self.assertEqual(sum(row["activity"]["messages"] for row in rows), 2)

    def test_unresolved_project_uses_cursor_slug_label(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "projects", "Users-missing-project",
                                "agent-transcripts", "session.jsonl")
            os.makedirs(os.path.dirname(path))
            with open(path, "w") as f:
                f.write(json.dumps({"role": "user", "message": "hello"}) + "\n")

            row = cursor.parse_file(path, {})

            self.assertEqual(row["project"], "Cursor · Users-missing-project")
            self.assertIsNone(row["cwd"])

    def test_parse_file_skips_malformed_jsonl_line(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "projects", "Users-test-project",
                                "agent-transcripts", "session.jsonl")
            os.makedirs(os.path.dirname(path))
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps({"role": "user", "message": "before"}) + "\n")
                f.write("{not valid json}\n")
                f.write(json.dumps({"role": "assistant", "message": "after"}) + "\n")

            row = cursor.parse_file(path, {})

            self.assertEqual(row["activity"]["messages"], 2)

    def test_project_path_without_projects_segment_is_safe(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps({"role": "user", "message": "hello"}) + "\n")

            row = cursor.parse_file(path, {})

            self.assertEqual(row["project"], "Cursor · unknown")
            self.assertEqual(row["projdir"], "unknown")


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

    def test_missing_workspace_dir_keeps_unmapped_activity(self):
        with tempfile.TemporaryDirectory() as root:
            session_id = "11111111-2222-3333-4444-555555555555"
            source = os.path.join(root, "antigravity")
            brain = os.path.join(source, "brain", session_id)
            os.makedirs(brain)
            original = antigravity.SOURCE_DIR, antigravity.WORKSPACE_DIR
            antigravity.SOURCE_DIR = source
            antigravity.WORKSPACE_DIR = os.path.join(root, "missing-workspaces")
            try:
                rows = antigravity.scan()
            finally:
                antigravity.SOURCE_DIR, antigravity.WORKSPACE_DIR = original

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["project"], "Antigravity · unmapped")


if __name__ == "__main__":
    unittest.main()
