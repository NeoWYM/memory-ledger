"""Shared helpers for the memory-ledger test suite."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest
from types import ModuleType
from typing import List, Tuple

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
SCRIPT = os.path.join(REPO_ROOT, "scripts", "memory_ledger.py")
WRAPPER = os.path.join(REPO_ROOT, "bin", "memory-ledger")
FIXTURE = os.path.join(TESTS_DIR, "fixtures", "memory")
GOLDEN_DIR = os.path.join(TESTS_DIR, "golden")
TODAY = "2026-03-15"


def load_module() -> ModuleType:
    """Import scripts/memory_ledger.py as a module."""
    spec = importlib.util.spec_from_file_location("memory_ledger", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["memory_ledger"] = module
    spec.loader.exec_module(module)
    return module


ml = load_module()


def run_cli(argv: List[str]) -> Tuple[int, str, str]:
    """Run ml.main(argv) in-process and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ml.main(argv)
        except SystemExit as exc:  # argparse errors
            code = int(exc.code) if isinstance(exc.code, int) else 2
    return code, out.getvalue(), err.getvalue()


class FixtureCase(unittest.TestCase):
    """Base class giving each test a private writable copy of the fixture."""

    def setUp(self) -> None:
        """Copy the fixture memory dir into a temp dir."""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.mem = os.path.join(self._tmp.name, "memory")
        shutil.copytree(FIXTURE, self.mem)
        self.env_backup = dict(os.environ)
        self.addCleanup(self._restore_env)
        for key in ("MEMORY_LEDGER_DIR", "MEMORY_LEDGER_LOCALE"):
            os.environ.pop(key, None)

    def _restore_env(self) -> None:
        os.environ.clear()
        os.environ.update(self.env_backup)

    def path(self, name: str) -> str:
        """Absolute path of a file inside the temp memory dir."""
        return os.path.join(self.mem, name)

    def write(self, name: str, text: str) -> str:
        """Write a file inside the temp memory dir and return its path."""
        full = self.path(name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)
        return full

    def replace_in(self, name: str, old: str, new: str) -> None:
        """Replace text in a fixture file, asserting the old text exists."""
        with open(self.path(name), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(old, text)
        with open(self.path(name), "w", encoding="utf-8") as handle:
            handle.write(text.replace(old, new))
