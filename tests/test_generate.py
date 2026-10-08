"""Golden-output and CLI contract tests for `generate`."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest

from helpers import FIXTURE, GOLDEN_DIR, SCRIPT, TODAY, WRAPPER, FixtureCase, run_cli


def read(path: str) -> str:
    """Read a UTF-8 file."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class GenerateTests(FixtureCase):
    """Dashboard rendering."""

    def generate(self, locale: str) -> str:
        """Generate into a scratch file and return its text."""
        out = os.path.join(os.path.dirname(self.mem), f"{locale}.md")
        code, stdout, _ = run_cli(
            ["generate", "--memory-dir", self.mem, "--locale", locale,
             "--today", TODAY, "--output", out]
        )
        self.assertEqual(code, 0)
        self.assertIn("1 overdue, 2 observing, 1 active, 1 todo, 3 checkpoints, 1 chores", stdout)
        return read(out)

    def test_golden_en(self) -> None:
        """English output matches the golden file."""
        self.assertEqual(self.generate("en"), read(os.path.join(GOLDEN_DIR, "en.md")))

    def test_golden_zh_tw(self) -> None:
        """zh-TW output matches the golden file."""
        self.assertEqual(self.generate("zh-TW"), read(os.path.join(GOLDEN_DIR, "zh-TW.md")))

    def test_zh_tw_headings_stable(self) -> None:
        """Headings that downstream tooling looks up by exact text stay put."""
        text = self.generate("zh-TW")
        for heading in ("## 📋 待辦", "## ⚠️ 觀察期已過，待回查", "## 🔔 查核點", "## 🧹 待收尾"):
            self.assertIn(heading, text)
        self.assertIn("（已過期 3 天）", text)
        self.assertIn("（今日到期）", text)

    def test_banner_names_the_command_in_both_locales(self) -> None:
        """Banner points at `memory-ledger generate`, never the old script name."""
        for locale in ("en", "zh-TW"):
            text = self.generate(locale)
            self.assertIn("`memory-ledger generate`", text)
            self.assertNotIn("generate_" + "dashboard", text)

    def test_default_output_is_memory_dir_dashboard(self) -> None:
        """Without --output the file lands in <memory-dir>/dashboard.md."""
        code, _, _ = run_cli(["generate", "--memory-dir", self.mem, "--today", TODAY])
        self.assertEqual(code, 0)
        self.assertEqual(read(self.path("dashboard.md")), read(os.path.join(GOLDEN_DIR, "en.md")))

    def test_env_fallbacks(self) -> None:
        """MEMORY_LEDGER_DIR and MEMORY_LEDGER_LOCALE are honoured."""
        os.environ["MEMORY_LEDGER_DIR"] = self.mem
        os.environ["MEMORY_LEDGER_LOCALE"] = "zh-TW"
        out = self.path("env.md")
        code, _, _ = run_cli(["generate", "--today", TODAY, "--output", out])
        self.assertEqual(code, 0)
        self.assertEqual(read(out), read(os.path.join(GOLDEN_DIR, "zh-TW.md")))

    def test_refuses_without_memory_dir(self) -> None:
        """No flag and no env var means refusal, not a guess from the cwd."""
        code, _, err = run_cli(["generate", "--today", TODAY])
        self.assertEqual(code, 2)
        self.assertIn("--memory-dir", err)
        code, _, _ = run_cli(["validate"])
        self.assertEqual(code, 2)

    def test_rejects_missing_dir_bad_locale_bad_today(self) -> None:
        """Usage errors exit 2."""
        self.assertEqual(run_cli(["generate", "--memory-dir", self.path("nope")])[0], 2)
        self.assertEqual(run_cli(["generate", "--memory-dir", self.mem, "--locale", "xx"])[0], 2)
        self.assertEqual(run_cli(["generate", "--memory-dir", self.mem, "--today", "bad"])[0], 2)

    def test_empty_sections(self) -> None:
        """A directory with no projects renders every section as empty."""
        empty = os.path.join(os.path.dirname(self.mem), "empty")
        os.makedirs(empty)
        out = os.path.join(empty, "d.md")
        run_cli(["generate", "--memory-dir", empty, "--today", TODAY, "--output", out])
        self.assertEqual(read(out).count("(none)"), 6)
        run_cli(["generate", "--memory-dir", empty, "--locale", "zh-TW", "--today", TODAY,
                 "--output", out])
        self.assertEqual(read(out).count("（無）"), 6)

    def test_terminal_status_beats_stale_deadline(self) -> None:
        """A done project with an old observe_until never renders as overdue."""
        text = self.generate("en")
        self.assertNotIn("zeta-shipped](project_zeta_shipped.md) — observing", text)

    def test_generate_does_not_touch_other_files(self) -> None:
        """Only the output file is written."""
        before = {n: read(self.path(n)) for n in os.listdir(self.mem) if n.endswith(".md")}
        run_cli(["generate", "--memory-dir", self.mem, "--today", TODAY,
                 "--output", self.path("out.md")])
        after = {n: read(self.path(n)) for n in before}
        self.assertEqual(before, after)

    def test_wrapper_runs_script(self) -> None:
        """bin/memory-ledger resolves the script relative to itself."""
        proc = subprocess.run(
            [WRAPPER, "validate", "--memory-dir", FIXTURE],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("all wikilinks resolve", proc.stdout)

    def test_script_runs_standalone(self) -> None:
        """The script runs under a plain interpreter with no package context."""
        proc = subprocess.run(
            [sys.executable, SCRIPT, "validate", "--memory-dir", FIXTURE],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
