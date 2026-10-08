# memory-ledger

A [Claude Code](https://code.claude.com) plugin that turns auto-memory project notes into a tracked ledger.

- **Dashboard**: `memory-ledger generate` builds `dashboard.md` from the `status`, `observe_until`, `checkpoints` and `chores` frontmatter of your `project_*.md` memory files: what is overdue, what is due, what is being observed, active, or still a to-do.
- **Validator**: `memory-ledger validate` catches the failures that otherwise go unnoticed: an unknown `status` (the project silently disappears), an unparseable checkpoint date or an unindented list item (it never comes due), dangling `[[wikilinks]]`, and memory files unreachable from the indexes.
- **Hook**: a PostToolUse hook validates every `project_*.md` you write, at write time.
- **Skills**: `memory-ledger:conventions` (the rules, for Claude to follow) and `memory-ledger:due` (a daily review routine with a PASS/FAIL/BLOCKED table).

Pure Python standard library; no dependencies.

## Install

```text
/plugin marketplace add NeoWYM/memory-ledger
/plugin install memory-ledger@memory-ledger
```

Per the Claude Code plugin documentation, a plugin's `bin/` directory is added to the Bash tool's PATH while the plugin is enabled, so Claude can run `memory-ledger` as a bare command. If it is not found, or to use it from your own shell, run the script from the plugin's install directory. Installed plugins are copied to `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` ([plugin loading](https://code.claude.com/docs/en/plugins/loading)); `CLAUDE_CODE_PLUGIN_CACHE_DIR`, when set, replaces the `~/.claude/plugins` root ([environment variables](https://code.claude.com/docs/en/env-vars)). The snippet picks the highest installed version and fails with a message if the plugin is not found. It ends with `exit 1` on failure, so in an interactive shell save it as a script or run it via `bash -c` rather than pasting it directly:

```bash
root="${CLAUDE_CODE_PLUGIN_CACHE_DIR:-$HOME/.claude/plugins}"
dir=$(for d in "$root"/cache/*/memory-ledger/*/; do
  [ -f "${d}scripts/memory_ledger.py" ] && printf '%s %s\n' "$(basename "$d")" "$d"
done | sort -V -k1,1 | tail -1 | cut -d' ' -f2-)
[ -n "$dir" ] || { echo "memory-ledger plugin not found under $root/cache" >&2; exit 1; }
python3 "${dir}scripts/memory_ledger.py" validate --memory-dir <dir>
```

Or symlink `bin/memory-ledger` onto your PATH.

## Frontmatter

Put the fields under `metadata:` in the project memory file, the way Claude Code writes memory files. List items must be indented.

```yaml
---
name: example-project
description: One line shown on the dashboard
metadata:
  type: project
  status: observing
  observe_until: 2026-12-01
  checkpoints:
    - 2026-11-20 | verify the first scheduled run produced output
  chores:
    - remove the temporary branch
---
```

| Field | Meaning |
| --- | --- |
| `type: project` | Required for the file to be tracked. |
| `status` | `todo`, `active`, `observing`, `done` or `superseded`. `done` and `superseded` are terminal and leave the dashboard. Anything else is a validation error. |
| `observe_until` | `YYYY-MM-DD`. The project's own observation window; at most one. Shown as overdue once past. |
| `checkpoints` | List of `YYYY-MM-DD \| what to check`. Dated sub-items; shown in their own section, flagged when overdue or due today. |
| `chores` | List of undated leftovers. Rendered even for terminal projects. |

The full rules, and the reasons for them, are in [`skills/conventions/SKILL.md`](skills/conventions/SKILL.md).

## Command line

```text
memory-ledger generate --memory-dir DIR [--output PATH] [--locale en|zh-TW] [--today YYYY-MM-DD]
memory-ledger validate --memory-dir DIR [FILES...]
memory-ledger hook          # reads PostToolUse JSON on stdin
```

- The memory directory is never derived from the working directory. Pass `--memory-dir` or set `MEMORY_LEDGER_DIR`; without either, `generate` and `validate` refuse to run (exit 2).
- `generate` writes `<memory-dir>/dashboard.md` unless `--output` is given and prints findings as warnings. Exit 0 on success, 2 on a usage or write error.
- `validate` exits 0 when clean, 1 on any finding, 2 on a usage error (no memory directory, a file argument that does not exist) or an internal error. With file arguments it checks only those files and skips the index check.
- `hook` exits 0 (nothing to report, or any internal error) or 2 (findings on stderr).
- `--today` overrides the date (used by the tests and for reproducible output).

## Locale

Dashboard text is selected by `--locale` or `MEMORY_LEDGER_LOCALE`. Available: `en` (default) and `zh-TW` (Traditional Chinese). Most validator messages are English in both locales. Three are localized: the zero-indent list item message, the placeholder inside the malformed-checkpoint message, and the hook hint. Tools that read the dashboard by heading should pin a locale; the emoji prefixes of the section headings are the same in every locale.

## Hook behaviour

`hooks/hooks.json` registers a PostToolUse hook for `Write|Edit|MultiEdit`. Plugin hooks fire in every project, so the hook is deliberately conservative:

- It acts only when `tool_input.file_path` matches `*/memory/project_*.md` and the file's frontmatter has `type: project`; the memory directory is the file's parent directory. Other files (for example notes in an unrelated `memory/` folder) are ignored.
- It validates just that file (statuses, checkpoints, list indentation, wikilinks), so a problem in another file does not interrupt an unrelated edit.
- On findings it exits 2 and writes them to stderr, which Claude sees. Otherwise it exits 0 with no output, including on malformed or missing input.

## Adopting in an existing memory directory

1. Run `memory-ledger validate --memory-dir <dir>` and read the findings. Old files usually need a `status` (use `done` for finished work) and an entry in `MEMORY.md` or `archive_index.md`.
2. Add `status` (and, where it applies, `observe_until`, `checkpoints`, `chores`) to the project files you want tracked.
3. Run `memory-ledger generate --memory-dir <dir>`.
4. Move links of finished projects from `MEMORY.md` to `archive_index.md` so the always-loaded index stays small. Both files together are what the validator treats as "the index".

## Development

```text
python3 -m unittest discover -s tests
claude plugin validate .
```

Tests use a synthetic memory directory under `tests/fixtures` and golden dashboards under `tests/golden`.

## Limitations

- It depends on Claude Code's auto-memory file format: markdown files with a leading `---` frontmatter block and `metadata:`-nested fields. If that format changes, the parser may need updating.
- The frontmatter parser is intentionally small, not a YAML parser. It reads flat `key: value` lines plus the two list fields. It strips one matching pair of surrounding quotes from scalar values and list items (double quotes: `\"` and `\\` are unescaped, other escapes stay literal; single quotes: `''` becomes `'`), which is how Claude Code's memory writer may re-serialize them; unbalanced quotes are left as written. Block scalars (`|`, `>`), flow lists with items and multi-line values are not supported; a list item with no indentation would be ignored, so the validator reports it as a finding.
- Index link detection expects links shaped like `(name.md)` using word characters, hyphens and slashes.
- The hook only sees edits made through the Write, Edit and MultiEdit tools, not edits made by shell commands.
- A `project_*.md` file without `type: project` frontmatter is invisible to the dashboard and to every per-file check. The unscoped `validate` and the regenerate warnings list such files; the hook ignores them.
- `checkpoints` and `chores` must be lists. A scalar value (`checkpoints: 2026-10-15 | text`) is reported as a finding because the parser would ignore it; use `[]` for none.

## License

MIT. See [LICENSE](LICENSE).

[繁體中文說明](README.zh-TW.md)
