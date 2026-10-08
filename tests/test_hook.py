"""PostToolUse hook behaviour, exercised through a real subprocess."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from typing import Optional

from helpers import SCRIPT, FixtureCase


class HookTests(FixtureCase):
    """The hook must be silent unless a memory project file is bad."""

    def hook(self, stdin: str, locale: Optional[str] = None):
        """Run `hook` with the given stdin text."""
        env = dict(os.environ)
        env.pop("MEMORY_LEDGER_LOCALE", None)
        if locale:
            env["MEMORY_LEDGER_LOCALE"] = locale
        return subprocess.run(
            [sys.executable, SCRIPT, "hook"], input=stdin, capture_output=True,
            text=True, env=env, check=False,
        )

    def payload(self, file_path: object) -> str:
        """Build a PostToolUse payload."""
        return json.dumps({"tool_name": "Write", "tool_input": {"file_path": file_path}})

    def assert_silent_ok(self, proc: subprocess.CompletedProcess) -> None:
        """Assert exit 0 with no output at all."""
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))

    def test_non_memory_path_is_silent(self) -> None:
        """Files outside */memory/project_*.md are ignored."""
        for target in ("/tmp/some/other/file.py", self.path("feedback_example_rule.md"),
                       os.path.join(os.path.dirname(self.mem), "project_x.md")):
            self.assert_silent_ok(self.hook(self.payload(target)))

    def test_missing_file_is_silent(self) -> None:
        """A matching path that does not exist is ignored."""
        self.assert_silent_ok(self.hook(self.payload(self.path("project_nope.md"))))

    def test_malformed_stdin_exits_zero(self) -> None:
        """Garbage, empty and wrongly-shaped input never fail the hook."""
        for stdin in ("", "not json", "[]", "null", "{}", '{"tool_input": 5}',
                      '{"tool_input": {"file_path": 7}}', '{"tool_input": {}}'):
            self.assert_silent_ok(self.hook(stdin))

    def test_good_file_is_silent(self) -> None:
        """A valid project file produces no output."""
        self.assert_silent_ok(self.hook(self.payload(self.path("project_delta_api.md"))))

    def test_bad_status_exits_two(self) -> None:
        """A bad status exits 2 and reports on stderr only."""
        self.replace_in("project_delta_api.md", "status: active", "status: open")
        proc = self.hook(self.payload(self.path("project_delta_api.md")))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("status: open", proc.stderr)
        self.assertIn("`memory-ledger generate`", proc.stderr)

    def test_hook_scopes_to_edited_file(self) -> None:
        """A bad sibling does not trigger a report for a good file."""
        self.replace_in("project_beta_cache.md", "status: observing", "status: closed")
        self.assert_silent_ok(self.hook(self.payload(self.path("project_delta_api.md"))))

    def test_hook_locale_from_env(self) -> None:
        """MEMORY_LEDGER_LOCALE selects the hint text."""
        self.replace_in("project_delta_api.md", "status: active", "status: open")
        proc = self.hook(self.payload(self.path("project_delta_api.md")), locale="zh-TW")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("修正 frontmatter", proc.stderr)
        self.assertIn("`memory-ledger generate`", proc.stderr)

    def test_hook_catches_zero_indent_item(self) -> None:
        """An unindented checkpoints item exits 2 with file and line."""
        path = self.write(
            "project_flat.md",
            "---\nname: flat\ndescription: d\nmetadata:\n  type: project\n"
            "  status: active\n  checkpoints:\n- 2026-03-20 | x\n---\n",
        )
        proc = self.hook(self.payload(path))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("project_flat.md:8", proc.stderr)

    def test_hook_catches_dangling_wikilink(self) -> None:
        """Scoped validate also covers wikilinks."""
        with open(self.path("project_delta_api.md"), "a", encoding="utf-8") as handle:
            handle.write("\nSee [[reference_missing]].\n")
        proc = self.hook(self.payload(self.path("project_delta_api.md")))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("[[reference_missing]]", proc.stderr)


class HooksManifestTests(unittest.TestCase):
    """hooks/hooks.json shape."""

    def test_manifest(self) -> None:
        """PostToolUse entry runs the plugin script via CLAUDE_PLUGIN_ROOT."""
        from helpers import REPO_ROOT

        with open(os.path.join(REPO_ROOT, "hooks", "hooks.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        entry = data["hooks"]["PostToolUse"][0]
        self.assertEqual(entry["matcher"], "Write|Edit|MultiEdit")
        command = entry["hooks"][0]["command"]
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/scripts/memory_ledger.py", command)
        self.assertTrue(command.endswith(" hook"))


if __name__ == "__main__":
    unittest.main()
