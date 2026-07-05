# Migrating an existing repo

Zero to gated in an afternoon. The migration is designed to be **incremental and non-blocking**: you get the safety net on day one, and the graph gets richer every week you use it — you never stop the world to "document the codebase."

## Step 1 — Scan (5 minutes)

```bash
cd your-repo
pip install graphcoding
graphcoding init                # creates .graphcoding/, scans every tracked file
graphcoding status
```

The scan produces a file node per tracked source file: type, language, a seed summary (module docstring or first meaningful comment), and `IMPORTS` edges for Python and JS/TS (relative + `@/` alias resolution).

## Step 2 — Tune the boundary (10 minutes)

Look at what got scanned; adjust `.graphcoding/config.json`:

```json
{
  "track_extensions": [".py", ".ts", ".tsx", "..."],
  "ignore_segments": ["node_modules", "dist", "generated", "migrations", "..."],
  "ignore_tests": true,
  "scan_symbols": false
}
```

Rules of thumb:

- **Exclude generated code** (protobufs, migrations, build output). The graph should hold things a mind decided; generators redecide theirs on every run.
- **Keep tests out at first** (`ignore_tests: true`, the default). Test files triple node count while their blast radius is exactly themselves. Revisit later if your tests are load-bearing architecture.
- **Leave `scan_symbols` off initially.** File-level granularity is the right resolution for adopting; promote hot files to symbol level later, where it earns its keep.

Rerun `graphcoding scan` after tuning — it's idempotent and upserting.

## Step 3 — Gate (2 minutes)

```bash
graphcoding hooks                                   # pre-commit + post-commit
git add .graphcoding && git commit -m "graphcoding: adopt"
```

Add the [CI workflow](../templates/github-action-drift.yml) and make it a required check. **From this commit forward, the graph cannot rot** — that's the property everything else builds on. A merely-scanned graph that cannot rot is already more trustworthy than the best architecture doc you have.

## Step 4 — Enrich where it pays (ongoing, prioritized)

The scan gave you structure. Value concentrates in what the scan can't see, so aim effort by expected payoff:

**4a. The top of the blast-radius table.** Find your load-bearing files (most incoming edges) and give each a real summary — what it's *for*, what invariants it guards:

```bash
python3 -c "
import json,collections
inc=collections.Counter()
for l in open('.graphcoding/graph.jsonl'):
    for e in json.loads(l).get('edges',[]): inc[e['to']]+=1
for n,c in inc.most_common(15): print(c,n)"
```

Fifteen good summaries on the fifteen hottest nodes covers a disproportionate share of every future QUERY.

**4b. Cross-boundary CALLS edges.** The highest-value records in the system, and the scanner definitionally can't find them. One workshop question to the team: *"what talks to what, that no import shows?"* Frontend→API route, cron→table, service→queue→consumer:

```bash
graphcoding link frontend/src/services/authService.ts CALLS backend/app/routes/auth.py
graphcoding link jobs/nightly_export.py REFERENCES backend/app/models/orders.py
```

**4c. Let the loop do the rest.** Every bug fixed, feature built, and onboarding surprise adds its edges and summaries at the moment someone actually holds the knowledge. Six months of normal work enriches the graph more reliably than any documentation sprint — because the gate keeps every addition current forever.

## Step 5 — Point your agents at it (5 minutes)

Add the [CLAUDE.md snippet](../templates/CLAUDE.md.snippet) (or [.cursorrules](../templates/cursorrules.snippet)) and drop the [skill](../skill/graphcoding/SKILL.md) into your agent harness. From the next session, the agent queries before editing and plans before building. See [agents.md](agents.md).

## Monorepos and big repos

- Paths are the namespace — `backend/…`, `frontend/…` coexist naturally in one graph.
- 10k files ≈ 10k lines of JSONL ≈ a few MB — loads in tens of milliseconds; irrelevant to clone size next to any lockfile.
- If distinct sub-trees have genuinely separate lifecycles, run one graph per sub-tree root (`graphcoding --root backend/ …`) — but prefer one graph until proven otherwise; the cross-tree edges are usually the most valuable ones.

## What NOT to do

- **Don't hand-audit the whole scan output before gating.** Gate first (step 3), audit incrementally (step 4). Un-gated perfection rots; gated imperfection improves.
- **Don't backfill summaries with a bulk LLM pass on day one.** You'll spend a lot to generate plausible restatements of code (the graph's *lowest*-value layer) — and none of it records intent. Let summaries be written by whoever is holding the intent at edit time. (If you do bulk-summarize, mark those nodes `needs-analysis` so readers know the words are machine guesses.)
- **Don't rebuild the graph from scratch to fix drift.** `sync`/`scan` reconcile incrementally and preserve human-recorded intent; a rebuild destroys it. See [drift.md](drift.md).
