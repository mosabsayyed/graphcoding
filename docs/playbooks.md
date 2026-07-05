# Playbooks — every SDLC situation, exact commands

Each playbook is the [loop](lifecycle.md) specialized to a situation. Commands are complete; adapt paths.

---

## 1 · Greenfield project

Design the system before it exists; the graph is the architecture doc that can't go stale.

```bash
mkdir myapp && cd myapp && git init
graphcoding init --hooks                  # empty graph, gate installed

# Architecture session = a series of `plan` calls
graphcoding plan src/app.py        -s "Entry point; wires config, db, api" -t CodeFile
graphcoding plan src/config.py     -s "Env-driven settings, single source"
graphcoding plan src/db/core.py    -s "Connection pool + session factory"
graphcoding plan src/api/users.py  -s "User CRUD endpoints" -e IMPORTS:src/db/core.py
graphcoding plan src/api/auth.py   -s "Login/refresh; issues JWTs" -e IMPORTS:src/api/users.py

git add .graphcoding && git commit -m "design: initial architecture"
```

Now build. `graphcoding status` is the backlog; the feature is done when it lists nothing. Every commit flips some `planned` → `ok` via `sync --staged`. The first "code" commit of the project already has a reviewed shape to conform to.

**Agent variant:** hand the agent the design commit and the instruction *"build until `graphcoding status` is clean; you may not create files that aren't planned — plan them first."* Scope creep becomes mechanically visible.

---

## 2 · Migrating an existing repo

Full guide: [migrating-existing-repos.md](migrating-existing-repos.md). Short version:

```bash
cd legacy-repo
graphcoding init --hooks        # scans everything: nodes + import edges
graphcoding status              # inspect; tune .graphcoding/config.json ignores
git add .graphcoding && git commit -m "graphcoding: adopt"
```

You are gated from this moment. Enrichment (better summaries, cross-boundary edges) happens incrementally — every time you touch an area, leave its nodes better than you found them.

---

## 3 · New feature

```bash
# QUERY the territory
graphcoding query checkout payment
graphcoding show src/api/checkout.py

# DESIGN
graphcoding plan src/services/discounts.py \
  -s "Coupon validation + price adjustment; only module that reads coupon rules" \
  -e IMPORTS:src/db/models.py
graphcoding link src/api/checkout.py CALLS src/services/discounts.py

# CODE until status is clean, SYNC each commit
graphcoding status
# ...build...
graphcoding sync --staged && git add -A && git commit -m "feat: discounts"
```

---

## 4 · Bug fix

The playbook that pays for the whole system. **Query first, fix second:**

```bash
graphcoding query session timeout           # locate the suspect area
graphcoding show src/auth/session.ts        # read intent + blast radius
#   incoming: 12 nodes — the fix must hold for all 12, not the 2 in the ticket
```

- Fix within existing structure → no DESIGN step; hooks handle sync.
- Fix reveals a missing edge (the bug existed *because* a dependency was invisible) → record it: `graphcoding link a CALLS b`. The graph now inoculates the next session against the same blindness.
- Root cause is structural → you're in playbook 5, and you know it *before* patching symptoms.

---

## 5 · Refactor

```bash
# Full territory map first — every caller of everything you'll move
graphcoding show src/utils/helpers.py       # 23 incoming edges, honesty hurts

# DESIGN the target shape
graphcoding plan src/utils/strings.py -s "String helpers (split from helpers.py)"
graphcoding plan src/utils/dates.py   -s "Date helpers (split from helpers.py)"
graphcoding mark-delete src/utils/helpers.py --force   # callers move in this change

git add .graphcoding && git commit -m "design: split helpers"
# CODE: move code, rewire the 23 callers; sync per commit.
# The refactor is DONE when: status shows no planned, no to-be-deleted,
# and `show src/utils/strings.py` carries the incoming edges helpers.py used to.
```

Half-finished refactors — the ones that haunt codebases for years — cannot hide: `status` lists the corpse until someone buries it.

---

## 6 · Deletion / dead code removal

```bash
graphcoding show src/jobs/export_v1.py
#   incoming: none (safe-to-change candidate — verify runtime refs)

graphcoding mark-delete src/jobs/export_v1.py
# refuses if anything still points at it — the safety catch

git rm src/jobs/export_v1.py
graphcoding sync --staged
git commit -m "remove dead export job"
```

