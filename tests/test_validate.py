"""Validator tests: every negative case asserts a non-zero exit."""
from __future__ import annotations

import unittest

from helpers import FixtureCase, run_cli


def read(path: str) -> str:
    """Read a UTF-8 file."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class ValidateTests(FixtureCase):
    """Behaviour of `validate`."""

    def validate(self, *files: str):
        """Run validate over the temp dir, optionally scoped to files."""
        return run_cli(["validate", "--memory-dir", self.mem, *files])

    def test_fixture_is_clean(self) -> None:
        """The unmodified fixture passes with all four OK lines."""
        code, out, err = self.validate()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(len(out.splitlines()), 4)

    def test_bad_status(self) -> None:
        """An unknown status is reported and exits 1."""
        self.replace_in("project_delta_api.md", "status: active", "status: open")
        code, _, err = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("project_delta_api.md: status: open", err)

    def test_observing_with_bad_status(self) -> None:
        """A bad status is caught even when a live observe_until still renders it."""
        self.replace_in("project_beta_cache.md", "status: observing", "status: closed")
        code, _, err = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("status: closed", err)

    def test_orphan_file(self) -> None:
        """A memory file reachable from no index is reported."""
        self.write("reference_orphan.md", "---\nname: orphan\n---\nText.\n")
        code, _, err = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("reference_orphan.md", err)
        self.assertIn("not reachable", err)

    def test_dangling_index_link(self) -> None:
        """An index link to a missing file is reported."""
        with open(self.path("MEMORY.md"), "a", encoding="utf-8") as handle:
            handle.write("- [ghost](reference_ghost.md) — gone\n")
        code, _, err = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("pointing at a missing file", err)
        self.assertIn("reference_ghost.md", err)

    def test_archive_index_counts_as_index(self) -> None:
        """Moving a link from MEMORY.md to archive_index.md keeps the file reachable."""
        self.replace_in("MEMORY.md", "- [reference-glossary](reference_glossary.md) — terms\n", "")
        code, _, err = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("reference_glossary.md", err)
        with open(self.path("archive_index.md"), "a", encoding="utf-8") as handle:
            handle.write("- [reference-glossary](reference_glossary.md) — terms\n")
        self.assertEqual(self.validate()[0], 0)

    def test_dangling_wikilink(self) -> None:
        """A wikilink resolving to no file is reported."""
        self.replace_in("feedback_example_rule.md",
                        "[[reference_glossary]]", "[[reference_missing]]")
        code, _, err = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("[[reference_missing]]", err)

    def test_wikilink_name_alias_and_dash_normalisation(self) -> None:
        """Links may use the frontmatter name or the stem, with - or _ spellings."""
        self.replace_in("feedback_example_rule.md",
                        "[[alpha-migration]]", "[[project-alpha-migration]]")
        self.assertEqual(self.validate()[0], 0)
        self.replace_in("feedback_example_rule.md",
                        "[[project-alpha-migration]]", "[[reference-glossary]]")
        self.assertEqual(self.validate()[0], 0)

    def test_non_link_brackets_ignored(self) -> None:
        """JSON-like double brackets are not links (the fixture already contains one)."""
        self.assertIn('[["a","b"]]', read(self.path("feedback_example_rule.md")))
        self.assertEqual(self.validate()[0], 0)

    def test_unparseable_checkpoint_date(self) -> None:
        """Both a wrong shape and an impossible date fail."""
        self.replace_in("project_alpha_migration.md", "2026-04-01 |", "2026-13-45 |")
        code, _, err = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("malformed checkpoint", err)
        self.assertIn("2026-13-45", err)
        self.replace_in("project_alpha_migration.md", "2026-13-45 |", "tomorrow |")
        self.assertEqual(self.validate()[0], 1)

    FLAT_PROJECT = (
        "---\nname: flat\ndescription: flat list\nmetadata:\n  type: project\n"
        "  status: active\n  {key}:\n- {item}\n---\n"
    )

    def add_flat(self, key: str, item: str) -> str:
        """Add an indexed project whose list item has no indentation."""
        path = self.write("project_flat.md", self.FLAT_PROJECT.format(key=key, item=item))
        with open(self.path("MEMORY.md"), "a", encoding="utf-8") as handle:
            handle.write("- [flat](project_flat.md) — flat\n")
        return path

    def test_zero_indent_checkpoint_item(self) -> None:
        """An unindented checkpoints item is reported with file and line, exit 1."""
        self.add_flat("checkpoints", "2026-03-20 | never rendered")
        code, _, err = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("zero-indent", err)
        self.assertIn("project_flat.md:8: - 2026-03-20 | never rendered", err)

    def test_zero_indent_chore_item(self) -> None:
        """The same applies to chores."""
        self.add_flat("chores", "remove the temporary branch")
        code, _, err = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("project_flat.md:8: - remove the temporary branch", err)

    def test_zero_indent_scoped_validate(self) -> None:
        """A scoped run catches it too."""
        path = self.add_flat("checkpoints", "2026-03-20 | x")
        self.assertEqual(self.validate(path)[0], 1)

    def test_zero_indent_localized(self) -> None:
        """The zh-TW locale reports it in Chinese."""
        path = self.add_flat("chores", "do it")
        code, _, err = run_cli(["validate", "--memory-dir", self.mem, "--locale", "zh-TW", path])
        self.assertEqual(code, 1)
        self.assertIn("零縮排", err)

    def test_zero_indent_regenerate_warns(self) -> None:
        """generate prints it as a warning and still exits 0."""
        self.add_flat("chores", "do it")
        code, _, err = run_cli(["generate", "--memory-dir", self.mem, "--today", "2026-03-15"])
        self.assertEqual(code, 0)
        self.assertIn("zero-indent", err)

    def test_indented_items_not_flagged(self) -> None:
        """Properly indented items, and dashes elsewhere, are not flagged."""
        self.write(
            "project_ok.md",
            "---\nname: ok\ndescription: fine\nmetadata:\n  type: project\n"
            "  status: active\n  checkpoints:\n    - 2026-03-20 | fine\n"
            "  chores:\n    - also fine\n---\n\n- a body bullet\n",
        )
        with open(self.path("MEMORY.md"), "a", encoding="utf-8") as handle:
            handle.write("- [ok](project_ok.md) — ok\n")
        code, out, err = self.validate()
        self.assertEqual((code, err), (0, ""))
        self.assertNotIn("zero-indent", out)

    def test_zero_indent_after_other_key_not_flagged(self) -> None:
        """A dash line after a non-list key is not a list item of checkpoints."""
        text = (
            "---\nname: ok2\ndescription: fine\nmetadata:\n  type: project\n"
            "  checkpoints:\n    - 2026-03-20 | fine\n  status: active\n- stray\n---\n"
        )
        self.write("project_ok2.md", text)
        with open(self.path("MEMORY.md"), "a", encoding="utf-8") as handle:
            handle.write("- [ok2](project_ok2.md) — ok\n")
        self.assertEqual(self.validate()[0], 0)

    def test_scoped_validate_skips_index_check(self) -> None:
        """A scoped run ignores orphans and dangling index links."""
        self.write("reference_orphan.md", "---\nname: orphan\n---\nText.\n")
        self.assertEqual(self.validate()[0], 1)
        code, out, _ = self.validate(self.path("project_delta_api.md"))
        self.assertEqual(code, 0)
        self.assertNotIn("reachable", out)

    def test_scoped_validate_still_checks_the_file(self) -> None:
        """Status, checkpoints and wikilinks are checked for the scoped file only."""
        self.replace_in("project_delta_api.md", "status: active", "status: open")
        self.replace_in("project_beta_cache.md", "status: observing", "status: closed")
        code, _, err = self.validate(self.path("project_delta_api.md"))
        self.assertEqual(code, 1)
        self.assertIn("project_delta_api.md", err)
        self.assertNotIn("project_beta_cache.md", err)

    def test_regenerate_warns_but_exits_zero(self) -> None:
        """generate reports findings on stderr without failing."""
        self.replace_in("project_delta_api.md", "status: active", "status: open")
        code, _, err = run_cli(["generate", "--memory-dir", self.mem, "--today", "2026-03-15"])
        self.assertEqual(code, 0)
        self.assertIn("invalid status", err)


if __name__ == "__main__":
    unittest.main()
