"""Static checks on plugin manifests and skill frontmatter."""
from __future__ import annotations

import glob
import json
import os
import unittest

from helpers import REPO_ROOT, ml


class ManifestTests(unittest.TestCase):
    """Manifests and skills carry the fields Claude Code needs."""

    def test_skill_frontmatter(self) -> None:
        """Every skill has a name matching its directory and a description."""
        skills = glob.glob(os.path.join(REPO_ROOT, "skills", "*", "SKILL.md"))
        self.assertEqual(sorted(os.path.basename(os.path.dirname(p)) for p in skills),
                         ["conventions", "due"])
        for path in skills:
            fm = ml.parse_frontmatter(path)
            self.assertIsNotNone(fm, path)
            self.assertEqual(fm.get("name"), os.path.basename(os.path.dirname(path)))
            self.assertTrue(fm.get("description"), path)

    def test_plugin_and_marketplace_names_agree(self) -> None:
        """marketplace plugin entry name equals plugin.json name."""
        base = os.path.join(REPO_ROOT, ".claude-plugin")
        with open(os.path.join(base, "plugin.json"), encoding="utf-8") as handle:
            plugin = json.load(handle)
        with open(os.path.join(base, "marketplace.json"), encoding="utf-8") as handle:
            market = json.load(handle)
        self.assertEqual(plugin["name"], market["plugins"][0]["name"])
        self.assertEqual(market["plugins"][0]["source"], "./")


if __name__ == "__main__":
    unittest.main()
