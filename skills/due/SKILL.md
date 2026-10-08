---
name: due
description: Review which tracked memory projects are due today. Regenerates the dashboard, lists overdue observation windows and due checkpoints, re-collects fresh evidence for each, produces a PASS/FAIL/BLOCKED table, then closes or extends items on the user's decision. Also lists the todo backlog when asked. Use for "what is due", "what should I verify", "what can I close", "what is on the todo list".
---

# /due: what should be reviewed today

This skill turns "which tracked items need verifying or closing today" into one repeatable routine. It reads the dashboard produced by memory-ledger; see the `conventions` skill for the field rules.

## Hard rules

- `dashboard.md` is generated. Never edit it by hand.
- Every PASS or FAIL must rest on evidence gathered today. Do not quote an earlier session's conclusion or an old result written in the project file: evidence that predates a change cannot show the change worked.
- If nothing is due and nothing is checkable today, say "nothing due today" and stop. Do not invent work.
- Ask before closing anything. Do not decide closure yourself.

The memory directory is the auto-memory directory given in your system prompt; call it `<dir>` below.

## Choose a mode first

- **Todo mode**: the user asks for the backlog ("what is on my todo list", "list the todos"). Regenerate (step 1), read the dashboard, list only the todo section, and stop. No evidence collection, no table; todo items have nothing to close. Any status claim beyond the dashboard's one-line summary ("already supported", "blocked on X") must come from reading the project file itself, with the source named, because summaries lag the body.
- **Review mode** (default): the user asks what to verify or close, or just runs `/due`. Do steps 1 to 5.
- If the wording is ambiguous, show the todo section first and offer to run the full review.

## Step 1: regenerate, do not just read

```bash
memory-ledger generate --memory-dir "<dir>"
```

Per the Claude Code docs, the plugin's `bin/` is added to PATH while the plugin is enabled. If `memory-ledger` is still not found, run the script from the plugin's cache directory (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`; if `CLAUDE_CODE_PLUGIN_CACHE_DIR` is set it replaces the `~/.claude/plugins` root) with the same arguments. This picks the highest installed version and stops with a message if the plugin is missing:

```bash
root="${CLAUDE_CODE_PLUGIN_CACHE_DIR:-$HOME/.claude/plugins}"
dir=$(for d in "$root"/cache/*/memory-ledger/*/; do
  [ -f "${d}scripts/memory_ledger.py" ] && printf '%s %s\n' "$(basename "$d")" "$d"
done | sort -V -k1,1 | tail -1 | cut -d' ' -f2-)
[ -n "$dir" ] || { echo "memory-ledger plugin not found under $root/cache" >&2; exit 1; }
python3 "${dir}scripts/memory_ledger.py" generate --memory-dir "<dir>"
```

Overdue is computed at generation time, so an old snapshot will happily show "none" today. Note any warnings printed at the end (invalid status, orphan file, dangling link, unindented list item); handle them in step 5.

Then Read `<dir>/dashboard.md`. Section headings depend on the output locale, so identify sections by their leading emoji, which are the same in every locale: ⚠️ observation window passed, 🔔 checkpoints, 🧹 chores, 🔵 observing, 🟢 active, 📋 todo.

## Step 2: list candidates (two classes)

- **Class A, date-driven**: everything in the ⚠️ section, plus 🔔 checkpoints marked overdue or due today. Copy them mechanically.
- **Class B, condition-driven**: items whose exit condition can be checked today even though no date has arrived. The dashboard cannot show these; open the body of every `observing` and `active` project. Typical cases: a sample-size or event-count gate that may already be met, a prerequisite change that has now been live long enough, an external blocker that has cleared. "Still running" does not count.

Doing only class A makes most days a no-op. If a body contains a future date that is not in `checkpoints`, move it into the frontmatter.

## Step 3: re-collect evidence for each candidate

1. Read the project file and find the verification method it records (a query, a command, an exit condition).
2. Run that method. Do not substitute a similar-looking check.
3. If the file records no runnable method, the verdict is **BLOCKED**; say what is missing. Do not use a proxy.
4. Before judging FAIL on "no data" or "no new samples", rule out harmless causes: a holiday or weekend, no new upstream content, a timezone date shift. A harmless cause gives BLOCKED (with the reason) or a suggested extension, not FAIL.
5. Check whether newer work supersedes the item (a newer project file, change or commit). If so, say "superseded by X" in the verdict.

How evidence is collected is specific to your environment (databases, clusters, dashboards, CI). The plugin ships no collectors. Put the exact verification command in each project file, or extend this skill locally with your own collection steps; a project that gives none stays BLOCKED.

## Step 4: present the table

| Item | Class | Exit condition | Evidence gathered today | Verdict |
|------|-------|----------------|-------------------------|---------|
| project_xxx | A / B | ... | actual numbers or state, with source | PASS / FAIL / BLOCKED |

Every cell must map to real tool output; if you could not obtain it, the verdict is BLOCKED. Cite the source (command, query, log path, or the body section). A dashboard row or an index line is not evidence. If an index line or dashboard summary disagrees with the body, list that below the table and suggest a fix.

Below the table, list the 🧹 chores (count and items). List only; do not expand or execute them, since they often hang on closed projects and no other step reaches them.

Then ask which items to close, which to extend, and which to leave.

## Step 5: act on the decision

**Close (PASS and the user agrees)**

1. Set `status` to `done` (or `superseded` if another project file replaced it) in the project's frontmatter.
2. Move the project's link from `MEMORY.md` to `archive_index.md`, in the same section. Skipping this leaves the file unreachable.
3. Run `memory-ledger generate --memory-dir "<dir>"` again.
4. Run `memory-ledger validate --memory-dir "<dir>"` without file arguments and require exit 0. A scoped run skips the index check, and a plain regenerate only prints warnings. If it fails, read which check fired; it may be an unrelated pre-existing problem.
5. Success means the item is gone from the dashboard and validate is clean. Do not use "it still renders" as a check.

**Extend (FAIL or not enough samples)**: set a new `observe_until`, write the reason and the numbers collected today into the body, regenerate, and confirm the item left the overdue section and is back under observing.

**Checkpoint finished**: delete the line from the project's `checkpoints` (record the conclusion in the body) or change it to the next date, then regenerate.

**Leave alone**: change nothing, but add today's numbers to the body so the next review does not start from zero.

## Scope

This skill only reviews and closes. If it uncovers a problem that needs real repair, finish the review and start that work separately.
