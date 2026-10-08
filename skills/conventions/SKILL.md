---
name: conventions
description: Conventions for tracking project progress in Claude Code auto-memory with status, observe_until, checkpoints and chores frontmatter, the generated dashboard.md, the archive index and wikilinks. Use when creating or updating a project memory file, closing a project, or when the memory-ledger hook or validator reports a finding.
---

# memory-ledger conventions

Project memories carry a few frontmatter fields. A script (`memory-ledger generate`) turns them into `dashboard.md`, and a validator (`memory-ledger validate`, also run by a hook after every write) checks them. The rules below exist because anything maintained by hand in two places drifts, and anything judged by eye gets overdue dates wrong.

## The memory directory

Commands need an explicit directory: `--memory-dir DIR` or the `MEMORY_LEDGER_DIR` environment variable. Use the auto-memory directory given in your system prompt. Never guess it from the working directory.

```bash
memory-ledger generate --memory-dir "<dir>"
memory-ledger validate --memory-dir "<dir>"
```

Output language is `en` by default; set `MEMORY_LEDGER_LOCALE=zh-TW` or pass `--locale` for Traditional Chinese.

## Frontmatter on `type: project` files

Fields live under `metadata:` in Claude Code's memory format. List items must be indented below their key; an unindented item is valid YAML but is silently dropped by the parser, so the validator reports it (file and line).

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

1. `status` is mandatory on every project file. Exactly five values are valid:
   - `todo`: planned, not started.
   - `active`: in progress with no fixed observation deadline.
   - `observing`: running under observation; normally has `observe_until`.
   - `done`: finished.
   - `superseded`: replaced by another project file; kept as history.

   `done` and `superseded` are terminal: they leave the dashboard, and the terminal check runs before the `observe_until` check, so a stale deadline cannot resurrect a closed project. Any other value (for example `open` or `closed`) makes the project silently vanish from the dashboard, which is why the validator rejects it.
2. `observe_until` (`YYYY-MM-DD`) is the project's own observation window. A project has at most one. It is compared with today's date by the script, not by eye.
3. Dates for sub-items go in `checkpoints`, never in `observe_until`. Each item is `YYYY-MM-DD | what to check`. Borrowing `observe_until` for one lagging sub-item misreports the whole project's window; a date written only in the body is invisible to the dashboard and never comes due. A checkpoint whose date does not parse never comes due either, so the validator rejects it. When a checkpoint is checked, delete the line (record the conclusion in the body) or move it to the next date.
4. Undated leftovers go in `chores`, one line each. A chore is a single action that is already decided, has a known method, and can be done at any time without changing the outcome. All three must hold:
   - no decision: otherwise open a `todo` project;
   - no timing: otherwise use a checkpoint;
   - no result to interpret: if doing it produces a number or a PASS/FAIL, it is a check, so use a checkpoint.

   Chores are rendered even for terminal projects, because a finished project's leftovers are the ones most likely to be forgotten. Do not turn the section into a task list; implementation steps belong in the body. Chores rot silently because nothing expires them, so write each with a one-line way to verify it is still undone, and verify before acting on one. To finish a chore, delete the line from the frontmatter and regenerate; never tick anything in `dashboard.md`.
5. Loose to-dos with no project to attach to get a small project file with `status: todo`. `dashboard.md` holds links and one-line summaries only; it is never a content store.

## dashboard.md is generated

Never edit it by hand. Change the frontmatter, then run `memory-ledger generate`. Regenerate rather than read an old snapshot: overdue is computed at generation time.

## Indexes: MEMORY.md and archive_index.md

- `MEMORY.md` is the always-loaded index for things that still affect the next action. One line per entry: what it is and when to open it.
- `archive_index.md` is the permanent, append-only record of closed work, in the same section layout. Keeping closed items out of `MEMORY.md` stops the always-loaded file growing with every finished project.
- When a project becomes `done` or `superseded`, move its link from `MEMORY.md` to `archive_index.md` in the same edit. This is exactly the moment the link is forgotten, because the project has just left the dashboard; forgetting it leaves the file reachable from nowhere.
- The full validator checks both directions across the two indexes together: every memory file must be reachable from one of them, and every index link must point at an existing file. Files named `MEMORY.md`, `archive_index.md` and `dashboard.md` are exempt.
- A scoped validate (with file arguments) skips the index check, because the index is a whole-directory property and a single file would make every other file look orphaned.

## Wikilinks

- `[[target]]` is the secondary navigation layer between memory files. The target is a filename stem or a frontmatter `name:`; both spellings are valid and `-` is treated as `_`.
- Text inside double brackets that is not a plain name (JSON like `[["a","b"]]`) is not a link and is ignored.
- There is deliberately no exception list; an allow-list rots like the links do. Do not use wikilink syntax for things outside the memory directory; write a plain path instead.
- When writing about wikilink syntax itself, do not type literal double brackets around an example name, or the validator will treat it as a real link.
- Wikilink checks can be scoped to one file, so the hook catches a typo at write time.

## Validator and hook

- `memory-ledger validate --memory-dir DIR` checks statuses, checkpoint dates, list indentation, wikilinks and index coverage. Exit 1 on any finding. With file arguments the index check is skipped.
- The plugin installs a PostToolUse hook for Write, Edit and MultiEdit. It acts only on `*/memory/project_*.md`, validates just the edited file (so a stale problem in another file does not flood an unrelated edit), and exits 2 with the findings on stderr. For any other path, or unreadable input, it does nothing.
- `memory-ledger generate` also prints the same findings as warnings after writing, without failing.
- When the hook reports a finding, fix the frontmatter first, then regenerate.
