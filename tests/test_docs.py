"""Run the documented plugin-cache fallback snippet against fake cache layouts."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest

from helpers import REPO_ROOT


def snippet(doc: str) -> str:
    """Extract the fallback shell snippet from a document."""
    with open(os.path.join(REPO_ROOT, doc), encoding="utf-8") as handle:
        text = handle.read()
    blocks = re.findall(r"```bash\n(.*?)```", text, flags=re.S)
    found = [b for b in blocks if "CLAUDE_CODE_PLUGIN_CACHE_DIR" in b]
    assert len(found) == 1, doc
    return found[0]


class FallbackSnippetTests(unittest.TestCase):
    """The snippet must pick the newest version and fail loudly when absent."""

    def run_snippet(self, doc: str, root: str):
        """Run the snippet with a stub script layout under `root`."""
        code = snippet(doc).replace("<dir>", "ignored").replace('"<dir>"', "ignored")
        env = {"PATH": os.environ["PATH"], "HOME": root, "CLAUDE_CODE_PLUGIN_CACHE_DIR": root}
        return subprocess.run(["sh", "-c", code], capture_output=True, text=True,
                              env=env, cwd=root, check=False)

    def make_version(self, root: str, marketplace: str, plugin: str, version: str) -> None:
        """Create a fake installed plugin version whose script prints its version."""
        scripts = os.path.join(root, "cache", marketplace, plugin, version, "scripts")
        os.makedirs(scripts)
        with open(os.path.join(scripts, "memory_ledger.py"), "w", encoding="utf-8") as handle:
            handle.write(f"print('{plugin} {version}')\n")

    def test_picks_highest_version_of_the_right_plugin(self) -> None:
        """0.10.0 beats 0.9.0, and other plugins' directories are ignored."""
        for doc in ("README.md", "README.zh-TW.md", "skills/due/SKILL.md"):
            with tempfile.TemporaryDirectory() as root:
                self.make_version(root, "mk", "memory-ledger", "0.9.0")
                self.make_version(root, "mk", "memory-ledger", "0.10.0")
                self.make_version(root, "mk", "other-plugin", "9.9.9")
                proc = self.run_snippet(doc, root)
                self.assertEqual(proc.returncode, 0, (doc, proc.stderr))
                self.assertEqual(proc.stdout.strip(), "memory-ledger 0.10.0", doc)

    def test_fails_loudly_when_not_installed(self) -> None:
        """Nothing found: clear message, non-zero exit, nothing executed."""
        for doc in ("README.md", "README.zh-TW.md", "skills/due/SKILL.md"):
            with tempfile.TemporaryDirectory() as root:
                self.make_version(root, "mk", "other-plugin", "1.0.0")
                proc = self.run_snippet(doc, root)
                self.assertNotEqual(proc.returncode, 0, doc)
                self.assertIn("memory-ledger plugin not found", proc.stderr)
                self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
