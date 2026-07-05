# Modeling the whole architecture — not just code files

Code files are one node species. Real systems break at the joints code scanners can't see: the database schema, the settings table that steers runtime behavior, the MCP server an agent calls, the queue between two services, the third-party API. GraphCoding models all of it in the same graph, with the same lifecycle, queried by the same commands.

## The open classification: code, or another system

One binary rule, deliberately open-ended:

- **Code** — the name is a repo-relative file path (`src/app.py`, optionally `::Symbol`). Scanned automatically, drift-gated against disk.
- **Another system** — the name carries a scheme, `anything:` (like a URI). Never expected on disk; it's a declaration, versioned and reviewable like everything else.

The scheme vocabulary is **yours to invent** — GraphCoding imposes nothing. Whatever your system touches can be absorbed into the graph:

| Scheme (examples, not a fixed list) | For |
|---|---|
| `db:` | database objects — `db:orders`, `db:settings::llm_provider` |
| `mcp:` | MCP servers + tools — `mcp:router::get_blast_radius` |
| `svc:` / `queue:` / `api:` | services, queues, third-party APIs |
| `erp:`, `sensor:`, `sap:` … | whatever your world contains — `erp:sap::orders`, `sensor:plant-7` |
| `team:`, `doc:`, `policy:` | even non-technical anchors, if edges to them carry design weight |

Node *types* are equally open — `-t` accepts any word; the built-in names (`CodeFile`, `ServiceDef`, …) are conventions, not a schema.

The `::` convention scales down inside externals exactly as it does inside files: a table is `db:orders`, one *load-bearing row* of a settings table is `db:settings::llm_provider`, one tool of an MCP server is `mcp:router::get_root_cause`.

Create them with `plan` — future ones as plans, live ones with `--existing`:

```bash
# a table that exists today
graphcoding plan db:orders --existing -t ServiceDef \
  -s "Order ledger; written only by checkout, read by reporting + reconcile job"

# a table the current feature will add — reviewable in the design commit
graphcoding plan db:invoices -t ServiceDef \
  -s "One row per issued invoice; FK to orders; immutable after issue"

# an MCP tool agents depend on
graphcoding plan mcp:router::get_blast_radius --existing -t ServiceDef \
  -s "Returns transitive dependents of a node; used by the review workflow"
```

## The edges are the point

External nodes exist to anchor the edges no scanner can ever find:

```bash
graphcoding link src/services/checkout.py CALLS      db:orders
graphcoding link src/jobs/reconcile.py    REFERENCES db:orders
graphcoding link src/llm/completion.py    REFERENCES db:settings::llm_provider
graphcoding link src/agents/reviewer.py   CALLS      mcp:router::get_blast_radius
graphcoding link svc:worker-pool          CALLS      queue:invoice-events
```

Then the questions that cause production incidents become one-command queries:

```bash
graphcoding show db:orders
#   recorded incoming edges (blast radius — these break if you change it):
#     <-[CALLS]-      src/services/checkout.py
#     <-[REFERENCES]- src/jobs/reconcile.py
#     <-[REFERENCES]- src/reporting/revenue.py
```

*"Who breaks if I alter this table?"* — answered before the migration is written, not after the pager goes off.

## The three cases, concretely

### Database schema

Two complementary layers; use both:

1. **Migration/DDL files** are ordinary file nodes (scanned automatically). They carry the *history* of the schema.
2. **`db:` nodes** carry the *current truth*: one node per table/view that matters, summary stating its ownership rule ("written only by X"), edges from every reader and writer.

Schema change = the standard loop: `plan db:new_table` (or update the summary of an existing one) in the design commit → migration file lands as a code node → `link` the touched readers/writers. A dropped table is `mark-delete db:old_table` — and the safety catch refuses while recorded readers exist, which is precisely the check DBAs do by grep and prayer.

### Settings / configuration tables

