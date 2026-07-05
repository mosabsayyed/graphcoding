# The loop: QUERY → DESIGN → CODE → SYNC → VERIFY

Every change, from a one-line fix to a subsystem rewrite, runs the same five steps. Small changes run them in thirty seconds; large ones over days. The steps never reorder, because each one exists to make the next one safe.

## 1 · QUERY — never touch code you haven't asked the graph about

```bash
graphcoding query payments refund          # find the territory
graphcoding show src/services/payments.py  # know it before entering
```

`show` answers the three questions that prevent 90% of regressions:

- **What is this for?** (summary — intent, not just contents)
- **Who breaks if I change it?** (incoming edges — the complete blast radius, not a grep sample)
- **What does it lean on?** (outgoing edges — including planned/missing targets)

Zero incoming edges is information too: a deletion candidate, or a node whose real callers are cross-boundary and were never recorded — either way, you now know what to verify instead of what to assume.

**The discipline:** if the graph's answer surprises you, the graph is either wrong (fix it now — one `link` or summary edit) or you were about to make a mistake. Both outcomes pay for the query.

## 2 · DESIGN — project the change onto the graph before writing code

Say the task is "add invoicing to checkout." Before any code:

```bash
graphcoding plan src/services/invoices.py \
    -s "Builds and stores an invoice for every successful charge" \
    -e IMPORTS:src/services/payments.py -e IMPORTS:src/db/models.py

graphcoding plan src/api/invoices.py \
    -s "GET /invoices list + PDF download endpoints" \
    -e IMPORTS:src/services/invoices.py

graphcoding link src/api/checkout.py CALLS src/services/invoices.py
graphcoding mark-delete src/legacy/receipts.py   # superseded by invoices
```

Four lines, and the design now exists as a first-class, versioned artifact:

- The **planned nodes** say what will exist and why (the summary is written at design time, when intent is clearest).
- The **edges** say how it wires into the system — `checkout.py`'s new edge points at a node that doesn't exist yet, which is precisely the work remaining.
- The **mark-delete** says what this change retires. (It will refuse if `receipts.py` still has callers — the design step just caught a migration you'd have discovered in production.)

Committing at this point is legitimate and useful: a **design commit** whose diff is pure graph. Reviewers can approve the shape of a change before the code exists. On a team, this is how two agents avoid building conflicting versions of the same feature.

For a large feature, this step *is* the architecture session. The graph replaces the design doc that would have gone stale; `unbuilt_planned` in the drift report replaces the task tracker that would have disagreed with reality.

## 3 · CODE — make the graph true

Build exactly what the graph says is missing:

```bash
graphcoding status
# planned — left to build (2):
#    ? src/api/invoices.py — GET /invoices list + PDF download endpoints
#    ? src/services/invoices.py — Builds and stores an invoice for every successful charge
# to-be-deleted — left to remove (1):
#    ! src/legacy/receipts.py
# dangling edges — dependencies not wired yet (1):
#    src/api/checkout.py -[CALLS]-> src/services/invoices.py
```

`status` is the task list, and it cannot lie, because it's computed from the same graph the gate enforces. For an AI agent this is the crucial property: a fresh session runs one command and knows *exactly* where the work stands — no reconstruction from chat history, no "I believe the plan was."

Scope discipline falls out for free: code that builds a planned node is in scope; code that would create nodes nobody planned is scope creep, and the drift report will name it (`missing_node`).

## 4 · SYNC — the graph moves with every change, not after all of them

```bash
graphcoding sync --staged        # before each commit
# or: sync --commit HEAD | sync --files a.py b.ts | sync   (fix all drift)
```

Sync rescans exactly the changed files: `planned` becomes `ok` when built, summaries refresh (a richer written summary always survives a shorter docstring), deleted files take their nodes and all edges pointing at them out of the graph, `to-be-deleted` completes when the file is really gone.

Sync as you go — per commit, not per feature. A ten-commit feature with one sync at the end has nine commits where the graph lied to whoever queried it (step 1 is only trustworthy because step 4 is habitual). The post-commit hook makes this automatic; the pre-commit gate makes forgetting it impossible.

## 5 · VERIFY — the gate

```bash
graphcoding drift          # full honesty: exit 1 on any blocking drift
graphcoding drift --staged # what the pre-commit hook runs: your files only
```

Three layers, each catching what the previous one missed:

| Layer | Runs | Scope | Catches |
|---|---|---|---|
| pre-commit hook | every `git commit` | staged files | drift at the moment it's cheapest to fix |
| post-commit hook | after commit | committed files | anything that slid past (merges, `--no-verify`) |
| CI (`drift` unscoped) | every push/PR | whole tree | everything, as a required check — the arbiter |

The staged-file scoping matters for teams: the full tree may drift because of *someone else's* work-in-progress; your commit is gated only on the files *you* are committing. CI holds the line globally where merging happens.

Done means: `graphcoding status` shows no planned, no to-be-deleted, no dangling edges from your change — and `DRIFT=NONE`. Not "I finished the code." The loop closes when **the graph and the code became the same statement.**

## The loop at three scales

| | QUERY | DESIGN | CODE | SYNC | VERIFY |
|---|---|---|---|---|---|
| **typo-level fix** | `show` the file (10s) | skip — no structural change | fix | auto (hook) | auto (hook) |
| **feature** | `query` + `show` the touched area | plan nodes/edges, maybe a design commit | build to `status` | per commit | gate + CI |
| **subsystem rewrite** | map the whole territory, record missing edges you discover | full projection: planned + mark-delete across dozens of nodes; reviewed as a design PR | days of work, always resumable via `status` | per commit | gate + CI + final `status` clean |

Same loop. The graph doesn't care how big the change is — only that the code and the contract move together.
