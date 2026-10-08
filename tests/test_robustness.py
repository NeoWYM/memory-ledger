"""Regression tests for crash resistance, tolerant reads and edge-case parsing."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from helpers import FIXTURE, REPO_ROOT, SCRIPT, TODAY, FixtureCase, ml, run_cli


def project(name: str, extra: str, status: str = "active", kind: str = "project") -> str:
    """Build a project memory file body with extra metadata lines."""
    return (
        f"---\nname: {name}\ndescription: d\nmetadata:\n  type: {kind}\n"
        f"  status: {status}\n{extra}---\n\nBody.\n"
    )


class RobustnessTests(FixtureCase):
    """Cases found in review: crashes, fail-open reads and false positives."""

    def index(self, fname: str) -> None:
        """Append an index line so the file is reachable."""
        with open(self.path("MEMORY.md"), "a", encoding="utf-8") as handle:
            handle.write(f"- [x]({fname}) — x\n")

    def hook(self, file_path: str):
        """Run the hook subprocess for one edited path."""
        payload = json.dumps({"tool_input": {"file_path": file_path}})
        return subprocess.run(
            [sys.executable, SCRIPT, "hook"], input=payload, capture_output=True,
            text=True, check=False,
        )

    # --- major 1: scalar vs list frontmatter --------------------------------

    def test_scalar_then_list_does_not_crash(self) -> None:
        """A list key seen first as a scalar no longer raises."""
        text = (
            "---\nname: mixed\ndescription: d\ncheckpoints: none\nchores: x\nmetadata:\n"
            "  type: project\n  status: active\n  checkpoints:\n    - 2026-03-20 | fine\n---\n"
        )
        path = self.write("project_mixed.md", text)
        self.index("project_mixed.md")
        fm = ml.parse_frontmatter(path)
        self.assertEqual(fm["checkpoints"], ["2026-03-20 | fine"])
        self.assertEqual(fm.get("chores", []), [])
        # The scalars are ignored by the parser but are findings, not crashes.
        code, _, err = run_cli(["validate", "--memory-dir", self.mem])
        self.assertEqual(code, 1)
        self.assertIn("project_mixed.md:4: checkpoints: none", err)
        self.assertIn("project_mixed.md:5: chores: x", err)
        self.assertNotIn("Traceback", err)
        code, _, err = run_cli(["generate", "--memory-dir", self.mem, "--today", TODAY])
        self.assertEqual((code, "Traceback" in err), (0, False))
        self.assertIn("scalar value", err)
        proc = self.hook(path)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)

    def test_scalar_on_list_key_is_a_finding(self) -> None:
        """`checkpoints: <date> | text` would be silently ignored, so it is reported."""
        extra = "  checkpoints: 2026-10-15 | verify the first run\n"
        path = self.write("project_scalar.md", project("scalar", extra))
        self.index("project_scalar.md")
        for argv in (["validate", "--memory-dir", self.mem],
                     ["validate", "--memory-dir", self.mem, path]):
            code, _, err = run_cli(argv)
            self.assertEqual(code, 1)
            self.assertIn("project_scalar.md:7: checkpoints: 2026-10-15 |", err)
        code, _, err = run_cli(["validate", "--memory-dir", self.mem, "--locale", "zh-TW", path])
        self.assertEqual(code, 1)
        self.assertIn("純量值", err)
        proc = self.hook(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("project_scalar.md:7", proc.stderr)

    def test_empty_forms_are_not_scalar_findings(self) -> None:
        """`[]` and a bare key with a comment stay valid empty lists."""
        extra = "  checkpoints: []\n  chores: # nothing yet\n"
        path = self.write("project_fine.md", project("fine", extra))
        self.index("project_fine.md")
        self.assertEqual(run_cli(["validate", "--memory-dir", self.mem])[0], 0)
        self.assertEqual(self.hook(path).returncode, 0)

    def test_unscoped_validate_reports_untyped_project_files(self) -> None:
        """A project_*.md without type: project is invisible, so unscoped validate says so."""
        self.write("project_notes.md", project("notes", "", kind="note"))
        self.write("project_bare.md", "No frontmatter at all.\n")
        self.index("project_notes.md")
        self.index("project_bare.md")
        code, _, err = run_cli(["validate", "--memory-dir", self.mem])
        self.assertEqual(code, 1)
        self.assertIn("without `type: project`", err)
        self.assertIn("  project_bare.md", err)
        self.assertIn("  project_notes.md", err)
        # Scoped runs and the hook gate are unchanged: no opinion on other files.
        self.assertEqual(run_cli(["validate", "--memory-dir", self.mem,
                                  self.path("project_notes.md")])[0], 0)
        self.assertEqual(self.hook(self.path("project_notes.md")).returncode, 0)
        code, _, err = run_cli(["generate", "--memory-dir", self.mem, "--today", TODAY])
        self.assertEqual(code, 0)
        self.assertIn("without `type: project`", err)

    def test_hook_findings_mention_internal_errors(self) -> None:
        """When a check crashed, exit-2 output also says so."""
        self.replace_in("project_delta_api.md", "status: active", "status: open")
        payload = json.dumps({"tool_input": {"file_path": self.path("project_delta_api.md")}})
        err = io.StringIO()
        with mock.patch.object(ml.Validator, "find_dangling_wikilinks",
                               side_effect=RuntimeError("boom")), \
                mock.patch("sys.stdin") as stdin, contextlib.redirect_stderr(err):
            stdin.buffer.read.return_value = payload.encode("utf-8")
            code = ml.main(["hook"])
        self.assertEqual(code, 2)
        self.assertIn("status: open", err.getvalue())
        self.assertIn("internal error in wikilink check", err.getvalue())

    def test_list_then_scalar_does_not_crash(self) -> None:
        """A scalar after a list does not turn the list into a string."""
        text = (
            "---\nname: mixed\ndescription: d\nmetadata:\n  type: project\n  status: active\n"
            "  checkpoints:\n    - 2026-03-20 | fine\n  checkpoints: later\n---\n"
        )
        path = self.write("project_mixed.md", text)
        self.assertEqual(ml.parse_frontmatter(path)["checkpoints"], ["2026-03-20 | fine"])

    # --- major 2: undecodable files -----------------------------------------

    def test_non_utf8_file_does_not_hide_findings(self) -> None:
        """A non-UTF8 file elsewhere neither aborts validate nor drops findings."""
        with open(self.path("reference_binary.md"), "wb") as handle:
            handle.write(b"---\nname: binary\n---\n\xff\xfe\x80 [[reference_glossary]]\n")
        self.index("reference_binary.md")
        self.replace_in("project_delta_api.md", "status: active", "status: open")
        code, _, err = run_cli(["validate", "--memory-dir", self.mem])
        self.assertEqual(code, 1)
        self.assertIn("status: open", err)
        self.assertNotIn("internal error", err)
        proc = self.hook(self.path("project_delta_api.md"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("status: open", proc.stderr)
        self.assertEqual(run_cli(["generate", "--memory-dir", self.mem, "--today", TODAY])[0], 0)

    def test_non_utf8_edited_file_is_still_checked(self) -> None:
        """Undecodable bytes in the edited file itself do not skip its checks."""
        raw = project("bad", "").replace("active", "open").encode("utf-8") + b"\xff\xfe\n"
        with open(self.path("project_bad.md"), "wb") as handle:
            handle.write(raw)
        self.assertEqual(self.hook(self.path("project_bad.md")).returncode, 2)

    def test_internal_error_never_hides_other_findings(self) -> None:
        """One crashing check is recorded; findings from the others survive."""
        self.replace_in("project_delta_api.md", "status: active", "status: open")
        validator = ml.Validator(self.mem, ml.LOCALES["en"])
        with mock.patch.object(ml.Validator, "find_dangling_wikilinks",
                               side_effect=RuntimeError("boom")):
            code, msgs = validator.validate()
        self.assertEqual(code, 1)
        self.assertTrue(any("status: open" in text for _, text in msgs))
        self.assertTrue(validator.internal_errors)
        self.assertFalse(any("all wikilinks resolve" in text for _, text in msgs))

    def test_cli_internal_error_is_exit_two_without_traceback(self) -> None:
        """validate and generate report internal errors cleanly."""
        with mock.patch.object(ml.Validator, "find_invalid_statuses",
                               side_effect=RuntimeError("boom")):
            code, _, err = run_cli(["validate", "--memory-dir", self.mem])
        self.assertEqual(code, 2)
        self.assertIn("internal error", err)
        self.assertNotIn("Traceback", err)
        with mock.patch.object(ml.DashboardBuilder, "build", side_effect=RuntimeError("boom")):
            code, _, err = run_cli(["generate", "--memory-dir", self.mem])
        self.assertEqual(code, 2)
        self.assertIn("internal error: RuntimeError: boom", err)

    def test_hook_internal_error_fails_open(self) -> None:
        """An unexpected exception in the hook yields exit 0 with no output."""
        payload = json.dumps({"tool_input": {"file_path": self.path("project_delta_api.md")}})
        with mock.patch.object(ml.Validator, "validate", side_effect=RuntimeError("boom")), \
                mock.patch("sys.stdin") as stdin:
            stdin.buffer.read.return_value = payload.encode("utf-8")
            code = ml.main(["hook"])
        self.assertEqual(code, 0)

    # --- minors ---------------------------------------------------------------

    def test_hook_requires_type_project(self) -> None:
        """A project_*.md that is not a type: project memory is ignored."""
        path = self.write("project_notes.md", project("n", "", kind="note")
                          + "See [[reference_missing]].\n")
        proc = self.hook(path)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))
        plain = self.write("project_plain.md", "No frontmatter, see [[reference_missing]].\n")
        proc = self.hook(plain)
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))

    def test_empty_list_forms_are_empty_lists(self) -> None:
        """`[]` and trailing comments mean an empty list, not a malformed item."""
        extra = "  checkpoints: [] # none yet\n  chores: []\n"
        path = self.write("project_empty.md", project("empty", extra))
        self.index("project_empty.md")
        fm = ml.parse_frontmatter(path)
        self.assertEqual((fm["checkpoints"], fm["chores"]), ([], []))
        extra = "  checkpoints: # none yet\n    - 2026-03-20 | real item\n  chores: # nothing\n"
        path = self.write("project_empty.md", project("empty", extra))
        fm = ml.parse_frontmatter(path)
        self.assertEqual((fm["checkpoints"], fm["chores"]), (["2026-03-20 | real item"], []))
        self.write("project_empty.md", project("empty", "  checkpoints: []\n  chores: [] # x\n"))
        self.assertEqual(run_cli(["validate", "--memory-dir", self.mem])[0], 0)
        out = self.path("o.md")
        run_cli(["generate", "--memory-dir", self.mem, "--today", TODAY, "--output", out])
        with open(out, encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("- [ —", text)
        self.assertNotIn("- ] —", text)

    def test_glob_special_directory_name(self) -> None:
        """A memory directory whose name contains glob characters still works."""
        with tempfile.TemporaryDirectory() as tmp:
            odd = os.path.join(tmp, "mem[ory]*?")
            shutil.copytree(FIXTURE, odd)
            code, _, err = run_cli(["validate", "--memory-dir", odd])
            self.assertEqual((code, err), (0, ""))
            with open(os.path.join(odd, "project_delta_api.md"), "r+", encoding="utf-8") as h:
                text = h.read().replace("status: active", "status: open")
                h.seek(0)
                h.write(text)
            with open(os.path.join(odd, "reference_orphan.md"), "w", encoding="utf-8") as h:
                h.write("---\nname: orphan\n---\n")
            code, _, err = run_cli(["validate", "--memory-dir", odd])
            self.assertEqual(code, 1)
            self.assertIn("status: open", err)
            self.assertIn("reference_orphan.md", err)
            out_file = os.path.join(tmp, "d.md")
            _, stdout, _ = run_cli(["generate", "--memory-dir", odd, "--today", TODAY,
                                    "--output", out_file])
            self.assertIn("1 overdue", stdout)

    def test_nonexistent_scoped_file_is_an_error(self) -> None:
        """A scoped validate naming a missing file exits 2 and names it."""
        missing = self.path("project_typo.md")
        code, out, err = run_cli(["validate", "--memory-dir", self.mem, missing])
        self.assertEqual(code, 2)
        self.assertIn("project_typo.md", err)
        self.assertEqual(out, "")

    def test_scoped_file_without_wikilinks_skips_target_scan(self) -> None:
        """No `[[` in the scanned file means the whole-directory scan never runs."""
        validator = ml.Validator(self.mem, ml.LOCALES["en"])
        with mock.patch.object(ml.Validator, "_wikilink_targets",
                               side_effect=AssertionError("must not run")):
            self.assertEqual(
                validator.find_dangling_wikilinks([self.path("project_delta_api.md")]), [])

    def test_overdue_pluralisation(self) -> None:
        """One day is singular in English."""
        extra = (
            "  checkpoints:\n    - 2026-03-14 | one day late\n"
            "    - 2026-03-13 | two days late\n"
        )
        self.write("project_late.md", project("late", extra))
        out = self.path("o.md")
        run_cli(["generate", "--memory-dir", self.mem, "--today", TODAY, "--output", out])
        with open(out, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("(overdue 1 day)", text)
        self.assertIn("(overdue 2 days)", text)

    def test_script_and_wrapper_are_executable(self) -> None:
        """bin/memory-ledger and the script keep their executable bit."""
        for rel in ("bin/memory-ledger", "scripts/memory_ledger.py"):
            self.assertTrue(os.access(os.path.join(REPO_ROOT, rel), os.X_OK), rel)


if __name__ == "__main__":
    unittest.main()