Two protections stack: the graph proves no *recorded* caller exists, and `mark-delete`'s refusal forces you to rewire live callers before the file can even be scheduled to die. (Runtime-only references — reflection, config strings — are exactly what cross-boundary `CALLS`/`REFERENCES` edges are for; record them when you find them and this check becomes airtight.)

---

## 7 · Code review

The reviewer opens the PR and reads **the graph diff first** — it's the intent:

```diff
+{"name": "src/services/invoices.py", "status": "planned", "summary": "Builds and stores an invoice for every successful charge", ...}
+{"name": "src/api/checkout.py", ..., "edges": [..., {"to": "src/services/invoices.py", "type": "CALLS"}]}
-{"name": "src/legacy/receipts.py", ...}
```

Three review questions become answerable at a glance:

1. **Does the shape make sense?** (graph diff alone — before reading a line of code)
2. **Does the code match the stated intent?** (summary vs. implementation)
3. **Is anything undeclared?** (CI drift check green = no stowaway files; every code change is accounted for in the graph diff)

Review the design commit separately from the build commits on large changes and you've recovered architecture review as a practice — without meetings.

---

## 8 · Onboarding (human or agent)

```bash
graphcoding status                       # size, shape, live work in flight
graphcoding query auth                   # how does login work here?
graphcoding show src/auth/session.ts     # the load-bearing walls, by edge count
```

A new engineer's first-week map — or an agent's session bootstrap — is three commands against a graph that is *current by construction*. Compare: two weeks of tribal knowledge transfer, or an agent burning half its context window grepping.

**First-contribution ritual that compounds:** every time onboarding surprises you ("wait, *this* calls *that*?"), record the missing edge. The graph gets smarter exactly where it was weakest.

---

## 9 · Hotfix under pressure

The loop compresses but does not break:

```bash
graphcoding show src/billing/charge.py    # 15 seconds; blast radius before touching prod code
# fix, then:
git commit -m "hotfix: double-charge on retry"   # hooks sync + gate automatically
```

The QUERY step is *most* valuable at 3 a.m. — pressure is when humans skip the caller check and agents hallucinate one. If the gate blocks a genuinely burning commit: `sync --staged` takes two seconds. That's the entire toll.

---

## 10 · Documentation and knowledge work

The graph replaces the *structural* layer of docs (what exists, what depends on what, what's planned) — that layer is now generated and enforced. Prose docs shrink to what prose is for: tutorials, decisions, context. Point them at node names; node names are stable, greppable anchors.

`Doc` nodes (`*.md` files are scanned automatically) can carry `REFERENCES` edges to the code they describe — making *stale documentation itself queryable*: docs whose referenced nodes vanished show up as dangling edges.

---

## 11 · Team scale

- **The gate is per-author by construction**: pre-commit checks *your staged files*; a teammate's un-synced WIP never blocks you. CI checks everything at merge time — the tree that merges is the tree that's true.
- **Merge conflicts in graph.jsonl** are rare (sorted, line-per-node) and trivial when they happen: both sides added nearby lines; keep both, rerun `graphcoding drift`.
- **Design commits become the coordination primitive.** Two people (or two agents) about to build overlapping features collide at the `plan` stage — a one-line JSONL conflict — instead of at the 2,000-line PR stage.
- **Standup is `graphcoding status`.** Planned = in flight. Dangling edges = blocked on wiring. To-be-deleted = cleanup debt, visible forever until paid.

---

## 12 · Multi-agent development

The configuration GraphCoding was extracted from: one human directing several LLM agents on one codebase.

- Every agent session **starts** with QUERY (`status` + `show` on its work area) — sessions become stateless-but-informed; nothing depends on chat history surviving.
- The human (or an orchestrator agent) does DESIGN; worker agents receive *"make these planned nodes real"* — a task spec that is precise, verifiable, and already in the repo.
- Workers may not create unplanned files (drift names them), may not delete unmarked files (drift names those too), must sync per commit (gate enforces).
- The orchestrator reviews by diffing intent vs. outcome: `status` before, `status` after, graph diff in between.

The graph is simultaneously the agents' shared memory, their task queue, their scope fence, and the human's audit trail. That's not four tools — it's one file.
