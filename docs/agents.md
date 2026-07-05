# GraphCoding for AI agents

GraphCoding was extracted from a production setup where LLM agents do most of the coding under one hard rule: **never edit blind, never drift.** This page is how to wire any agent into the loop.

## What the agent gets

| Agent failure mode | GraphCoding counter |
|---|---|
| Greps for context, sees a sample, acts on the sample | `graphcoding show <file>` returns the **complete** blast radius |
| Re-derives architecture each session, differently | `status` + `query` reconstruct the exact work state from the repo |
| Plans in chat, then the plan evaporates | plans are `planned` nodes — versioned, queryable, enforced |
| Scope creep ("while I was here I also…") | unplanned files = named drift; the gate blocks the commit |
| Claims done when half-done | "done" is mechanical: `status` clean + `DRIFT=NONE` |
| Deletes something "unused" | `mark-delete` refuses while recorded callers exist |

The deeper shift: the graph is the agent's **long-term memory that survives session death** — and, symmetrically, the human's **audit trail of agent intent**. When an agent plans nodes before building, you can review what it *intended* separately from what it *did*.

## The agent contract (any harness)

Five rules, drop-in text in [templates/CLAUDE.md.snippet](../templates/CLAUDE.md.snippet):

1. **QUERY before touching any file**: `graphcoding show <path>` — read the summary and incoming edges. Never edit a file whose blast radius you haven't seen this session.
2. **DESIGN before building**: for every new file, `graphcoding plan <path> -s "<one-line intent>"` with edges; for removals, `graphcoding mark-delete`. Get the plan approved if the workflow calls for review.
3. **Build only what is planned.** Need an unplanned file mid-build? Plan it first — the summary you'd write is the justification.
4. **SYNC with every commit**: `graphcoding sync --staged` before committing (hooks enforce this; don't fight them, and never use `--no-verify`).
5. **VERIFY before claiming done**: `graphcoding status` shows nothing planned/doomed from your task and `graphcoding drift` prints `DRIFT=NONE`. Paste that output in your final report.

## Claude Code

Two integration levels; use both.

**Skill** (deep): copy [skill/graphcoding](../skill/graphcoding/SKILL.md) into `.claude/skills/graphcoding/`. It teaches the loop, the commands, and the recovery procedures, and triggers on any coding task.

**CLAUDE.md** (always-on): append the snippet:

```bash
cat templates/CLAUDE.md.snippet >> CLAUDE.md
```

Optionally enforce with hooks (Claude Code `PreToolUse` on `Bash(git commit*)` → run `graphcoding drift --staged`, block on exit 1) — this repo's ancestor ran exactly that gate on the agent itself, not just on git.

## Cursor / Copilot / Windsurf / anything with a rules file

```bash
cat templates/cursorrules.snippet >> .cursorrules   # or the equivalent rules file
```

Same five rules, phrased for harnesses without skill support. The git hooks and CI do the enforcement, so even a rules-ignoring agent can't merge drift.

## Custom harnesses / orchestrators

The CLI is the API — stable, line-oriented, exit-code honest:

```bash
graphcoding query <terms>      # ranked matches: name  [type/status] — summary
graphcoding show <node>        # summary, outgoing, incoming
graphcoding status             # planned / doomed / dangling / drift summary
graphcoding drift --quiet      # exit code only: 0 clean, 1 drift
```

Orchestration pattern that works (one human or planner-agent, N worker agents):

1. Planner projects the feature onto the graph (`plan`/`link`/`mark-delete`) → design commit.
2. Each worker gets: *"make nodes X, Y real; `graphcoding status` is your task list; query before editing; sync per commit."*
3. Workers physically can't creep scope (drift gate names any unplanned file) or strand deletions (gate again).
4. Reviewer diffs graph-intent vs. code-outcome; CI drift check is the merge arbiter.

Because the graph lives in the repo, this works across worktrees and branches for free — each branch carries its own graph state, and merging branches merges their designs line-by-line.

## Token economics

Worth stating plainly: querying the graph is not just safer than grepping, it is **cheaper**. A `show` on a hot file replaces reading a dozen files into context to discover the same edges — at a fraction of the tokens, with zero sampling risk. Summaries function as a compressed index of the codebase that the agent reads instead of the code, descending into actual source only where the task demands it. On large repos this is the difference between an agent that spends its context window learning the map and one that spends it doing the work.
