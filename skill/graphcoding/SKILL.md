---
name: graphcoding
description: Use on EVERY coding task in a repo that has a .graphcoding/ directory — editing, creating, deleting, refactoring, debugging, reviewing, or planning code. The repo's knowledge graph is the source of truth: query it before touching code, project designs onto it before building, sync it with every change. Drift between code and graph blocks commits.
---

# GraphCoding — code against the graph

This repo keeps a knowledge graph of itself in `.graphcoding/graph.jsonl`. It is the source of truth for what exists, what it's for, who depends on what, what is planned, and what is scheduled for deletion. Your job on every coding task is to keep the code and the graph as the same statement.

**Check:** if `.graphcoding/` exists in the repo root, this skill applies to every coding task. All commands below are the `graphcoding` CLI (`pip install graphcoding`).

## The loop (never reorder, never skip)

### 1 · QUERY — before you open or edit ANY file

```bash
graphcoding query <task keywords>     # find the territory
graphcoding show <path>               # BEFORE editing that path
graphcoding status                    # session start: planned work, drift, state
```

`show` gives you the file's intent (summary) and its **complete blast radius** (incoming edges = everything that breaks if you change it). Never edit a file whose blast radius you haven't seen in this session. Do not substitute grep — grep samples; the graph enumerates.

If the graph contradicts what you find in source, the graph is stale: fix it immediately (`sync --files <path>`, or correct the summary/edges) before proceeding.

### 2 · DESIGN — before you write new code

Project the change onto the graph first:

```bash
graphcoding plan <path> -s "<one line: what it WILL do>" -e IMPORTS:<dep> ...
graphcoding link <source> CALLS <target>      # incl. cross-boundary (HTTP/queue) edges
graphcoding mark-delete <path>                # for every removal (refuses if callers exist)
```

Rules:
- Every new file gets a `plan` with a real summary **before** you create the file.
- Summaries state responsibility, not contents: "the only module that talks to Stripe", not "payment functions".
- `mark-delete` refusing = the design has a hole (live callers). Rewire them first; `--force` only when the callers are removed in the same change.
- Edges to not-yet-existing nodes are correct — they are the work list.

### 3 · CODE — build only what is planned

`graphcoding status` is your task list: planned nodes to build, to-be-deleted files to remove, dangling edges to wire. Need an unplanned file mid-build? **Plan it first** (the one-line summary is the justification), then build it. Files you create without planning will be named by the drift gate.

### 4 · SYNC — with every commit, not at the end

```bash
graphcoding sync --staged     # before each commit; planned -> ok, deletions complete
```

The pre-commit hook enforces this; **never bypass it with `--no-verify`**. If the hook blocks you: run the sync, `git add .graphcoding/graph.jsonl`, retry the commit.

### 5 · VERIFY — before you claim done

Done means, mechanically:

```bash
graphcoding status    # nothing planned / to-be-deleted / dangling from YOUR task
graphcoding drift     # prints DRIFT=NONE
```

Paste that output in your completion report. "The code works" without `DRIFT=NONE` is not done.

## Drift recovery

`drift` reporting issues? Reconcile **incrementally** — never delete and rebuild the graph (that destroys human-recorded intent that cannot be regenerated):

```bash
graphcoding sync            # repairs missing/ghost/built-not-synced
graphcoding drift           # re-check; must print DRIFT=NONE
```

`not_deleted` findings are not auto-repaired on purpose: the graph says that file should be removed. Remove the file (then sync), or explicitly revert the decision by re-planning the node.

## Quick reference

| Need | Command |
|---|---|
| find code by meaning | `graphcoding query <terms>` |
| know a file before editing | `graphcoding show <path>` |
| declare a new file | `graphcoding plan <path> -s "..." -e IMPORTS:<dep>` |
| record any dependency | `graphcoding link <src> <CALLS\|IMPORTS\|REFERENCES\|...> <dst>` |
| schedule a removal | `graphcoding mark-delete <path>` |
| declare non-file architecture (db table, settings row, MCP tool, queue, API) | `graphcoding plan db:orders --existing -s "..."` then `link` its readers/writers |
| reconcile after changes | `graphcoding sync --staged` (or `--files`, `--commit`) |
| task list / work state | `graphcoding status` |
| the done-check | `graphcoding drift` → `DRIFT=NONE` |
| memory quality (stale summaries, orphans) | `graphcoding health` |

Blast-radius honesty: `show` lists **recorded** edges. If it prints the
"scanner-visible edges only" caveat, runtime/cross-boundary callers may exist
unrecorded — verify once, then `graphcoding link` what you find so the next
session inherits it. When `health` lists a stale-summary suspect for a file you
are touching, fix the summary in the same change.
