"""Quoted YAML scalars and list items, as written by Claude Code's memory serializer."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest

from helpers import SCRIPT, TODAY, FixtureCase, ml, run_cli

# The serializer re-quotes one list item and adds session bookkeeping keys.
SERIALIZED = '''---
name: quoted-project
description: "Project with a \\"quoted\\" description"
metadata:
  node_type: memory
  type: project
  originSessionId: 3f2b8c1e-0000-4000-8000-000000000003
  modified: 2026-03-01T09:00:00.000Z
  status: observing
  observe_until: "2026-03-30"
  checkpoints:
    - "2026-03-16 | daily: run `memory-ledger validate --memory-dir <dir>` then check (b) ..."
    - 2026-03-20 | plain item
  chores:
    - "remove the temporary branch"
    - 'it''s done when the sample is gone'
---

Body.
'''


class QuotingTests(FixtureCase):
    """unquote() and its effect on parsing, rendering and validation."""

    def add(self, text: str = SERIALIZED, name: str = "project_quoted.md") -> str:
        """Write a project file and index it."""
        path = self.write(name, text)
        with open(self.path("MEMORY.md"), "a", encoding="utf-8") as handle:
            handle.write(f"- [q]({name}) — q\n")
        return path

    def test_unquote_rules(self) -> None:
        """Matching pairs are stripped; escapes handled; odd cases untouched."""
        cases = {
            '"abc"': "abc", "'abc'": "abc", '"a \\"b\\" c"': 'a "b" c',
            '"back\\\\slash"': "back\\slash", '"keep \\n literal"': "keep \\n literal",
            "'it''s'": "it's", '"abc': '"abc', 'abc"': 'abc"', "'abc": "'abc",
            '"abc\\"': '"abc\\"', '"mixed\'': '"mixed\'', '"': '"', "plain": "plain",
        }
        for raw, want in cases.items():
            self.assertEqual(ml.unquote(raw), want, raw)

    def test_quoted_items_parse(self) -> None:
        """Checkpoint and chore items lose their quotes; other keys survive."""
        fm = ml.parse_frontmatter(self.add())
        self.assertEqual(fm["checkpoints"][0][:30], "2026-03-16 | daily: run `memor")
        self.assertEqual(fm["checkpoints"][1], "2026-03-20 | plain item")
        self.assertEqual(fm["chores"], ["remove the temporary branch",
                                        "it's done when the sample is gone"])
        self.assertEqual(fm["description"], 'Project with a "quoted" description')
        self.assertEqual(fm["observe_until"], "2026-03-30")
        self.assertEqual(fm["originSessionId"], "3f2b8c1e-0000-4000-8000-000000000003")

    def test_validate_passes_and_dashboard_has_no_quotes(self) -> None:
        """The serializer form is valid, and the dashboard renders unquoted text."""
        self.add()
        code, _, err = run_cli(["validate", "--memory-dir", self.mem])
        self.assertEqual((code, err), (0, ""))
        out = self.path("o.md")
        run_cli(["generate", "--memory-dir", self.mem, "--today", TODAY, "--output", out])
        with open(out, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("- 2026-03-16 — daily: run `memory-ledger validate --memory-dir <dir>`", text)
        self.assertNotIn('"2026-03-16', text)
        self.assertIn("- remove the temporary branch — [project_quoted.md]", text)
        self.assertIn("- it's done when the sample is gone —", text)
        self.assertIn('Project with a "quoted" description', text)
        self.assertIn("[quoted-project](project_quoted.md) — observing until 2026-03-30", text)

    def test_quoted_status_values(self) -> None:
        """`status: "todo"` and `status: 'observing'` are valid statuses."""
        for status in ('"todo"', "'observing'", '"done"'):
            self.add(SERIALIZED.replace("status: observing", f"status: {status}"))
            self.assertEqual(run_cli(["validate", "--memory-dir", self.mem])[0], 0, status)
            self.setUp()

    def test_quoted_status_is_still_checked(self) -> None:
        """Unquoting happens before the status check, so a bad quoted value is flagged."""
        self.add(SERIALIZED.replace("status: observing", 'status: "open"'))
        code, _, err = run_cli(["validate", "--memory-dir", self.mem])
        self.assertEqual(code, 1)
        self.assertIn("status: open", err)

    def test_quoted_type(self) -> None:
        """`type: "project"` still marks a project."""
        path = self.add(SERIALIZED.replace("type: project", 'type: "project"'))
        self.assertEqual(ml.parse_frontmatter(path)["type"], "project")
        self.assertEqual(run_cli(["validate", "--memory-dir", self.mem])[0], 0)

    def test_unbalanced_quote_is_still_flagged(self) -> None:
        """A checkpoint with a dangling quote is malformed, as before."""
        bad = SERIALIZED.replace('- "2026-03-16 |', '- "2026-13-16 |').replace(
            "(b) ...\"", "(b) ...")
        self.add(bad)
        code, _, err = run_cli(["validate", "--memory-dir", self.mem])
        self.assertEqual(code, 1)
        self.assertIn("malformed checkpoint", err)
        self.assertIn('"2026-13-16', err)

    def test_unbalanced_status_is_still_flagged(self) -> None:
        """An unterminated quoted status is an invalid status."""
        self.add(SERIALIZED.replace("status: observing", 'status: "todo'))
        code, _, err = run_cli(["validate", "--memory-dir", self.mem])
        self.assertEqual(code, 1)
        self.assertIn('status: "todo', err)

    def test_hook_accepts_serializer_form(self) -> None:
        """The hook stays silent on a valid file in exactly the serializer form."""
        path = self.add()
        payload = json.dumps({"tool_input": {"file_path": path}})
        proc = subprocess.run([sys.executable, SCRIPT, "hook"], input=payload,
                              capture_output=True, text=True, check=False)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
