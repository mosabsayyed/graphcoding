# Core concepts

Everything in GraphCoding reduces to four ideas: **nodes**, **edges**, **statuses**, and **one file** that holds them.

## The graph file

`.graphcoding/graph.jsonl` — one JSON object per line, sorted by node name.

```json
{"name": "src/api/checkout.py", "type": "CodeFile", "status": "ok", "language": "python", "summary": "Checkout endpoint: validates cart, charges via payments service.", "edges": [{"to": "src/services/payments.py", "type": "IMPORTS"}]}
```

Why this format and not SQLite, not a server, not YAML:

- **Sorted + line-per-node** → a node edit is a one-line diff; two branches adding different nodes merge without conflict; `git blame` works on your architecture.
- **JSONL** → parseable by everything (`jq`, Python, awk); no schema migrations; append/repair by hand in an emergency.
- **In-repo** → the graph branches, reverts, and reviews *with* the code it describes. This is the property no external database can offer.

Commit it like a lockfile. It *is* a lockfile — for architecture.

`.graphcoding/config.json` sits next to it: tracked extensions, ignored directories, whether to scan symbols. Defaults are sensible; edit freely.

## Nodes

A node is anything worth knowing about. Its `name` is its identity:

- **File node** — repo-relative path: `src/services/payments.py`
- **Symbol node** — path + `::` + symbol: `src/services/payments.py::refund` (opt-in via `scan_symbols`, or created by hand where it matters)

| Field | Meaning |
|---|---|
| `name` | identity; path or `path::Symbol` |
| `type` | `CodeFile`, `CodeFunction`, `CodeClass`, `CodeModule`, `Component`, `Hook`, `TypeDef`, `ServiceDef`, `ConfigFile`, `Doc` |
| `status` | lifecycle — see below |
| `language` | informational |
| `summary` | **one line of human-language intent.** The single most valuable field in the system |
| `edges` | outgoing edges (see below) |

### The summary rule

A summary says what the thing is *for*, not what it contains. "Stripe charge + refund orchestration; the only module allowed to talk to Stripe" beats "payment functions." Scanners seed summaries from docstrings and first comments; humans and agents upgrade them. The store never lets a shorter auto-summary overwrite a longer written one.

## Edges

Directed, typed, stored on the source node.

| Edge | Reading |
|---|---|
| `IMPORTS` | source imports target (scanner-maintained) |
| `CALLS` | source invokes target at runtime — **including across process/repo boundaries a compiler can't see** (HTTP, queue, RPC) |
| `CONTAINS` | file contains symbol |
| `INHERITS` / `IMPLEMENTS` | type relationships |
| `REFERENCES` | source reads/configures/documents target |
| `DEPENDS_ON` | coarse dependency when nothing sharper fits |
| `RELATED_TO` | "these change together"; the edge of last resort — prefer anything more specific |

Two derived views do most of the daily work:

- **Blast radius** = incoming edges. `graphcoding show src/db.py` lists everything that breaks if you change `db.py`. This is the query that makes blind edits impossible.
- **Dangling edge** = an edge whose target isn't in the graph (yet). Not an error — **unfinished work, by design.** `graphcoding status` lists them as the wiring todo list.

The `CALLS`-across-boundaries edge deserves emphasis: it is the highest-value, lowest-cost record in the whole system. `frontend/src/services/authService.ts -[CALLS]-> backend/app/routes/auth.py` takes one `graphcoding link` command to record and saves every future maintainer from the classic "renamed the route, frontend broke in prod" incident.

## Statuses — the lifecycle dimension

Statuses are what turn a code map into a design contract. They encode **time**: what should exist, what does, what shouldn't.

| Status | Meaning | Enters | Leaves |
|---|---|---|---|
| `planned` | should exist; doesn't yet | `graphcoding plan` (DESIGN) | `sync` after the file is built → `ok` |
| `ok` | exists; graph agrees with disk | `scan` / `sync` | — |
| `needs-analysis` | exists; summary is machine-guessed, wants a human/agent pass | bulk migration | upgrading the summary |
| `to-be-deleted` | exists; shouldn't | `graphcoding mark-delete` | file removed + `sync` → node removed |

Rules the tooling enforces:

- A `planned` node with **no file** is fine — design ahead of code is the point (drift report shows it as informational).
- A `planned` node **with a file** is blocking drift: you built it, now sync it (one command).
- `mark-delete` **refuses while incoming edges exist** — you cannot schedule a deletion that strands callers. Rewire first, or `--force` when the callers die in the same change.
- A `to-be-deleted` node whose file still exists is blocking drift: the graph says remove it; finish the job.

## Drift — the four disagreements

Drift is any disagreement between disk and graph. There are exactly four kinds:

| Kind | Disk | Graph | Blocking? |
|---|---|---|---|
| `missing_node` | file exists | no node | yes — the graph is blind to real code |
| `ghost_node` | file gone | node remains | yes — the graph describes fiction |
| `built_not_synced` | file exists | still `planned` | yes — finish the loop |
| `not_deleted` | file exists | `to-be-deleted` | yes — finish the deletion |
| `unbuilt_planned` | no file | `planned` | no — that's just the plan |

`graphcoding drift` exits 1 on any blocking drift. The pre-commit hook runs it scoped to **your staged files** (`--staged`), so a teammate's un-graphed work-in-progress never blocks your commit; CI runs it unscoped as the final arbiter. Details: [drift.md](drift.md).

## What the scanner does and deliberately doesn't

`graphcoding scan` / `init` walks tracked files and produces file nodes with language, seed summary (docstring / first comment), and `IMPORTS` edges (Python via `ast`; JS/TS/Vue/Svelte via import-statement parsing with relative-path and `@/` alias resolution). Other languages get file nodes without automatic edges.

It is deliberately **not** a full static analyzer, and this is a feature:

1. The regenerable layer (imports) is cheap and self-healing — rescan any time.
2. The valuable layer (summaries, planned/deleted intent, cross-boundary `CALLS`) **cannot come from a scanner** by definition. Tools that promise "we'll extract your architecture automatically" extract structure and call it architecture. GraphCoding is honest about the split: machines maintain structure, minds record intent, the gate keeps both current.

## External nodes — the rest of the architecture

The classification is open and binary: a name that is a repo-relative path is **code** (scanned, drift-gated); a name with a scheme — `anything:` — is **another system** (declared, never expected on disk). Invent schemes for whatever your system touches: `db:orders`, `db:settings::llm_provider`, `mcp:router::get_blast_radius`, `svc:gateway`, `erp:sap::orders`. They exist to anchor the edges no scanner can find (`src/checkout.py -[CALLS]-> db:orders`). Created via `plan` (`--existing` for things already live), retired instantly by `mark-delete` (same callers-first safety catch). Full patterns: [whole-system-graph.md](whole-system-graph.md).

## Namespacing and monorepos

Node names are repo-relative paths, so a monorepo works out of the box (`backend/...`, `frontend/...` are just prefixes). For multi-repo systems, run one graph per repo and record cross-repo `CALLS` edges in the caller's graph using any stable convention for the target name (e.g. `other-repo:path/to/route.py`) — the edge will show as dangling, which is true and useful: it points out of this graph's world.
