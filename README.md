# GraphCoding

**Your repo's living knowledge graph — the design contract humans and AI agents code against.**

[![CI](https://github.com/mosabsayyed/graphcoding/actions/workflows/ci.yml/badge.svg)](https://github.com/mosabsayyed/graphcoding/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](pyproject.toml)
[![zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](pyproject.toml)

AI agents write most of the code now. And they all fail the same way: they **edit blind** (change a function without knowing who calls it), they **drift** (the plan says one thing, the code says another, nobody notices until it breaks), and they **forget** (every session starts from zero and re-derives the architecture — differently each time).

GraphCoding fixes this with one move: **keep a knowledge graph of your codebase inside the repo, and make it the source of truth for every change.** Files, functions, and components are nodes. Imports and calls are edges. Design intent is a `planned` node *before* the code exists. Deletions are marked *before* the file is removed. A drift gate blocks any commit where code and graph disagree.

The graph is a plain sorted-JSONL file. It diffs in pull requests, merges cleanly, needs no server, and works with any language and any agent.

```
┌─────────────────────────────────────────────────────────────┐
│                     The GraphCoding loop                     │
│                                                              │
│   1 QUERY    what exists? who calls it? (blast radius)       │
│   2 DESIGN   project the change onto the graph as            │
│              planned nodes + edges — before writing code     │
│   3 CODE     build exactly what the graph says is missing    │
│   4 SYNC     reconcile graph with every file you touched     │
│   5 VERIFY   drift gate: code ≠ graph → commit blocked       │
│                                                              │
│              impossible to drift, by construction            │
└─────────────────────────────────────────────────────────────┘
```

## 60-second start

```bash
pip install graphcoding        # or: pipx install graphcoding
# until the first PyPI release lands:
# pip install git+https://github.com/mosabsayyed/graphcoding

cd your-repo
graphcoding init --hooks       # scan the repo into a graph + install the gate
graphcoding status             # nodes, edges, planned work, drift
```

That's it. Your repo now has a `.graphcoding/graph.jsonl` — commit it like a lockfile.

```bash
# QUERY — before touching payment code, know the blast radius
$ graphcoding show src/services/payments.py
src/services/payments.py
  type: CodeFile   status: ok   language: python
  summary: Stripe charge + refund orchestration.
  incoming (blast radius — these break if you change it):
    <-[IMPORTS]- src/api/checkout.py
    <-[IMPORTS]- src/api/refunds.py
    <-[CALLS]-   src/jobs/reconcile.py

# DESIGN — declare the change before writing it
$ graphcoding plan src/services/invoices.py \
    -s "Invoice generation on successful charge" \
    -e IMPORTS:src/services/payments.py

# CODE — you (or your agent) build it. Then:
$ graphcoding sync --staged     # planned -> ok, summary refreshed
$ git commit -m "invoices"      # pre-commit gate re-checks drift
```

## Why a graph, and why *in* the repo

| Without GraphCoding | With GraphCoding |
|---|---|
| Agent greps for context, samples 5 of 40 call sites, breaks the other 35 | `show` returns the complete blast radius in one call |
| The design lives in a chat scrollback that's gone tomorrow | The design is `planned` nodes in the graph, versioned with the code |
| "Did we finish the refactor?" — someone greps and guesses | `status` lists every planned node not yet built and every deletion not yet done |
| Docs describe the architecture as of eight months ago | The drift gate makes stale impossible: code and graph move in the same commit |
| Every new agent session re-learns the codebase differently | Every session starts with the same queryable, current model |

Three properties make it work:

1. **In-repo, plain text.** The graph is sorted JSONL — one node per line. PRs show design changes as readable diffs. Branches merge. CI reads it with zero infrastructure.
2. **Design-first, not documentation-after.** `planned` nodes and dangling edges *are* the spec and the todo list. Work = making the graph true.
3. **Enforced, not aspirational.** Methodologies fail when they depend on memory. The pre-commit gate and CI check make the loop mechanical: drift blocks the commit that caused it — scoped to *your* staged files, so a teammate's WIP never blocks you.

## Built for AI agents (and the humans who review them)

GraphCoding was extracted from a production system where Claude builds a full-stack platform under a hard rule: *never edit blind, never drift.* The agent-facing pieces ship in this repo:

- **[Agent skill](skill/graphcoding/SKILL.md)** — drop into `.claude/skills/` (or any skill-aware harness); teaches the agent the loop and the commands.
- **[CLAUDE.md / AGENTS.md snippet](templates/CLAUDE.md.snippet)** — the five rules in ~20 lines for any coding agent.
- **[Cursor rules](templates/cursorrules.snippet)** — same contract for Cursor.
- **[CI workflow](templates/github-action-drift.yml)** — drift gate as a required check, so agent PRs can't merge stale.

An agent with GraphCoding stops asking "what does this codebase look like?" and starts asking `graphcoding query auth token refresh`. It stops "I'll refactor this" and starts `graphcoding show src/auth/session.ts` → *here are the 12 places that break.* The graph is the agent's long-term memory — and your audit trail of what it intended vs. what it did.

## Covers the whole SDLC

The [playbooks](docs/playbooks.md) give the exact command sequence for each case:

| Situation | Playbook |
|---|---|
| Greenfield project | design the whole system as `planned` nodes; code until `status` is clean |
| Existing repo | `init` scans everything; [migration guide](docs/migrating-existing-repos.md) |
| New feature | plan → build → sync, gated |
| Bug fix | query the blast radius first; fix without collateral damage |
| Refactor / deletion | `mark-delete` refuses while callers exist — dead-code removal with a safety catch |
| Code review | review the graph diff *next to* the code diff: intent vs. implementation |
| Onboarding | `status` + `query` instead of two weeks of tribal knowledge |
| Team scale | per-file gate scoping, mergeable JSONL, CI as arbiter |

## Documentation

| | |
|---|---|
| [Manifesto](docs/manifesto.md) | why coding against a graph beats coding against files |
| [Core concepts](docs/core-concepts.md) | nodes, edges, statuses, the graph file format |
| [The loop](docs/lifecycle.md) | QUERY → DESIGN → CODE → SYNC → VERIFY, in depth |
| [Playbooks](docs/playbooks.md) | every SDLC situation, exact commands |
| [Migrating an existing repo](docs/migrating-existing-repos.md) | zero to gated in an afternoon |
| [Starting a new project](docs/starting-new-projects.md) | graph-first greenfield |
| [AI agents](docs/agents.md) | Claude Code, Cursor, Copilot, custom harnesses |
| [Drift](docs/drift.md) | the four drift classes and how the gate works |
| [Scaling up](docs/scaling.md) | embeddings, semantic search, Neo4j — when JSONL isn't enough |
| [FAQ](docs/faq.md) | "isn't this just documentation?" and other fair questions |

## Dogfood

This repo is built with GraphCoding: [`.graphcoding/graph.jsonl`](.graphcoding/graph.jsonl) is its own graph, and [CI](.github/workflows/ci.yml) fails if any commit drifts from it. Clone it and run `graphcoding status` to see the tool describe itself.

## Design principles

- **Zero dependencies.** Python stdlib only. Nothing to break.
- **Any language.** Deep parsing for Python and JS/TS; file-level nodes + manual edges for everything else. The methodology is language-agnostic; the scanner is just a convenience.
- **The graph carries intent, not just structure.** A scanner can rebuild imports; it cannot rebuild *why*. Summaries, planned nodes, and cross-cutting edges (the frontend service that calls a backend route over HTTP — no import will ever show that) are the durable value.
- **Escape hatches everywhere.** It's a text file. `jq` it, script it, or delete `.graphcoding/` and you've lost nothing but the memory.

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). The bar for a PR here: the graph diff must tell the story of your change before the code diff does.

## License

[MIT](LICENSE)