The sneakiest dependency class in modern systems: behavior steered by *rows*, not code. Model the rows that carry design weight as sub-nodes — `db:settings::llm_provider`, `db:instruction_elements::reviewer_prompt` — each with a summary saying what reads it and what it controls, plus `REFERENCES` edges from the consuming code.

Now "can I change this config row?" has a blast radius, config-driven behavior shows up in design review, and a prompt-in-a-table (the standard pattern for LLM apps) is a first-class architectural element instead of invisible state.

### Environments — dev, staging, prod

The third category after code and systems: **where things run**. Environments are declared nodes (`env:dev`, `env:staging`, `env:prod`) whose summaries carry the facts that prevent disasters — who may deploy, what is read-only, where it lives:

```bash
graphcoding plan env:prod --existing -t Environment \
  -s "Production (prod.example.com). READ-ONLY for agents; deploys only via ops/deploy.sh after staging sign-off"
graphcoding plan env:staging --existing -t Environment \
  -s "Staging; safe for agent experiments; wiped weekly"

# topology and promotion path as edges
graphcoding link svc:api-gateway DEPLOYED_IN env:prod
graphcoding link env:dev     PROMOTES_TO env:staging
graphcoding link env:staging PROMOTES_TO env:prod
```

Conventions that keep it clean:

- **Code is environment-agnostic** — the same file ships everywhere, so file nodes never carry an environment. Environments attach to the *deployed* things: services, databases, config.
- **Qualify instances only where environments genuinely differ**: if staging and prod share a schema, one `db:orders` is right; if an instance difference carries design weight, nest schemes — `prod:db:orders`, `staging:db:orders` (any `scheme:` chain is a valid external name).
- **Config divergence is the usual suspect**: `db:settings::llm_provider` reading differently per env is exactly what `CONFIGURES` edges from env nodes are for.
- **Agent guardrail**: the skill tells agents to `show env:*` before any deploy/restart/migration — the environment's rules ("read-only", "deploys via X only") reach the agent as a query result at the moment it matters, not as a memory of a memory.

### MCP servers and agent tooling

MCP has two faces, classified differently. The **tool as a capability** — what agents and code call — is a declared system node (`mcp:router::semantic_search`), because consumers depend on the interface, which outlives file renames. The **server's source**, if it lives in your repo, is ordinary code nodes. The join is an edge: `mcp:router::semantic_search -[IMPLEMENTED_BY]-> mcp-server/src/tools.py` — so changing the implementation walks the blast radius through the declaration to every consumer. Third-party MCP you don't host has only the first face.

Declare each server (`mcp:router --existing`) and each tool that matters, then `link` every consumer — including *skills and agent configs*, which are file nodes already (`.claude/skills/reviewer/SKILL.md CALLS mcp:router::semantic_search`).

Payoff: renaming or retiring an MCP tool stops being a grep-across-repos gamble. `show mcp:router::semantic_search` lists every dependent skill, workflow, and module; `mark-delete` refuses until they're rewired. Your agent infrastructure gets the same deletion safety as your code.

## Rules of thumb

- **Model what carries design weight, not everything.** Twenty `db:` nodes for the tables that matter beats four hundred generated ones nobody summarizes. External nodes are hand-curated by definition — that's their value.
- **Summaries state ownership and invariants** ("written only by checkout", "immutable after issue", "rows are versioned, never edited"). These are the sentences that prevent incidents.
- **Externals are declarations, so keep them honest in review.** The drift gate can't check the real database against `db:` nodes (see limits below) — but the PR review can: a migration file changing in the same diff as its `db:` node is the pattern reviewers learn to expect.

## Honest limits

The gate cannot verify that `db:orders` still matches the live database, that `mcp:router` is deployed, or that `api:stripe` didn't change under you — externals are *declared*, not *scanned*. That's the same trust level as every architecture diagram ever drawn, minus the rot: these declarations live in version control, appear in every relevant PR, carry blast radii, and `health` counts the ones nobody has summarized. Teams that want mechanical verification of externals can build it per-system (a CI script diffing `db:` nodes against `information_schema` is an afternoon's work — and a welcome PR).
